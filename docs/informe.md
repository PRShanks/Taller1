# Informe Técnico — Taller 1
## Aplicación de Técnicas Avanzadas de IA Generativa sobre Datos Financieros de Hoteles Estelar S.A.

---

## 1. Resumen del proyecto

Este proyecto implementa un sistema completo de análisis de información
empresarial que combina **web scraping**, **procesamiento con LLM mediante
LangChain**, **recuperación aumentada por embeddings (RAG)** y una
**interfaz web interactiva en Streamlit**.

La empresa seleccionada es **Hoteles Estelar S.A.** (NIT 890304099),
cuyos datos financieros 2024 fueron extraídos del reporte público
publicado en *Estrategia en Acción* (fuente: Supersociedades).

---

## 2. Arquitectura

```
┌────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   SCRAPER      │ ──▶ │  data_loader.py  │ ──▶ │ Texto consolidado   │
│  (Power BI)    │     │   (limpieza +    │     │  (.txt)             │
│                │     │    enriquec.)    │     │                     │
└────────────────┘     └──────────────────┘     └──────────┬──────────┘
                                                            │
                ┌───────────────────────────────────────────┼──────────────────┐
                ▼                                           ▼                  ▼
        ┌──────────────┐                          ┌──────────────┐    ┌──────────────┐
        │  RESUMEN     │                          │  FAQ         │    │  Q&A (RAG)   │
        │ (LangChain   │                          │ (LangChain   │    │ FAISS +      │
        │  + Claude)   │                          │  + Claude)   │    │ Claude       │
        └──────┬───────┘                          └──────┬───────┘    └──────┬───────┘
               │                                         │                   │
               └────────────────┬────────────────────────┴───────────────────┘
                                ▼
                       ┌──────────────────┐
                       │   STREAMLIT      │
                       │   Dashboard      │
                       └──────────────────┘
```

### Decisiones técnicas

| Componente | Tecnología | Justificación |
|---|---|---|
| Orquestación LLM | LangChain 0.3 | Estándar de la industria, abstrae prompts y cadenas. |
| Modelo de lenguaje | Claude Haiku 4.5 | Rápido, económico y suficientemente preciso para la tarea. |
| Embeddings | sentence-transformers (multilingüe) | Local, gratuito, calidad alta en español. |
| Vector store | FAISS | Persistencia local sencilla, sin dependencia de servicios externos. |
| Frontend | Streamlit | Bajo costo de desarrollo, ideal para prototipos de IA. |
| Gestión de secretos | python-dotenv | Mantiene API keys fuera del código fuente. |

---

## 3. Componentes implementados

### 3.1 Scraper (preexistente)
Ubicación: `scripts/extract_estelar_report.py`
Genera el archivo `data/estelar_reportes/HOTELES_ESTELAR_890304099.md`
con los indicadores financieros 2024.

### 3.2 Procesamiento de datos
`llm/data_loader.py` toma el `.md` crudo, lo limpia (quita marcadores
Markdown, transforma tablas en pares clave-valor) y lo enriquece con
contexto adicional (descripción de la empresa y glosario de indicadores
financieros). El resultado se guarda en `data/processed/estelar_consolidado.txt`.

### 3.3 Tarea 1 — Resumen ejecutivo
`llm/summarizer.py` genera un resumen estructurado en 4 secciones
(identificación, desempeño, apalancamiento, conclusión). Temperatura 0.3.

### 3.4 Tarea 2 — Generación de FAQ
`llm/faq_generator.py` produce N preguntas frecuentes con respuesta
basadas en el contexto. Cobertura temática variada y formato Markdown.
Temperatura 0.5 para diversidad.

### 3.5 Tarea 3 — Q&A con RAG
`llm/qa_chain.py` implementa el flujo completo:
1. División del contexto en chunks de 400 caracteres con overlap de 80.
2. Generación de embeddings con `paraphrase-multilingual-MiniLM-L12-v2`.
3. Indexación en FAISS y persistencia en disco.
4. Para cada pregunta: recuperación de los 4 chunks más similares y
   generación de respuesta con Claude (temperatura 0.0).
5. Guardrail anti-alucinación: respuesta literal cuando no hay información.

### 3.6 Dashboard
`app/dashboard.py` expone las tres funcionalidades en tabs separados,
con caché de resultados para evitar llamadas repetidas al modelo.

---

## 4. Prompt Engineering

El detalle del proceso iterativo está en `docs/prompts_experimentacion.md`.
En síntesis, los prompts finales aplican:

- Asignación de **rol experto**.
- **Reglas numeradas** explícitas.
- Cláusulas **anti-alucinación** literales.
- **Formato de salida** estructurado.
- **Temperatura** ajustada por tarea.

---

## 5. Resultados y evaluación cualitativa

| Criterio | Resultado |
|---|---|
| Resumen factualmente correcto | ✅ Cifras coinciden con el reporte fuente. |
| FAQ con respuestas verificables | ✅ Todas las respuestas se trazan al contexto. |
| Q&A maneja preguntas fuera de alcance | ✅ Responde literalmente *"No tengo esa información..."* |
| Tiempo de respuesta promedio | ~2-3 s (Claude Haiku 4.5) |
| Costo aproximado por consulta | < USD 0.001 |

---

## 6. Limitaciones y trabajo futuro

1. **Volumen de datos pequeño:** el reporte original tiene pocos campos.
   Una versión productiva debería integrar múltiples años y comparativos
   sectoriales para enriquecer las respuestas.
2. **Sin evaluación cuantitativa:** sería ideal armar un set de preguntas
   con respuestas de referencia y medir precisión y *faithfulness*
   (con frameworks tipo RAGAS).
3. **Embeddings podrían afinarse:** usar un modelo financiero específico
   en español mejoraría la recuperación.
4. **Trazabilidad de fuentes:** actualmente se muestran los chunks
   recuperados, pero no hay highlighting de la oración exacta.

---

## 7. Cómo ejecutar el proyecto

Ver `README.md`.

---

## 8. Repositorio

Código fuente disponible en GitHub: *(agregar aquí la URL del repo)*.
