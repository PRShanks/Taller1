# Exploration: RAG Migration (BM25 → Supabase pgvector)

## Executive Summary

The Taller1 project currently uses BM25 lexical search (`rank-bm25`) with word-window chunking (150 words, 30-word overlap) for retrieval-augmented Q&A. This change replaces BM25 with a semantic RAG system backed by Supabase Vector DB (pgvector), selecting OpenAI `text-embedding-3-small` as the embedding provider. The migration touches 6 files, removes the `rank-bm25` dependency, adds 4 new packages (`langchain-community`, `langchain-openai`, `langchain-text-splitters`, `supabase`), and keeps summarizer/FAQ/memory/prompts modules intact for subsequent changes.

The document ingestion pipeline shifts from a single consolidated `.txt` file to chunked `Document` objects with metadata (source: file name, section header). The BM25 word-window approach (no semantic understanding) is replaced by vector similarity search via `SupabaseVectorStore.as_retriever()` with `RecursiveCharacterTextSplitter` chunking. This is a self-contained change that lays the foundation for the agent + tools architecture (change 2) and Postgres checkpointer (change 3).

---

## Current State

### Architecture

The project follows a clean layered architecture: `app/` (Streamlit UI) → `llm/` (domain logic) → `data/` (raw + processed). The LLM layer uses LangChain LCEL chains with dependency injection and factory pattern.

### BM25 Retrieval Flow

```
User question → responder_pregunta() → cargar_contexto() (reads 53KB .txt)
  → _construir_bm25() (word windows: 150 tokens, 30 overlap)
  → _recuperar_chunks() (BM25Okapi.get_scores on tokenized query)
  → Top-k chunk context → LLM prompt → JSON response
```

**Location**: `llm/qa_chain.py`, lines 58-84.

**What BM25 does**: Tokenizes text into word windows, builds a TF-IDF-based sparse index, scores query-chunk relevance by term frequency overlap. No semantic understanding — "ingresos" won't match "facturación" or "ventas" unless those words appear explicitly.

### Data Files

| File | Size | Content |
|------|------|---------|
| `hoteles_estelar_agente_clientes.md` | 33.8 KB | Corporate info, hotels, services |
| `informacion general.md` | 10.4 KB | General company information |
| `inteligencia empresarial.md` | 9.0 KB | Business intelligence |
| `reporte-financiero-completo.md` | 33.4 KB | Financial report 2019-2024 |
| `estelar_consolidado.txt` (processed) | 53.6 KB | Concatenated + cleaned |

**Important discovery**: `llm/data_loader.py` references stale filenames (`HOTELES_ESTELAR_890304099.md`, `hoteles_estelar.md`) that don't match the actual files. The `scripts/consolidar_estelar.py` works correctly because it globs all `.md`/`.txt` files from the directory.

### UI Controls

In `app/dashboard.py` sidebar (lines 87-95):
- `usar_completo` toggle: bypasses BM25 entirely, passes full context to LLM
- `top_k` number input (1-15, default 5): number of BM25 chunks to retrieve (disabled when `usar_completo=True`)

### Dependencies (BM25-related)

```toml
# pyproject.toml — current
"rank-bm25>=0.2.2",       # ← TO REMOVE
"langchain-core>=1.3.2",  # ← stays
```

---

## Affected Areas

### Files to Modify

1. **`llm/qa_chain.py`** (161 lines) — **Heavy refactor**
   - Remove: `_construir_bm25()`, `_recuperar_chunks()`, `rank_bm25` import
   - Add: retriever injection (semantic search replaces lexical)
   - Modify: `responder_pregunta()` to use vector retriever instead of BM25
   - Keep: `_parsear_respuesta()` (response normalization)

2. **`llm/data_loader.py`** (99 lines) — **Moderate refactor**
   - Add: `RecursiveCharacterTextSplitter` integration
   - Add: function to produce `list[Document]` with metadata (source file, chunk index)
   - Fix: stale file references (use glob pattern matching actual files)
   - Keep: `limpiar_markdown()`, `cargar_contexto()` (for summarizer/FAQ backward compat)
   - Add: embedding + Supabase ingestion function

3. **`app/dashboard.py`** (247 lines) — **Light refactor**
   - Remove: `usar_completo` toggle and `top_k` number input from sidebar
   - Add: `top_k` remains but now controls vector search k (renamed for clarity)
   - Modify: `responder_pregunta()` call signature (no more `contexto_completo` param)
   - Keep: everything else (commands, chat, memory, error handling)

4. **`pyproject.toml`** — **Dependency changes**
   - Remove: `"rank-bm25>=0.2.2"`
   - Add: `"langchain-community>=0.3.0"` (SupabaseVectorStore)
   - Add: `"langchain-openai>=0.3.0"` (OpenAIEmbeddings)
   - Add: `"langchain-text-splitters>=0.3.0"` (RecursiveCharacterTextSplitter)
   - Add: `"supabase>=2.0.0"` (Python Supabase client)

5. **`Makefile`** — Add ingestion targets
   - `make ingest`: runs document → chunk → embed → Supabase pipeline
   - `make reindex`: clears + re-ingests all documents
   - `make ingest-check`: verifies docs are in Supabase

6. **`.env.example`** — New environment variables
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `OPENAI_API_KEY`

### Files NOT Modified (deferred to subsequent changes)

| File | Why unchanged |
|------|---------------|
| `llm/summarizer.py` | Becomes tool in change 2 — keep current behavior |
| `llm/faq_generator.py` | Becomes tool in change 2 — keep current behavior |
| `llm/prompts.py` | Refactored in change 2 (agent system prompt) |
| `llm/factory.py` | Unchanged — LLM creation stays the same |
| `llm/memory.py` | Migrated to Postgres checkpointer in change 3 |
| `system_prompt.txt` | Refactored in change 2 (agent system prompt) |
| `scripts/consolidar_estelar.py` | Unused after migration (replaced by ingestion pipeline) |

---

## Approaches

### Approach 1: OpenAI Embeddings + Supabase pgvector (RECOMMENDED)

Use OpenAI `text-embedding-3-small` (1536 dimensions, $0.02/1M tokens) with `SupabaseVectorStore` from `langchain-community`.

```
Documents (.md) → RecursiveCharacterTextSplitter (chunk_size=1000, overlap=200)
  → OpenAIEmbeddings (text-embedding-3-small, 1536d)
  → SupabaseVectorStore (table: documents, fn: match_documents)
  → vector_store.as_retriever(search_type="similarity", k=5)
  → inject into responder_pregunta()
```

- **Pros**:
  - Production-grade embedding quality
  - SupabaseVectorStore is well-tested in LangChain ecosystem
  - `text-embedding-3-small` is cheap (~$0.02 per 1M tokens); 53KB text ≈ 13K tokens ≈ $0.00026 for all docs
  - Metadata filtering by source file (useful for agent tools later)
  - Supabase free tier supports pgvector (500MB DB)
  - API-based: no GPU needed locally
- **Cons**:
  - Requires OpenAI API key (adds dependency on external service)
  - Slight latency for embedding API calls during ingestion
  - Monthly cost (negligible for this data size)

### Approach 2: Ollama Embeddings + Supabase pgvector

Use Ollama's `nomic-embed-text` (768 dimensions, local, free) with Supabase.

- **Pros**:
  - No external API key needed (fully local)
  - No per-token cost
  - Same SupabaseVectorStore integration
  - Fits project's existing Ollama support for LLMs
- **Cons**:
  - Embedding quality significantly lower than OpenAI
  - `nomic-embed-text` dimension is 768 (different from OpenAI's 1536) — schema must match
  - Must have Ollama running locally during ingestion and query
  - Spanish performance of `nomic-embed-text` is subpar vs multilingual models
  - Not suitable for production

### Approach 3: HuggingFace Sentence-Transformers + Supabase

Use `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384d, local).

- **Pros**:
  - Multilingual model — good Spanish performance
  - No API key needed
  - Can use `HuggingFaceEmbeddings` from `langchain-community`
- **Cons**:
  - 384 dimensions — lower semantic resolution
  - Model download (~420MB) on first run
  - Slight quality gap vs OpenAI `text-embedding-3-small`
  - CPU-bound embedding (slow for large datasets, but fine for 53KB)

### Approach 4: Hybrid (BM25 + Vector) — DEFERRED

Combine BM25 + vector similarity search for best-of-both-worlds retrieval.

- **Verdict**: Not needed for this change. The data is small (~53KB), and semantic search alone is sufficient. Hybrid search adds complexity without proportional benefit at this scale. Can be added later if retrieval quality is insufficient.

---

## Recommendation

**Approach 1: OpenAI Embeddings + Supabase pgvector**

Rationale:
1. The project already uses a paid API (Anthropic Claude), so adding OpenAI for embeddings is consistent
2. Cost is negligible: embedding 53KB of text costs < $0.001; monthly query costs will be similarly tiny
3. `text-embedding-3-small` (1536d) is the industry standard — best Spanish semantic understanding
4. `SupabaseVectorStore` has the most mature LangChain integration of all PostgreSQL-based vector stores
5. The specific embedding dimension (1536) is well-documented and easy to set in the SQL schema
6. The `as_retriever()` API makes the retriever plug-and-play for the future agent architecture

**Key decision**: Use `RecursiveCharacterTextSplitter` with `chunk_size=1000` and `chunk_overlap=200`. This produces ~70-80 chunks from 53KB of text — well within Supabase free tier limits.

---

## Technical Details

### Supabase SQL Schema

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content TEXT NOT NULL,
  metadata JSONB DEFAULT '{}'::jsonb,
  embedding VECTOR(1536)
);

CREATE INDEX ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);

CREATE FUNCTION match_documents(
  query_embedding VECTOR(1536),
  match_count INT DEFAULT 5,
  filter JSONB DEFAULT '{}'::jsonb
) RETURNS TABLE (
  id UUID,
  content TEXT,
  metadata JSONB,
  similarity FLOAT
) LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    d.id,
    d.content,
    d.metadata,
    1 - (d.embedding <=> query_embedding) AS similarity
  FROM documents d
  WHERE d.metadata @> filter
  ORDER BY d.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
```

### Ingestion Pipeline Design

```python
# New: llm/data_loader.py addition
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from supabase import create_client

def cargar_documentos() -> list[Document]:
    """Load all .md files as LangChain Documents with source metadata."""
    docs = []
    for md_file in sorted(Path("data/estelar_reportes").glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        cleaned = limpiar_markdown(text)
        docs.append(
            Document(page_content=cleaned, metadata={"source": md_file.name})
        )
    return docs

def crear_vector_store() -> SupabaseVectorStore:
    """Create or connect to Supabase vector store."""
    client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    return SupabaseVectorStore(
        client=client,
        embedding=embeddings,
        table_name="documents",
        query_name="match_documents",
    )

def ingestar_documentos(force: bool = False) -> SupabaseVectorStore:
    """Chunk, embed, and index all documents into Supabase."""
    docs = cargar_documentos()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    vector_store = crear_vector_store()
    if force:
        # Delete existing documents (truncate)
        ...
    vector_store.add_documents(chunks)
    return vector_store
```

### Retriever Integration

```python
# Modified: llm/qa_chain.py
def responder_pregunta(
    pregunta: str,
    top_k: int = 5,
    llm: BaseChatModel | None = None,
    historial: list[BaseMessage] | None = None,
    retriever: BaseRetriever | None = None,
) -> dict:
    if llm is None:
        llm = crear_llm(temperature=0.0, max_tokens=512)
    if retriever is None:
        from llm.data_loader import crear_vector_store
        retriever = crear_vector_store().as_retriever(
            search_type="similarity",
            search_kwargs={"k": top_k},
        )

    docs = retriever.invoke(pregunta)
    fuentes = [doc.page_content for doc in docs]
    contexto = "\n\n---\n\n".join(fuentes)
    # ... rest stays the same
```

### Embedding Model Comparison

| Model | Provider | Dims | Quality | Cost | Local? |
|-------|----------|------|---------|------|--------|
| `text-embedding-3-small` | OpenAI | 1536 | ★★★★★ | $0.02/1M tokens | No |
| `text-embedding-3-large` | OpenAI | 3072 | ★★★★★ | $0.13/1M tokens | No |
| `nomic-embed-text` | Ollama | 768 | ★★★☆☆ | Free | Yes |
| `all-MiniLM-L6-v2` | HuggingFace | 384 | ★★★☆☆ | Free | Yes |
| `paraphrase-multilingual-MiniLM-L12-v2` | HuggingFace | 384 | ★★★★☆ | Free | Yes |

---

## Risks

1. **LangChain Python SupabaseVectorStore API uncertainty**
   - The documented API (Context7 shows JS examples) may differ from Python
   - **Mitigation**: Check `langchain-community` source on GitHub and the installed package before implementing. The Python constructor typically uses `SupabaseVectorStore(client=..., embedding=..., table_name=..., query_name=...)`

2. **OpenAI API dependency**
   - The project currently has no OpenAI dependency; adding one means another API key to manage
   - **Mitigation**: Document the key in `.env.example`; cost is negligible for this data volume

3. **Supabase setup complexity**
   - Requires creating a Supabase project, enabling pgvector, running SQL migration
   - **Mitigation**: Provide a `migrations/001_setup_pgvector.sql` file and Makefile target. Supabase has a free tier.

4. **Dimension mismatch**
   - If the SQL schema vector dimension doesn't match the embedding model, queries will fail at the PostgreSQL level
   - **Mitigation**: Use a constant `EMBEDDING_DIMENSION = 1536` shared between Python and SQL; validate at runtime

5. **Stale data_loader references**
   - `data_loader.py` hardcodes filenames that don't exist (`HOTELES_ESTELAR_890304099.md`)
   - **Mitigation**: Fix as part of this change — use glob patterns

6. **No existing tests**
   - The project has zero tests; adding a retrieval pipeline without tests is risky
   - **Mitigation**: Write integration tests for the ingestion pipeline and retrieval (mock Supabase + OpenAI)

7. **Backward compatibility**
   - `cargar_contexto()` is used by `summarizer.py` and `faq_generator.py` — must keep working
   - **Mitigation**: Keep `cargar_contexto()` intact. Add new functions (`cargar_documentos()`, `crear_vector_store()`) without removing existing ones.

---

## Ready for Proposal

**Yes** — the exploration is complete. The orchestrator should proceed to `sdd-propose` with the following scope:

1. Remove BM25 dependency and code from `llm/qa_chain.py`
2. Add OpenAI embeddings + Supabase vector store integration to `llm/data_loader.py`
3. Rewrite `responder_pregunta()` to use `SupabaseVectorStore.as_retriever()`
4. Update `app/dashboard.py` UI (remove `contexto_completo` toggle, keep `top_k`)
5. Add 4 new dependencies (`pyproject.toml`) + remove `rank-bm25`
6. Create `migrations/001_setup_pgvector.sql`
7. Add Makefile targets (`make ingest`, `make reindex`)
8. Update `.env.example` with 3 new environment variables
9. Write tests: ingestion pipeline, retrieval quality, backward compatibility
10. Fix stale file references in `data_loader.py`

### Key Architecture Decision

**Embedding model**: `text-embedding-3-small` (OpenAI, 1536d)
**Why**: Production quality, trivial cost, best Spanish semantic performance of affordable options. Consistent with the project's existing approach of using paid cloud APIs (Claude).
