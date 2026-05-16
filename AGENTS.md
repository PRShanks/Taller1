# Taller1 — Hoteles Estelar Chat Assistant

> Chatbot corporativo para Hoteles Estelar S.A. con Q&A, resumen ejecutivo y generación de FAQ basados en reportes financieros.

## Stack Técnico

| Componente | Tecnología |
| --- | --- |
| Lenguaje | Python 3.12 (obligatorio — FAISS no soporta 3.13+) |
| Gestor de paquetes | uv (NO pip, NO poetry) |
| Framework LLM | LangChain (langchain-core, langchain-anthropic, langchain-ollama) |
| Proveedores LLM | Anthropic Claude (API) y Ollama (local) |
| Recuperación | Supabase pgvector con OpenAI/Ollama embeddings |
| UI | Streamlit |
| Scraping | Playwright + Requests (scripts separados) |
| Variables de entorno | python-dotenv (.env, NUNCA en el repo) |

## Arquitectura

```text
Taller1/
├── app/
│   └── dashboard.py              # UI Streamlit (orquestación)
├── llm/
│   ├── __init__.py
│   ├── clients/
│   │   ├── factory.py            # Factory pattern para crear LLMs
│   │   └── memory.py             # Memoria de sesión (SqliteStore persistente)
│   ├── core/
│   │   ├── qa.py                 # Q&A con RAG + tool-calling loop
│   │   ├── faq_generator.py      # Generación de FAQ
│   │   └── summarizer.py         # Resumen ejecutivo
│   ├── financial/
│   │   ├── db.py                 # SQLite con auto-seed desde CSV
│   │   └── tool.py               # @tool query_financiero
│   ├── prompts/
│   │   └── qa.py                 # Prompts y carga del system prompt
│   ├── rag/
│   │   ├── embeddings.py         # Factory de embeddings (OpenAI/Ollama)
│   │   ├── sanitizer.py          # Anti-inyección para contexto RAG
│   │   └── vector_store.py       # SupabaseVectorStore propio
│   ├── models.py                 # Modelos Pydantic (RespuestaQA)
│   └── data_loader.py            # Carga y consolidación de .md a .txt
├── scripts/
│   ├── consolidar_estelar.py     # Consolida .md en .txt
│   ├── extract_estelar_report.py # Extracción de Power BI
│   ├── extract_hotelesestelar_web.py
│   └── capture_analisis_individual.py
├── data/
│   ├── estelar_reportes/         # Datos crudos (.md + .csv)
│   └── processed/                # Datos consolidados (.txt + .db autogenerados)
├── system_prompt.md              # System prompt externo (editable sin tocar código)
├── main.py                       # Entry point genérico
├── pyproject.toml                # Dependencias y metadata del proyecto
└── Makefile                      # Automatización de tareas
```

### Principios de Diseño

- **Alta cohesión**: cada módulo tiene UNA responsabilidad clara.
  - `factory.py` → crear LLMs
  - `data_loader.py` → cargar datos
  - `prompts/qa.py` → prompts y carga del system prompt
  - `core/qa.py` → lógica de Q&A con RAG + tool-calling loop
  - `summarizer.py` → lógica de resumen
  - `faq_generator.py` → lógica de FAQ
- **Bajo acoplamiento**: inyección de dependencias (`llm=None` con default via factory).
  - Las funciones del dominio reciben `llm: BaseChatModel | None` en vez de importar el LLM globalmente.
  - Los prompts se inyectan desde `prompts.py`, no están hardcodeados en la lógica.
  - La memoria se inyecta: `historial: list[BaseMessage] | None` permite Q&A con o sin contexto previo.
- **Separación de capas**: UI (`app/`) → Dominio (`llm/`) → Datos (`data/`). Nunca cruzar capas saltando niveles.

## Memoria de Sesión

El módulo `llm/clients/memory.py` gestiona la memoria de conversación usando `SqliteStore` de LangGraph (persistente en disco).

Arquitectura de namespaces:
- **Historial**: `("sessions", session_id, "messages")` — mensajes de la conversación
- **Datos de usuario**: `("users", user_id, "profile")` — preferencias y contexto personalizado

Flujo actual:
1. `SessionMemory` se crea como singleton en Streamlit via `@st.cache_resource`
2. Cada sesión de Streamlit tiene un `session_id` único
3. Se guarda cada mensaje (humano + AI) en el store SQLite
4. Al hacer una pregunta, se recupera el historial como `list[BaseMessage]` y se pasa al LLM via `_build_mensajes_base()`
5. El botón "Limpiar historial" en el sidebar elimina los mensajes de la sesión

Objetivo futuro:
- Reemplazar `SqliteStore` por `PostgresStore` para sesiones distribuidas
- La interfaz `SessionMemory` se mantiene, solo se cambia el store subyacente

## Reglas Obligatorias

### Docstrings

TODA función, clase y módulo DEBE tener docstring:

```python
"""nombre_modulo.py
-------------------
Descripción breve del módulo: qué hace y para qué.
"""


def funcion_ejemplo(parametro: str, otro: int = 5) -> dict:
    """Descripción breve de qué hace la función.

    Parámetros:
        parametro: descripción del parámetro
        otro: descripción del valor por defecto

    Devuelve:
        dict con claves 'respuesta' y 'fuentes'
    """
```

- Módulos: docstring al inicio con nombre, separador y descripción.
- Funciones públicas: descripción, parámetros, tipo de retorno.
- Funciones privadas (`_prefijo`): descripción breve al menos.

### pyproject.toml

- Cuando se agregue una dependencia nueva, ACTUALIZAR `pyproject.toml` y luego correr `uv lock`.
- NUNCA instalar paquetes con `pip install` directo. Siempre usar `uv add <paquete>`.
- Verificar que la versión de Python sea `>=3.12` en `requires-python`.
- Mantener la sección `[project]` con nombre, versión y descripción descriptivos.

### Imports

Orden de imports (separados por línea en blanco):

```python
# 1. Standard library
import os
import re
from pathlib import Path

# 2. Third-party
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

# 3. Local
from llm.factory import crear_llm
from llm.prompts import PROMPT_QA
```

### Tipado

- Usar type hints en todas las firmas de funciones públicas.
- Preferir `str | None` sobre `Optional[str]`.
- Preferir `list[str]` sobre `List[str]`.
- Los módulos privados (`_prefijo`) pueden ser más laxos.

## Comandos UV

```bash
# Crear entorno virtual
uv venv --python 3.12

# Activar entorno (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Instalar dependencias desde pyproject.toml
uv sync

# Agregar una dependencia
uv add <paquete>

# Agregar dependencia de desarrollo
uv add --dev <paquete>

# Ejecutar un script del proyecto
uv run python -m llm.qa_chain

# Ejecutar Streamlit
uv run streamlit run app/dashboard.py

# Bloquear dependencias
uv lock
```

## Makefile Targets

Usar `make <target>` para tareas comunes. Ver `Makefile` para el listado completo.

## Documentación Reciente

- Cuando se consulte documentación de librerías (LangChain, Streamlit, Ollama), SIEMPRE usar la versión más reciente disponible.
- Si hay dudas sobre una API, verificar con Context7 o la documentación oficial antes de asumir comportamiento.
- Los breaking changes de LangChain son frecuentes: siempre verificar la versión instalada en `pyproject.toml`.

## Testing

- Los tests van en `tests/` reflejando la estructura de `llm/`.
- Usar `pytest` como runner.
- Cada módulo nuevo DEBE tener al menos un test de integración básica.
- Mockear los LLMs en tests unitarios (no llamar APIs reales en CI).

## Agregar una Nueva Capacidad

1. Crear el módulo en `llm/` con alta cohesión.
2. Definir el prompt en `llm/prompts.py`.
3. Inyectar el LLM via `factory.py` (parámetro `llm=None` con default).
4. Agregar docstrings completos.
5. Actualizar `pyproject.toml` si hay nuevas dependencias.
6. Agregar target en el `Makefile` si aplica.
7. Integrar en `app/dashboard.py` si requiere UI.

## Seguridad

- NUNCA commitear `.env` o API keys.
- NUNCA hardcodear secrets en el código.
- Siempre usar `os.getenv()` o `load_dotenv()` para credenciales.
- El `.gitignore` ya excluye `.env`, `.venv/`, `data/vector_store/`.
