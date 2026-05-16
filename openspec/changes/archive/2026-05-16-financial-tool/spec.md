# Financial Tool Specification

## Glossary

- **metricas_financieras**: SQLite table con columnas id, anio, seccion, concepto, valor_num, valor_raw, unidad, es_ratio.
- **query_financiero**: `@tool` de LangChain que envuelve consultas SELECT parametrizadas contra SQLite.
- **bind_tools()**: Método de LangChain para exponer tools al LLM vía function calling.

## Constraints

- 0 nuevas dependencias PyPI (`sqlite3` stdlib).
- DB en `data/processed/metricas_financieras.db` (configurable vía `FINANCIAL_DB_PATH`).
- Auto-seed desde `data/estelar_reportes/metricas_financieras.csv` si DB no existe o CSV es más reciente.
- Valores monetarios en millones de COP.
- Si `bind_tools()` no es soportado (Ollama), operar sin tool (solo RAG).

## Out of Scope

- Escritura/mutación en SQLite.
- LangGraph (loop manual).
- Múltiples tools financieras (una sola tool cubre todo).
- Reemplazo de RAG.

---

## 1. financial-data

**ID**: FTD-001  
**Description**: Store SQLite read-only con métricas financieras. Auto-seed desde CSV.

| ID | Requirement |
|----|-------------|
| FTD-REQ-01 | MUST seed `metricas_financieras` desde CSV si DB no existe |
| FTD-REQ-02 | MUST re-seed si CSV es más reciente que DB |
| FTD-REQ-03 | Table MUST tener columnas: id, anio, seccion, concepto, valor_num, valor_raw, unidad, es_ratio |
| FTD-REQ-04 | Indexes MUST existir en anio, seccion, concepto |

| # | Scenario |
|---|----------|
| 1 | GIVEN no DB file WHEN primer query THEN DB creada + seedeada FROM CSV |
| 2 | GIVEN DB existente + CSV más nuevo WHEN query THEN DB re-seedea |
| 3 | GIVEN DB seedeada WHEN SELECT anio=2024 AND concepto='EBITDA' THEN 1 row |

**Acceptance**: `consultar_metricas(seccion="EBITDA", anio=2024)` retorna tupla correcta.  
**Dependencies**: CSV en `data/estelar_reportes/metricas_financieras.csv`.  
**Open Questions**: None.

---

## 2. tool-calling

**ID**: FTD-002  
**Description**: `@tool query_financiero` con parámetros estructurados (no SQL generado por LLM).

| ID | Requirement |
|----|-------------|
| TCL-REQ-01 | MUST usar `@tool` de langchain-core |
| TCL-REQ-02 | Params: seccion (str\|None), anio (int\|None), concepto (str\|None) |
| TCL-REQ-03 | SQL MUST ser solo SELECT, solo tabla metricas_financieras, params sanitizados |
| TCL-REQ-04 | Output MUST ser JSON `[{anio,seccion,concepto,valor_num,...}]` |
| TCL-REQ-05 | Sin resultados MUST retornar `[]` |

| # | Scenario |
|---|----------|
| 1 | GIVEN LLM llama tool(concepto="EBITDA") WHEN ejecutada THEN JSON con todas las filas EBITDA |
| 2 | GIVEN LLM llama tool(seccion="Balance general") WHEN ejecutada THEN filas de balance |
| 3 | GIVEN usuario pregunta no-financiera WHEN LLM decide THEN tool NO es llamada |

**Acceptance**: `query_financiero(seccion=None, anio=2024, concepto=None)` retorna todas las filas de 2024.  
`query_financiero(concepto="NO_EXISTE")` retorna `[]`.  
**Dependencies**: FTD-001.  
**Open Questions**: ¿Agregar `top_n`? (Deferred — no necesario para queries actuales.)

---

## 3. qa-extended

**ID**: FTD-003  
**Description**: `responder_pregunta()` bindea `query_financiero` y re-enruta tool_calls.

| ID | Requirement |
|----|-------------|
| QAE-REQ-01 | MUST bindear `query_financiero` via `.bind_tools()` |
| QAE-REQ-02 | Si hay tool_call, MUST pasar resultado al LLM para formatear respuesta |
| QAE-REQ-03 | `RespuestaQA` MUST agregar `uso_tool_financiera: bool`, `tool_used: bool` |
| QAE-REQ-04 | Fallback: sin `bind_tools()`, operar solo RAG |
| QAE-REQ-05 | Dashboard MUST mostrar badge "📊 Dato financiero" si tool usada |

| # | Scenario |
|---|----------|
| 1 | GIVEN "¿EBITDA 2024?" WHEN respuesta THEN `uso_tool_financiera=True` + badge |
| 2 | GIVEN "¿cómo reservo?" WHEN respuesta THEN `uso_tool_financiera=False` |
| 3 | GIVEN Ollama sin tool support WHEN query THEN RAG-only fallback |

**Acceptance**: `responder_pregunta("¿EBITDA 2024?")` retorna dict con `uso_tool_financiera=True`.  
Tests con mock LLM verifican ruta de tool invocation.  
**Dependencies**: FTD-001, FTD-002.  
**Open Questions**: None.

---

## 4. system-prompt-update

**ID**: FTD-004  
**Description**: Actualizar `system_prompt.md` para reflejar SQLite local y params estructurados.

| ID | Requirement |
|----|-------------|
| SPU-REQ-01 | MUST cambiar referencias de Supabase a SQLite local |
| SPU-REQ-02 | MUST cambiar ILIKE → LIKE (SQLite no soporta ILIKE) |
| SPU-REQ-03 | MUST describir params (seccion, anio, concepto) en vez de SQL crudo |
| SPU-REQ-04 | MUST actualizar Ejemplo 2 para usar params en vez de SQL |
| SPU-REQ-05 | MUST agregar nota sobre sanitización automática |

| # | Scenario |
|---|----------|
| 1 | GIVEN `system_prompt.md` actualizado WHEN grep "SUPABASE" THEN 0 matches |
| 2 | GIVEN `system_prompt.md` actualizado WHEN grep "ILIKE" THEN 0 matches |
| 3 | GIVEN `system_prompt.md` WHEN Ejemplo 2 THEN usa `query_financiero(seccion=..., anio=...)` |

**Acceptance**: Sin menciones a Supabase. Sin ILIKE. Ejemplo 2 actualizado.  
**Dependencies**: None.  
**Open Questions**: None.
