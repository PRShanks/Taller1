# Proposal: Financial Tool — SQLite + LangChain Tool Calling

## Intent

RAG falla en consultas financieras exactas — embeddings no capturan "EBITDA 2024 = COP 70.147M". Ruta **determinista** via SQLite que el LLM invoque al detectar consultas numéricas.

## Scope

### In Scope
- `llm/financial/`: `db.py`, `tool.py`, `__init__.py`
- CSV → SQLite auto-seed en primer uso
- `llm/core/qa.py`: bindear tool via `.bind_tools()` + trackear uso
- `llm/models.py`: extender `RespuestaQA` con `uso_tool_financiera`
- `app/dashboard.py`: badge condicional

### Out of Scope
- SQLite persistente / escritura
- LangGraph (loop manual basta)
- Múltiples tools (una sola cubre todo)
- Reemplazo de RAG

## Capabilities

### New
- `financial-data`: SQLite read-only sobre métricas. Auto-seed CSV. Consultas por sección/año/concepto.
- `tool-calling`: `@tool` que LLM invoca via `.bind_tools()`. Retorna JSON. Sistema trackea invocación.
- `qa-extended`: Q&A modificado que bindea tool y re-enruta tool → LLM para formateo.

### Modified
None.

## Approach

| Capa | Módulo | Función |
|------|--------|---------|
| SQLite | `db.py` | `consultar_metricas(seccion, anio, concepto)` con WHERE paramétrico |
| Tool | `tool.py` | `@tool` envolviendo consulta. Retorna JSON. LLM decide llamada |
| Q&A | `qa.py` | `bind_tools()` → 1er invoke → si `tool_calls`, ejecutar tool → 2do invoke |
| UI | `dashboard.py` | Badge condicional |

## Data Flow

Usuario → LLM con tool bindeada → LLM decide tool_call → SQL ejecuta → JSON → LLM formatea → `RespuestaQA(uso_tool=True)` → badge en UI

## Tool Contract

| Campo | Tipo | Descripción |
|-------|------|-------------|
| Input | `seccion?`, `anio?`, `concepto?` | Filtros opcionales |
| Output | `str` | JSON: `[{anio,seccion,concepto,valor_num,valor_raw,unidad,es_ratio}]` |

## Risks

| Riesgo | Prob. | Mitigación |
|--------|-------|------------|
| LLM no llama tool cuando debe | Media | Prompt engineering + fallback RAG |
| LLM llama tool cuando no debe | Baja | Tool barata (SQLite in-mem) |
| `bind_tools()` no soportado en Ollama | Media | Fallback: omitir binding |
| CSV cambia formato/ruta | Baja | Path hardcodeado + validación |

## Rollback Plan

1. `git revert` commits de módulos modificados
2. Eliminar `llm/financial/`
3. Sin cambios en `pyproject.toml`
4. `make test` para verificar

## Dependencies

- 0 nuevas dependencias PyPI (`sqlite3` stdlib)
- CSV en `data/estelar_reportes/metricas_financieras.csv`

## Success Criteria

- [ ] SQLite seedeado del CSV; `SELECT` correcto
- [ ] `consultar_metricas("EBITDA", 2024)` retorna row
- [ ] LLM llama tool en "¿EBITDA 2024?" — NO en "¿qué dice el resumen?"
- [ ] `uso_tool_financiera=True` cuando tool se invocó
- [ ] Dashboard muestra badge
- [ ] Tests existentes pasan
- [ ] 0 nuevas dependencias
