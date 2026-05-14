# Apply Progress — Batch 2

**Change**: rag-migration
**Mode**: Standard
**Batch**: 2 of several

## Completed Tasks (Cumulative)

### Batch 1 (already done)

- [x] **T1 / 1.1** — `llm/embeddings.py` — `crear_embeddings()` factory with Ollama/OpenAI support
- [x] **T3 / 2.1** — `llm/data_loader.py` — Replaced stale hardcoded paths with `REPORTES_DIR.glob("*.md")`
- [x] **T6 / 3.1** — `pyproject.toml` — Removed rank-bm25, added new deps, ran `uv lock`
- [x] **T7 / 3.2** — `.env.example` — Added SUPABASE_URL, SUPABASE_SERVICE_KEY, EMBEDDING_PROVIDER, OPENAI_API_KEY
- [x] **T8 / 3.3** — `Makefile` — Added `ingest` and `reindex` placeholder targets + `.PHONY` entries

### Batch 2 (this batch)

- [x] **T2 / 1.2** — `llm/vector_store.py` — `crear_vector_store()` factory
  - Reads `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` from env
  - No URL → returns `None` silently
  - URL without key → raises `OSError`
  - Both present → `supabase.Client` + `SupabaseVectorStore`
  - Google-style docstrings, module-level `load_dotenv()`

- [x] **T4 / 2.2** — `llm/qa_chain.py` — Remove BM25, integrate vector store
  - Removed `from rank_bm25 import BM25Okapi`, `_construir_bm25()`, `_recuperar_chunks()`
  - Removed `top_k` and `contexto_completo` params from `responder_pregunta()`
  - New logic: `crear_vector_store(crear_embeddings())` → if store exists, `similarity_search(k=5)` + LLM + `_parsear_respuesta()`; if `None`, return plain message with `encontrado=False`
  - No LLM call, no `cargar_contexto()` in no-Supabase path
  - Updated module docstring and `__main__` demo
  - Kept `_parsear_respuesta()` byte-identical

- [x] **T5 / 2.3** — `app/dashboard.py` — Remove BM25-related UI controls
  - Removed `usar_completo` toggle and `top_k` slider from sidebar
  - Updated `responder_pregunta()` call (removed `top_k`/`contexto_completo` args)
  - Simplified fuentes expander guard to just `resultado.get("fuentes")`
  - Sidebar flow: modelo → divider → memory → divider → contexto crudo button

## Files Changed

| File | Action | What Was Done |
|------|--------|---------------|
| `llm/vector_store.py` | Created | New factory: `crear_vector_store()` with Supabase integration |
| `llm/qa_chain.py` | Modified | Removed BM25, added dual-path Supabase/no-Supabase logic |
| `app/dashboard.py` | Modified | Removed sidebar BM25 controls, simplified call |

## Deviations from Design

None — implementation matches design.

## Issues Found

- Spec Scenario 3 says `crear_vector_store()` without `SUPABASE_URL` should **raise** `OSError`, but task T2 explicitly says **return `None`** silently. Followed the task (which matches the design's `SupabaseVectorStore | None` return type and the data flow diagram). The test for Scenario 3 will need to be adjusted accordingly.

## Verification Results

| Check | Result |
|-------|--------|
| `ruff check llm/vector_store.py llm/qa_chain.py app/dashboard.py` | ✅ All checks passed |
| `from llm.vector_store import crear_vector_store` | ✅ Module imports correctly |
| No Supabase → `encontrado: False` | ✅ `responder_pregunta('test')['encontrado']` returns `False` |
| No `top_k`/`contexto_completo` in signature | ✅ Signature: `['pregunta', 'llm', 'historial']` |
| Demo `python -m llm.qa_chain` | ✅ Shows no-Supabase message with all fields |

## Remaining Tasks

- [ ] **T9 / 4.1-4.3** — Tests for embeddings, vector store, qa_chain
- [ ] **T10 / 5.1-5.4** — Verification (ruff, pytest, grep checks)

## Status

8/13 tasks complete. Ready for next batch (tests + final verification).
