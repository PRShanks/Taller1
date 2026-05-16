# Archive Report: `financial-tool`

**Date**: 2026-05-16
**Status**: COMPLETE — PASS
**Mode**: hybrid (openspec + engram)

## Change Summary

Implementación de una LangChain Tool (`query_financiero`) para consultas financieras deterministas vía SQLite local. El LLM puede invocar la tool via `.bind_tools()` para obtener datos numéricos precisos cuando detecta consultas financieras ("EBITDA 2024 = COP 70.147M"), complementando al RAG basado en embeddings.

## DAG State

```text
proposal → specs → design → tasks → apply → verify → archive ✅
```

## Artifacts

### Openspec (filesystem)

| Artifact | Path |
|----------|------|
| Proposal | `openspec/changes/archive/2026-05-16-financial-tool/proposal.md` |
| Spec | `openspec/changes/archive/2026-05-16-financial-tool/spec.md` |
| Design | — (inline in engram) |
| Tasks | — (inline in engram) |
| Apply Progress | — (inline in engram) |
| Verify Report | — (inline in engram) |
| Archive Report | `openspec/changes/archive/2026-05-16-financial-tool/archive.md` |

### Engram (memory)

| Artifact | ID | Title |
|----------|----|-------|
| Proposal | #237 | sdd/financial-tool/proposal |
| Spec | #239 | sdd/financial-tool/spec |
| Design | #240 | sdd/financial-tool/design |
| Apply Progress (Batch 2) | #248 | sdd/financial-tool/apply-progress |
| Verify Report | #251 | sdd/financial-tool/verify-report |
| Archive Report | — | sdd/financial-tool/archive-report |
| Tool Layer (discovery) | #246 | Created query_financiero LangChain tool |
| System Prompt (discovery) | #247 | Updated system_prompt.md to v2.1 (SQLite local) |

## Main Specs Updated

| Domain | Action | Details |
|--------|--------|---------|
| `financial` | Created | `openspec/specs/financial/spec.md` (full spec, not delta) |

## Files Created

| File | Purpose |
|------|---------|
| `llm/financial/__init__.py` | Package init |
| `llm/financial/db.py` | SQLite setup + auto-seed + consultas parametrizadas |
| `llm/financial/tool.py` | `@tool query_financiero` con params seccion/anio/concepto |
| `tests/test_financial_db.py` | 15 tests (DB schema, auto-seed, filtros, SQL injection) |
| `tests/test_financial_tool.py` | 12 tests (tool estructura, ejecución) |
| `tests/test_financial_integration.py` | 5 tests (tool-calling loop, fallback Ollama, offline) |

## Files Modified

| File | Change |
|------|--------|
| `llm/models.py` | +`uso_tool_financiera: bool` en `RespuestaQA` |
| `llm/core/qa.py` | Tool-calling loop con `bind_tools()` + fallback Ollama |
| `app/dashboard.py` | Badge "📊 Dato financiero" condicional |
| `system_prompt.md` | v2.1: SQLite local, params estructurados, sin Supabase/ILIKE |
| `llm/prompts/qa.py` | Fix path `system_prompt.txt` → `system_prompt.md` |

## Verification Results

| Metric | Result |
|--------|--------|
| Scenario compliance | 28/28 compliant ✅ |
| New tests | 32 tests |
| Total tests | 58 tests, all passing ✅ |
| Ruff lint | Clean ✅ |
| New dependencies | 0 ✅ (sqlite3 stdlib) |
| Verdict | **PASS** — archive proceeding |

## Deviations from Design

| Design | Implementation | Impact |
|--------|---------------|--------|
| `id` column as INTEGER PK | `id` es TEXT (UUID del CSV) | None — PK uniqueness preserved |
| `tool_used: bool` field | Dropped — solo `uso_tool_financiera` | Simpler API, no impact |

## Lessons Learned

- `BaseTool.get_input_schema()` returns a Pydantic model, not a dict — use `.model_json_schema()` to get JSON schema properties.
- Markdown edits need careful offset tracking when lines shift during batch edits.
- `bind_tools()` puede no ser soportado por Ollama → `try/except (TypeError, AttributeError, NotImplementedError)` como fallback.
- SQLite con `check_same_thread=False` es necesario para Streamlit (multi-thread).

## SDD Cycle Complete

```text
✅ proposal    — 2026-05-16 06:03
✅ specs       — 2026-05-16 06:12
✅ design      — 2026-05-16 06:16
✅ tasks       — 2026-05-16 (inline)
✅ apply       — 2026-05-16 06:42 (Batch 2)
✅ verify      — 2026-05-16 07:03
✅ archive     — 2026-05-16 14:11
```

Ready for the next change.
