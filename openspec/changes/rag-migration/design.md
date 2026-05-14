# Design: RAG Migration (BM25 → Supabase pgvector)

## Technical Approach

Replace BM25 lexical search in `qa_chain.py` with a dual-path strategy: when Supabase credentials are present, use `SupabaseVectorStore` for semantic retrieval; when absent, respond with a plain-text message indicating RAG is not available (NO LLM call, NO full-text fallback). Embedding provider defaults to Ollama (`nomic-embed-text` for local testing) and is swappable via `EMBEDDING_PROVIDER`. New modules (`embeddings.py`, `vector_store.py`) are thin factories — no ingestion logic, no schema management, no hardcoded embedding dimensions. The embedding dimension is determined at runtime by whatever model is configured.

## Architecture Decisions

| Decision | Options | Choice | Rationale |
| --- | --- | --- | --- |
| Embedding default | OpenAI / Ollama | **Ollama `nomic-embed-text`** | Zero config for local testing; matches existing Ollama LLM support. Ready to switch when external team chooses the final model. |
| Embedding dimension | Hardcode / Dynamic | **Dynamic (runtime)** | External team chooses the model. Dimension is determined by whatever `Embeddings` instance is configured. No hardcoded 1536 or any other value. |
| Vector store client | raw `supabase-py` / `SupabaseVectorStore` | **`SupabaseVectorStore`** | User explicitly confirmed it. Simplifies integration — LangChain handles RPC calls and result marshalling. |
| Fallback behavior | Crash / Full text + LLM / Plain message | **Plain message (NO LLM, NO full text)** | User explicitly: "sin Supabase solo responde en texto plano sin conectarte al modelo nada de cargar textos completos al modelo." |
| Ingestion pipeline | Build now / Placeholder | **Placeholder `make ingest`** | External team handles ingestion. We only build the consumer side. |

## Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    responder_pregunta()                       │
│                                                               │
│   ┌─ Supabase configured? ──────────────────────────────┐    │
│   │ YES: crear_vector_store(crear_embeddings())         │    │
│   │      → similarity_search(query)                     │    │
│   │      → contexto + pregunta → LLM → _parsear_respuesta│    │
│   │      → { respuesta, encontrado, confianza, nota }   │    │
│   │                                                      │    │
│   │ NO:  return {                                       │    │
│   │        respuesta: "Sistema RAG no disponible..."     │    │
│   │        encontrado: false,                            │    │
│   │        confianza: "baja",                            │    │
│   │        nota: "Configure SUPABASE_URL..."             │    │
│   │      }                                               │    │
│   └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘

dashboard.py ←→ responder_pregunta()
                    │
                    ├── embeddings.py → crear_embeddings()
                    │                       └── OllamaEmbeddings (default, testing)
                    │                       └── cualquier LangChain Embeddings
                    │                           (cuando el equipo elija el modelo)
                    │
                    └── vector_store.py → crear_vector_store(embeddings)
                                            └── SupabaseVectorStore
                                            └── None → mensaje plano
```

## File Changes

| File | Action | Description |
| --- | --- | --- |
| `llm/embeddings.py` | Create | Factory: `crear_embeddings() → Embeddings`. Reads `EMBEDDING_PROVIDER`. Default: Ollama `nomic-embed-text`. Diseñado para soportar CUALQUIER `Embeddings` de LangChain (OpenAI, HuggingFace, etc.). |
| `llm/vector_store.py` | Create | Factory: `crear_vector_store(embeddings) → SupabaseVectorStore \| None`. No hardcodea dimensión — la hereda del embedding model configurado. `None` si falta `SUPABASE_URL`. |
| `llm/qa_chain.py` | Modify | Remove BM25 functions (`_construir_bm25`, `_recuperar_chunks`, `BM25Okapi`). Remove `top_k`/`contexto_completo` params. New logic: try vector store → si no, mensaje plano sin LLM. |
| `llm/data_loader.py` | Modify | Replace hardcoded filenames with `glob("data/estelar_reportes/*.md")`. Keep `cargar_contexto()` for potential external use. |
| `app/dashboard.py` | Modify | Remove `usar_completo` toggle, `top_k` slider, BM25 references in sidebar and question handling. |
| `pyproject.toml` | Modify | `-rank-bm25`, `+langchain-community`, `+langchain-openai`, `+supabase`. |
| `.env.example` | Modify | Add `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `EMBEDDING_PROVIDER`, `OPENAI_API_KEY`. |
| `Makefile` | Modify | Add `ingest` target as echo placeholder. |

## Key Design Detail: How the No-Supabase Path Works

When `SUPABASE_URL` is NOT set, `responder_pregunta()` does:

1. `crear_vector_store()` returns `None`
2. Detects `None` → returns a dict **inmediatamente**:
   ```python
   {
       "respuesta": "El sistema de búsqueda semántica (RAG) no está configurado. "
                    "Para activarlo, configure SUPABASE_URL y SUPABASE_SERVICE_KEY "
                    "en el archivo .env y asegúrese de que el equipo de datos haya "
                    "ejecutado la ingesta de documentos en la base de datos vectorial.",
       "encontrado": False,
       "confianza": "baja",
       "nota": "Modo fallback: sin conexión a base de datos vectorial.",
   }
   ```
3. **NO** se llama a `cargar_contexto()`, **NO** se instancia un LLM, **NO** hay llamada a modelo alguno.

Esto es intencional: el usuario no quiere que el sistema funcione "a medias" sin Supabase. Quiere que falle explícitamente para que sea claro que RAG no está operativo.

## Key Design Detail: Embedding Dimension Agnostic

La dimensión del embedding **no se hardcodea en ningún lado**:

- `crear_embeddings()` devuelve cualquier `Embeddings` de LangChain
- `SupabaseVectorStore` obtiene la dimensión del embedding model en tiempo real
- La tabla `documents` en Supabase y la función `match_documents` deben tener `VECTOR(n)` donde `n` coincida con la dimensión del modelo que el otro equipo elija — eso es **responsabilidad del equipo externo**
- Nuestro código funciona con cualquier dimensión sin cambios

Esto significa: cuando el equipo externo decida "usamos OpenAI text-embedding-3-small" (1536d) o "usamos multilingual-e5-large" (1024d), SOLO cambiamos la env var `EMBEDDING_PROVIDER`.

## Interfaces

```python
# llm/embeddings.py
def crear_embeddings(
    proveedor: str | None = None,
    modelo: str | None = None,
) -> Embeddings:
    """Default proveedor='ollama' → OllamaEmbeddings(nomic-embed-text).
       proveedor='openai' → OpenAIEmbeddings(text-embedding-3-small).
       Missing API key → OSError. Unknown provider → ValueError.
       Fácilmente extensible a cualquier Embeddings de LangChain.
    """

# llm/vector_store.py
def crear_vector_store(
    embeddings: Embeddings | None = None,
) -> SupabaseVectorStore | None:
    """Returns None cuando SUPABASE_URL no está configurada.
       Returns SupabaseVectorStore cuando hay credenciales.
       OSError si URL está seteada pero SUPABASE_SERVICE_KEY no.
       No hardcodea dimensión de embedding.
    """

# llm/qa_chain.py — nueva firma
def responder_pregunta(
    pregunta: str,
    llm: BaseChatModel | None = None,
    historial: list[BaseMessage] | None = None,
) -> dict:
    """Sin top_k ni contexto_completo.
       Interno: si hay Supabase → retriever semántico + LLM.
       Si no → mensaje plano sin LLM ni cargar_contexto().
       Return dict se mantiene: respuesta, encontrado, confianza, nota, fuentes.
    """

# NOTA: el LLM solo se usa en el path con Supabase.
# Sin Supabase, no se instancia LLM, no se llama cargar_contexto().
```

## Testing Strategy

| Layer | What to Test | Approach |
| --- | --- | --- |
| Unit | `crear_embeddings()` con Ollama default | Assert devuelve `OllamaEmbeddings` sin error |
| Unit | `crear_embeddings()` missing OpenAI key | Assert `OSError` con mensaje claro |
| Unit | `crear_vector_store()` sin SUPABASE_URL | Assert returns `None` |
| Unit | `crear_vector_store()` URL sin key | Assert `OSError` |
| Unit | `responder_pregunta()` signature | Assert `top_k` y `contexto_completo` ausentes via `inspect.signature` |
| Integration | Sin Supabase → mensaje plano | Assert respuesta sin LLM, con "no disponible" en el texto |
| Manual | Dashboard carga | No controles BM25 visibles en sidebar |

## Migration / Rollout

1. **Create** `embeddings.py` y `vector_store.py` — archivos nuevos, sin cambios a código existente
2. **Fix** `data_loader.py` — reemplazar nombres hardcodeados por glob
3. **Refactor** `qa_chain.py` — remover BM25, agregar dual-path (Supabase → LLM, no Supabase → mensaje plano)
4. **Update** `dashboard.py` — remover controles BM25
5. **Update** `pyproject.toml`, `.env.example`, `Makefile`
6. **Write** tests
7. **Verify**: todos los escenarios de spec pasan

Rollback: `git checkout HEAD~1 -- llm/qa_chain.py llm/data_loader.py app/dashboard.py pyproject.toml` + borrar archivos nuevos + `uv lock`.

## Open Questions

- La dimensión del embedding queda a cargo del equipo externo — nuestro código se adapta dinámicamente
- El schema de Supabase (`documents` table, `match_documents` RPC) también es responsabilidad externa
