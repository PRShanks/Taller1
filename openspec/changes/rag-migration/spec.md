# Spec: RAG Migration (BM25 to Supabase pgvector)

> Change 1 of 3 — replace BM25 lexical search with semantic RAG via Supabase pgvector.
>
> **Nota**: La ingesta de documentos, el schema SQL de Supabase y la elección del modelo de
> embeddings son responsabilidad de otros equipos. Este change construye la infraestructura
> del lado del consumo (retriever, embedding factory, wrapper de vector store) y deja todo
> preparado para que cuando lleguen los accesos, funcione sin cambios de código.
>
> **Importante**: Sin Supabase no hay LLM call. `responder_pregunta()` devuelve un mensaje
> plano indicando que RAG no está disponible. No se carga texto completo al modelo.

---

## 1. Requirements

### 1.1 Functional

| ID | Domain | Requirement | RFC 2119 |
| --- | --- | --- | --- |
| R01 | embeddings | `crear_embeddings()` returns a LangChain `Embeddings` instance configured by `EMBEDDING_PROVIDER` env var (default: `ollama`). Provider `ollama` defaults to `nomic-embed-text`. Provider `openai` uses `text-embedding-3-small`. | MUST |
| R02 | embeddings | Missing `OPENAI_API_KEY` when `EMBEDDING_PROVIDER=openai` raises `OSError` with clear message. | MUST |
| R03 | embeddings | Unknown `EMBEDDING_PROVIDER` value raises `ValueError` listing valid options. | MUST |
| R04 | vector-store | `crear_vector_store()` returns a SupabaseVectorStore-compatible instance. Missing `SUPABASE_URL` or `SUPABASE_SERVICE_KEY` raises `OSError` with actionable message. | MUST |
| R05 | vector-store | Assumes `documents` table with columns `id`, `content`, `metadata` (JSONB), `embedding` (VECTOR) and an `rpc("match_documents", ...)` function exists (external team). | SHOULD |
| R06 | qa-chain | `responder_pregunta()` removes `top_k` and `contexto_completo` params. When Supabase is configured, uses semantic retrieval + LLM. When not configured, returns plain-text message ("RAG no disponible") — NO LLM call, NO `cargar_contexto()`. | MUST |
| R07 | qa-chain | `_construir_bm25()` and `_recuperar_chunks()` removed. No `rank_bm25` imports. | MUST |
| R08 | qa-chain | Return dict format (`respuesta`, `encontrado`, `confianza`, `nota`, `fuentes`) stays unchanged. | MUST |
| R09 | dashboard | `usar_completo` toggle removed. BM25 `top_k` slider removed. No BM25 references in sidebar. | MUST |
| R10 | data-loader | Stale hardcoded filenames (`HOTELES_ESTELAR_890304099.md`, `hoteles_estelar.md`) replaced with glob pattern on `data/estelar_reportes/*.md`. | MUST |
| R11 | data-loader | `cargar_contexto()` remains unchanged for backward compat with summarizer/FAQ. | MUST |

### 1.2 Non-Functional

| ID | Requirement | RFC 2119 |
| --- | --- | --- |
| NF01 | No-Supabase mode: if Supabase is unavailable (missing creds), `responder_pregunta()` returns a plain-text message explaining RAG is not configured — NO LLM call, NO `cargar_contexto()`, no crash, no traceback. | MUST |
| NF02 | Embedding provider is swappable via `EMBEDDING_PROVIDER` env var without code changes. | MUST |
| NF03 | All new public functions have Google-style docstrings with params and return types. | MUST |
| NF04 | `rank-bm25` removed from `pyproject.toml` and `uv lock` regenerated. | MUST |
| NF05 | `pyproject.toml` gains `langchain-community`, `langchain-openai`, `supabase`, `langchain-text-splitters`. | MUST |

---

## 2. Test Scenarios

### Scenario 1: Embedding factory works standalone

```bash
uv run python -c "
from llm.embeddings import crear_embeddings
emb = crear_embeddings()
print(type(emb).__module__)
"
```

- **GIVEN** no `EMBEDDING_PROVIDER` set (defaults to ollama)
- **WHEN** `crear_embeddings()` is called
- **THEN** it returns an `OllamaEmbeddings` instance without error
- **AND** the module path contains `langchain_ollama`

### Scenario 2: Embedding factory fails gracefully with missing API key

```bash
EMBEDDING_PROVIDER=openai uv run python -c "
from llm.embeddings import crear_embeddings
try:
    crear_embeddings()
    print('NO_ERROR')
except OSError as e:
    print(f'EXPECTED: {e}')
"
```

- **GIVEN** `EMBEDDING_PROVIDER=openai` and no `OPENAI_API_KEY`
- **WHEN** `crear_embeddings()` is called
- **THEN** it raises `OSError` with message mentioning `OPENAI_API_KEY`

### Scenario 3: Vector store fails gracefully with missing credentials

```bash
uv run python -c "
from llm.vector_store import crear_vector_store
try:
    crear_vector_store()
    print('NO_ERROR')
except OSError as e:
    print(f'EXPECTED: {e}')
"
```

- **GIVEN** no `SUPABASE_URL` in environment
- **WHEN** `crear_vector_store()` is called
- **THEN** it raises `OSError` with message mentioning `SUPABASE_URL`

### Scenario 4: QA chain no longer has BM25 params

```bash
uv run python -c "
from llm.qa_chain import responder_pregunta
import inspect
sig = inspect.signature(responder_pregunta)
params = list(sig.parameters.keys())
print(f'Params: {params}')
assert 'top_k' not in params, 'top_k should be removed'
assert 'contexto_completo' not in params, 'contexto_completo should be removed'
print('OK: BM25 params removed')
"
```

- **GIVEN** the modified `responder_pregunta()` signature
- **WHEN** inspecting its parameters
- **THEN** `top_k` and `contexto_completo` are absent

### Scenario 5: rank-bm25 removed from dependencies

```bash
grep -r "rank-bm25" pyproject.toml
```

- **GIVEN** the modified `pyproject.toml`
- **WHEN** searching for `rank-bm25`
- **THEN** no matches found

### Scenario 6: Dashboard loads without BM25 controls

- **GIVEN** the modified `app/dashboard.py`
- **WHEN** the user inspects the sidebar
- **THEN** no "Contexto completo" toggle appears
- **AND** no BM25 `top_k` slider appears

### Scenario 7: data_loader globs actual files (not stale names)

- **GIVEN** the modified `data_loader.py`
- **WHEN** `cargar_contexto()` runs
- **THEN** it finds `.md` files via glob (actual files, not stale names)

### Scenario 8: QA without Supabase returns plain message

```bash
uv run python -c "
from llm.qa_chain import responder_pregunta
result = responder_pregunta('¿Cuáles fueron los ingresos?')
print(f'Respuesta: {result[\"respuesta\"][:80]}...')
print(f'Encontrado: {result[\"encontrado\"]}')
assert 'no disponible' in result['respuesta'].lower()
assert result['encontrado'] is False
print('OK: fallback message works')
"
```

- **GIVEN** no `SUPABASE_URL` set
- **WHEN** `responder_pregunta()` is called
- **THEN** it returns a dict with `encontrado: False`
- **AND** `respuesta` contains text like "no disponible" or "no configurado"
- **AND** no LLM call was made

---

## 3. Acceptance Criteria

- [ ] `rank-bm25` removed from `pyproject.toml`; `uv lock` regenerated
- [ ] `_construir_bm25()`, `_recuperar_chunks()`, `BM25Okapi` import removed from `qa_chain.py`
- [ ] `responder_pregunta()` no longer has `top_k` or `contexto_completo` parameters
- [ ] `llm/embeddings.py` exists with `crear_embeddings()` — works with both `ollama` and `openai`
- [ ] `llm/vector_store.py` exists with `crear_vector_store()` — fails gracefully if creds missing
- [ ] `dashboard.py` — BM25 controls removed
- [ ] `data_loader.py` — stale file refs replaced with glob pattern
- [ ] `.env.example` updated with `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `EMBEDDING_PROVIDER`, `OPENAI_API_KEY`
- [ ] `Makefile` has `ingest` target (placeholder for external team)
- [ ] Sin Supabase: `responder_pregunta()` devuelve mensaje plano "no disponible", sin LLM, sin `cargar_contexto()`
- [ ] All new modules have Google-style docstrings
- [ ] Scenario 1 through Scenario 8 pass

---

## 4. Minimal Scope Boundaries

### In Scope

- `llm/embeddings.py` — embedding factory with Ollama (default) and OpenAI support
- `llm/vector_store.py` — Supabase client wrapper (thin, graceful error, defines contract for external team)
- `llm/qa_chain.py` — BM25 removal, dual-path (Supabase → LLM, no Supabase → mensaje plano)
- `llm/data_loader.py` — fix stale filenames with glob, keep `cargar_contexto()` backward compat
- `app/dashboard.py` — remove BM25 UI controls, simplify sidebar
- `pyproject.toml` — -`rank-bm25`, +`langchain-community`, +`langchain-openai`, +`supabase`, +`langchain-text-splitters`
- `Makefile` — +`ingest` target (placeholder for external team)
- `.env.example` — +`SUPABASE_URL`, +`SUPABASE_SERVICE_KEY`, +`EMBEDDING_PROVIDER`, +`OPENAI_API_KEY`
- Tests for new modules (embedding factory, vector_store graceful error, no-Supabase message behavior)

### Out of Scope

- Document ingestion pipeline (external team)
- SQL migration for pgvector (external team delivers schema)
- Actual Supabase database provisioning (external team)
- Embedding model selection (external team)
- Agent architecture (`create_agent`, middleware) — change 2
- Postgres checkpointer for session memory — change 3
- Summarizer and FAQ as agent tools — change 2
- `system_prompt.txt` refactoring — change 2
- Prompt refactoring in `prompts.py` — change 2
- Performance optimization or embedding caching
- Hybrid search (BM25 + vector) — deferred
- `scripts/consolidar_estelar.py` removal or modification
