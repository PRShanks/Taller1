# Tasks: RAG Migration (BM25 → Supabase pgvector)

**Line budget**: ~320 lines estimated (medium risk). Chained PRs not required — self-contained change.

## Phase 1: Foundation — New Modules

- [x] 1.1 `llm/embeddings.py` — `crear_embeddings()` factory. Reads `EMBEDDING_PROVIDER` env var (default `ollama`). Ollama → `OllamaEmbeddings(model="nomic-embed-text")`. OpenAI → `OpenAIEmbeddings(text-embedding-3-small)`. Missing key → `OSError`. Unknown provider → `ValueError`. Google-style docstrings.
- [x] 1.2 `llm/vector_store.py` — `crear_vector_store(embeddings)` factory. Reads `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`. No URL → returns `None` silently. URL without key → `OSError`. Both present → `supabase.Client` + `SupabaseVectorStore`. No hardcoded embedding dimension.

## Phase 2: Core Logic — Modify Existing Modules

- [x] 2.1 `llm/data_loader.py` — Replace stale `RAW_MD_FINANCIERO`/`RAW_MD_CORPORATIVO` with `glob("data/estelar_reportes/*.md")`. Keep `cargar_contexto()` and `consolidar_datos()` signatures unchanged for backward compat with summarizer/FAQ.
- [x] 2.2 `llm/qa_chain.py` — Remove `from rank_bm25 import BM25Okapi`, `_construir_bm25()`, `_recuperar_chunks()`. Remove `top_k` and `contexto_completo` params from `responder_pregunta()`. New logic: try `crear_vector_store(crear_embeddings())` → if store, `similarity_search()` + LLM + `_parsear_respuesta()`; if `None`, return plain message "RAG no disponible" with `encontrado=False`. Keep `_parsear_respuesta()` and return format unchanged.
- [x] 2.3 `app/dashboard.py` — Remove `usar_completo` toggle and `top_k` slider from sidebar. Remove `top_k`/`contexto_completo` from `responder_pregunta()` call. Remove `not usar_completo` guard on fuentes expander (show conditionally on `resultado.get("fuentes")`).

## Phase 3: Config & Dependencies

- [x] 3.1 `pyproject.toml` — Remove `"rank-bm25>=0.2.2"`. Add `"langchain-community"`, `"langchain-openai"`, `"supabase"`, `"langchain-text-splitters"`. Run `uv lock`.
- [x] 3.2 `.env.example` — Add `SUPABASE_URL=`, `SUPABASE_SERVICE_KEY=`, `EMBEDDING_PROVIDER=ollama`, `OPENAI_API_KEY=`.
- [x] 3.3 `Makefile` — Add `ingest` target: `@echo "Placeholder: la ingesta la realiza el equipo de datos."`. Add `reindex` target: same placeholder. Add both to `.PHONY`.

## Phase 4: Testing (Strict TDD — write tests after code)

- [ ] 4.1 `tests/test_embeddings.py` — Test default Ollama, OpenAI missing key → `OSError`, invalid provider → `ValueError`.
- [ ] 4.2 `tests/test_vector_store.py` — Test no URL → `None`, URL without key → `OSError`.
- [ ] 4.3 `tests/test_qa_chain.py` — Test signature: `top_k`/`contexto_completo` absent. Test no Supabase → dict with `encontrado=False` and "no disponible" in response. No LLM call, no `cargar_contexto()`.

## Phase 5: Verification

- [ ] 5.1 Run `ruff check llm/ app/ tests/` — zero lint errors.
- [ ] 5.2 Run `pytest tests/ -v` — all 7+ test cases pass.
- [ ] 5.3 Run `grep -r "rank-bm25" pyproject.toml` — no matches.
- [ ] 5.4 Run scenario checks from spec: embedding factory, vector store graceful errors, no-Supabase message, glob-based data loading.
