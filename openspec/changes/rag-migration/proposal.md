# Proposal: RAG Migration (BM25 → Supabase pgvector)

## Intent

Replace BM25 lexical search with semantic RAG backed by Supabase pgvector. BM25 fails on conceptual queries
(e.g., "¿cómo le fue a la empresa?" won't match "desempeño financiero"). Semantic embeddings enable meaning-based retrieval
without exact keyword match. This is change 1 of 3 — it establishes the retrieval backbone only.

## Scope

### In Scope
- `llm/embeddings.py` — embedding factory (swappable provider via `EMBEDDING_PROVIDER` env var)
- `llm/vector_store.py` — Supabase pgvector client (connects, fails gracefully if creds missing)
- `llm/retriever.py` — semantic similarity search wrapping the vector store
- `llm/data_loader.py` — refactored: chunk + embed + upsert pipeline; fix stale file references
- `llm/qa_chain.py` — remove `_construir_bm25()`, `_recuperar_chunks()`, `rank_bm25`; inject retriever
- `app/dashboard.py` — remove `usar_completo` toggle and `top_k` from Q&A flow
- `pyproject.toml` — remove `rank-bm25`; add `langchain-community`, `langchain-openai`, `supabase`, `langchain-text-splitters`
- `Makefile` — add `ingest` and `reindex` targets
- `.env.example` — add `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `EMBEDDING_PROVIDER`, embedding API keys

### Out of Scope
- Supabase DB/table/migration creation (external team)
- Embedding model selection (external team — we provide the swappable factory)
- Summarizer/FAQ refactoring into agent tools (change 2)
- InMemoryStore → persistent memory migration (change 3)
- Prompt refactoring or `system_prompt.txt` changes

## Capabilities

### New Capabilities
- `embeddings`: Embedding model factory reading `EMBEDDING_PROVIDER` env var. Creates any LangChain `Embeddings`.
  Falls back to Ollama (`nomic-embed-text`) when no provider set. Fails with clear message if provider configured but credentials missing.
- `vector-store`: Supabase client wrapper. Reads `SUPABASE_URL` + `SUPABASE_SERVICE_KEY`. Provides `add_documents()`
  and `similarity_search()`. Raises `OSError` with actionable message when env vars absent. Assumes external `documents` table
  with `id`, `content`, `metadata`, `embedding` columns.
- `document-ingestion`: Loads raw `.md` via glob (fixing stale hardcoded filenames), splits with `RecursiveCharacterTextSplitter`
  (chunk=1000, overlap=200), embeds, upserts to Supabase. Keeps `cargar_contexto()` for backward compat (full-text, no RAG).
- `semantic-qa`: Retriever wrapping `vector_store.similarity_search()`. `responder_pregunta()` loses `contexto_completo`
  and `top_k` params. Context now always comes from semantic retrieval (k=5 default, configurable via retriever).

### Modified Capabilities
None — no existing specs in `openspec/specs/`.

## Approach

**Embedding factory** reads `EMBEDDING_PROVIDER` (openai, ollama) at init. Each provider maps to its LangChain integration
(`langchain_openai.OpenAIEmbeddings`, `langchain_ollama.OllamaEmbeddings`). Missing API key → clear `OSError`. No provider set →
defaults to Ollama local `nomic-embed-text` with warning.

**Supabase client** uses `supabase-py` (not `langchain_community.vectorstores.SupabaseVectorStore` — avoids LangChain's
heavy wrapper). Direct `supabase.Client` calls for `rpc("match_documents", ...)`. This keeps us flexible when the external
team provides the actual schema.

**Document ingestion**: `data_loader.py` gains `indexar_documentos(force=False)`. On first run (or `force=True`),
loads all `.md` → splits → embeds → upserts via `vector_store`. Idempotent: skips if docs already exist (checks count).

**Q&A**: `responder_pregunta(pregunta, llm, historial)` now calls `retriever.get_relevant_documents(pregunta)`,
joins chunks, passes to LLM. `_parsear_respuesta()` stays.

## Affected Files

| File | Impact | Description |
|------|--------|-------------|
| `llm/embeddings.py` | New | Embedding factory + `get_embeddings()` |
| `llm/vector_store.py` | New | Supabase client + `add_documents()` / `similarity_search()` |
| `llm/retriever.py` | New | Semantic retriever wrapping vector store |
| `llm/data_loader.py` | Modified | Glob-based loading, chunk+embed+store pipeline, keep `cargar_contexto()` |
| `llm/qa_chain.py` | Modified | Remove BM25 functions, inject retriever, simplify `responder_pregunta()` |
| `app/dashboard.py` | Modified | Remove `usar_completo` toggle, remove `top_k` slider from Q&A |
| `pyproject.toml` | Modified | -`rank-bm25`, +`langchain-community`, +`langchain-openai`, +`supabase`, +`langchain-text-splitters` |
| `Makefile` | Modified | +`ingest`, +`reindex` targets |
| `.env.example` | Modified | +`SUPABASE_URL`, +`SUPABASE_SERVICE_KEY`, +`EMBEDDING_PROVIDER`, +`OPENAI_API_KEY` |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Supabase schema mismatch when external team delivers | Med | Decouple via `vector_store.py` abstractions; align on column names early |
| Embedding dimension unknown until provider chosen | Med | Read dimension from model at runtime; documented in `.env.example` |
| `langchain_community` SupabaseVectorStore API drift | Med | Use `supabase-py` directly instead of LangChain wrappers |
| Ingestion runtime: ~80KB docs + embedding API call | Low | Cache embeddings; `make reindex` for reprocessing |
| Zero existing tests for retrieval pipeline | High | Write integration tests with mocked Supabase + embeddings |

## Rollback Plan

1. Revert `qa_chain.py` to BM25 version from git (`git checkout HEAD~1 -- llm/qa_chain.py`)
2. Remove new files: `llm/embeddings.py`, `llm/vector_store.py`, `llm/retriever.py`
3. Revert `pyproject.toml` and run `uv lock`
4. Revert `dashboard.py`, `data_loader.py`, `Makefile`, `.env.example`
5. `make clean-data && make run-data` to regenerate `.txt`

## Dependencies

- External team delivers Supabase URL + service key (blocking for runtime, not for code)
- External team selects embedding provider (blocking for final config, not for factory code)
- `supabase-py` package from PyPI (not langchain-community's vectorstore wrapper)

## Success Criteria

- [ ] `make ingest` loads 4 `.md` files, chunks, embeds, and stores in Supabase without errors
- [ ] Q&A returns relevant answers using semantic search (manual smoke test with conceptual queries)
- [ ] Missing `SUPABASE_URL` produces clear `OSError` message, not a crash
- [ ] `cargar_contexto()` still works for backward compat with summarizer/FAQ
- [ ] All existing Makefile targets (`dev`, `lint`, `test`, etc.) continue working
- [ ] `rank-bm25` removed from `pyproject.toml` and no import references remain
