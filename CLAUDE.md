# CLAUDE.md — Hoteles Estelar Chat Assistant

## Project Overview

Enterprise chatbot for Hoteles Estelar S.A. that provides Q&A, executive summaries, and FAQ generation based on financial and corporate reports. Built incrementally as part of a university course on Generative AI techniques.

**Stack:** Python 3.12 · uv · LangChain · Anthropic Claude + Ollama · BM25 · Streamlit

## Key Architecture Decisions

- **Factory pattern** for LLM creation (`llm/factory.py`): supports switching between Claude and Ollama without changing business logic.
- **Dependency injection**: all domain functions accept `llm: BaseChatModel | None` — never instantiate LLMs inside business logic.
- **Prompts separated**: all system prompts and templates live in `llm/prompts.py` and `system_prompt.txt`. Never hardcode prompts in chain logic.
- **External system prompt**: `system_prompt.txt` is loaded at runtime so non-technical users can edit behavior without touching code.
- **BM25 retrieval**: chunks of 150 words with 30-word overlap for Q&A. Simpler than vector embeddings and sufficient for structured financial text.

## Conventions

### Code Style

- **Docstrings are MANDATORY** on every module, class, and public function. Use the triple-quote format with description, parameters, and return types.
- **High cohesion, low coupling**: each module does ONE thing. When adding a feature, create a new focused module rather than extending an existing one.
- **Type hints** on all public function signatures. Use `str | None` not `Optional[str]`, `list[str]` not `List[str]`.
- **Import order**: stdlib → third-party → local, separated by blank lines.

### Package Management

- Use **uv exclusively**. Never run `pip install` directly.
- After adding any dependency, run `uv lock` to update the lockfile.
- Keep `pyproject.toml` name, version, and description updated.

### File Organization

```text
llm/          → Domain logic (LLM chains, data loading, prompts)
app/          → Presentation layer (Streamlit dashboard only)
scripts/      → Data pipeline scripts (scraping, consolidation)
data/         → Data files (raw and processed, gitignored where needed)
tests/        → Test files mirroring llm/ structure
```

- Never import from `app/` in `llm/`. The dependency direction is `app/` → `llm/` → `data/`.
- Business logic goes in `llm/`. UI orchestration goes in `app/`.

### LangChain Chains

Chains follow this pattern:

```python
chain = PROMPT_TEMPLATE | llm | StrOutputParser()
result = chain.invoke({"variable": value})
```

- Always use `StrOutputParser()` at the end.
- Never call `llm.invoke()` directly for multi-step chains.
- Pass the LLM instance, don't create it inline.

## Common Tasks

### Adding a new LLM capability

1. Create `llm/new_capability.py` with a single exported function.
2. Add the prompt to `llm/prompts.py`.
3. Accept `llm: BaseChatModel | None = None` parameter, default via `crear_llm()`.
4. Add tests in `tests/test_new_capability.py`.
5. Wire into `app/dashboard.py` if it needs a UI.
6. Update `Makefile` if there's a new run command.

### Adding a new LLM provider

1. Add the provider name and models to `llm/factory.py`.
2. Add the new `langchain-<provider>` dependency to `pyproject.toml`.
3. Run `uv lock`.

### Running the project

```bash
make dev          # Start Streamlit dashboard
make run-qa       # Run Q&A chain standalone
make run-summary  # Run summarizer standalone
make run-faq      # Run FAQ generator standalone
make lint         # Run linters
make test         # Run tests
make setup        # Initial setup (venv + dependencies)
```

## Important Notes

- Python 3.12 is REQUIRED. Dependency `faiss-cpu` (future use) does not support 3.13+.
- `.env` contains `ANTHROPIC_API_KEY` — never commit it.
- The BM25 chunking is configured in `qa_chain.py` (chunk size 150 words, overlap 30).
- `data/processed/estelar_consolidado.txt` is auto-generated from `data/estelar_reportes/*.md` — never edit it manually.
- When consulting LangChain documentation, always use the latest version. The API changes frequently between major versions.
