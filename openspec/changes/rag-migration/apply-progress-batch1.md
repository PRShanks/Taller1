# Apply Progress — Batch 1

**Change**: rag-migration
**Mode**: Standard
**Batch**: 1 of several

## Completed Tasks

- [x] **T1 / 1.1** — `llm/embeddings.py` — `crear_embeddings()` factory with Ollama/OpenAI support
- [x] **T3 / 2.1** — `llm/data_loader.py` — Replaced stale hardcoded paths with `REPORTES_DIR.glob("*.md")`
- [x] **T6 / 3.1** — `pyproject.toml` — Removed rank-bm25, added new deps, ran `uv lock`
- [x] **T7 / 3.2** — `.env.example` — Added SUPABASE_URL, SUPABASE_SERVICE_KEY, EMBEDDING_PROVIDER, OPENAI_API_KEY
- [x] **T8 / 3.3** — `Makefile` — Added `ingest` and `reindex` placeholder targets + `.PHONY` entries

## Files Changed

| File | Action | What Was Done |
|------|--------|---------------|
| `llm/embeddings.py` | Created | New factory module for embeddings (OllamaEmbeddings/OpenAIEmbeddings) |
| `llm/data_loader.py` | Modified | Replaced hardcoded paths with glob-based approach, dynamic section headers |
| `pyproject.toml` | Modified | Removed rank-bm25, added langchain-community, langchain-openai, supabase, langchain-text-splitters |
| `.env.example` | Modified | Added RAG-related env vars |
| `Makefile` | Modified | Added ingest/reindex targets + .PHONY entries |
| `uv.lock` | Modified | Regenerated via `uv lock` |

## Remaining Tasks

- [ ] **T2 / 1.2** — `llm/vector_store.py` — `crear_vector_store()` factory
- [ ] **T4 / 2.2** — `llm/qa_chain.py` — Remove BM25, integrate vector store
- [ ] **T5 / 2.3** — `app/dashboard.py` — Remove BM25-related UI controls
- [ ] **T9 / 4.1-4.3** — Tests
- [ ] **T10 / 5.1-5.4** — Final verification

## Status

5/13 tasks complete. Ready for next batch.
