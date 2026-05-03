# Audit Remediation Report

> **Project**: PAR LLAMA
> **Audit Date**: 2026-05-03
> **Remediation Date**: 2026-05-03
> **Issues Targeted**: ARC-001, QA-001, QA-002

---

## Execution Summary

| Phase | Status | Agent | Issues Targeted | Resolved | Partial | Manual |
|-------|--------|-------|----------------|----------|---------|--------|
| ARC-001 (Architecture) | Done | fix-architecture | 1 | 1 | 0 | 0 |
| QA-001/QA-002 (Code Quality) | Done | fix-code-quality | 2 | 2 | 0 | 0 |
| Verification | Pass | — | — | — | — | — |

**Overall**: 3 issues resolved, 0 partial, 0 require manual intervention.

---

## Resolved Issues

### Architecture

- **[ARC-001] God Object: ParLlamaApp (1,094 lines) Violates Single Responsibility** -- `src/parllama/app.py`
  - Extracted `ModelJobProcessor` (372 lines) to `src/parllama/coordinators/model_job_processor.py` -- owns job queue, progress reporting, pull/push/copy/create model operations, and Ollama error handling.
  - Extracted `ExecutionCoordinator` (231 lines) to `src/parllama/coordinators/execution_coordinator.py` -- owns execution system initialization, template matching dispatch, command execution, and result injection into chat sessions.
  - `app.py` reduced from 1,094 to ~759 lines (31% reduction).
  - Thin `@on()` handlers remain in `app.py` per Textual framework requirements, delegating to coordinators via one-liner calls.
  - `MessageRouter` extraction deferred to ARC-005 (pub/sub consolidation) since `post_message_all()` and `notify_subs` are core app infrastructure used by both remaining app.py code and the new coordinators.
  - Fixed pre-existing bug in `do_copy_local_model` where `ollama.ResponseError` handler passed the job event object instead of the caught exception to `handle_ollama_error`.
  - Updated `options_view.py` to reference `command_executor` and `template_matcher` through `app.execution_coordinator`.

### Code Quality

- **[QA-001] Magic Number in Error Parsing with ast.literal_eval** -- `src/parllama/chat_session.py:290-325`
  - Replaced hardcoded `err_msg[18:]` slicing with `_parse_llm_error()` static method using `str.removeprefix("Error code: ")` and `str.find(" - ")` to safely strip the provider library prefix.
  - Replaced `ast.literal_eval()` with `json.loads()` wrapped in try/except for `JSONDecodeError`, `ValueError`, `KeyError`.
  - Method returns raw error string as fallback when parsing fails, eliminating IndexError risk on short messages.
  - Removed unused `import ast`.

- **[QA-002] Duplicated Error Parsing Logic** -- `src/parllama/chat_session.py:444,476`
  - Both copy-pasted parsing blocks replaced with calls to `_parse_llm_error()`.

---

## Verification Results

- **Format**: Pass (ruff format, 108 files unchanged)
- **Lint**: Pass (ruff check, all checks passed)
- **Type Check**: Pass (pyright, 0 errors, 0 warnings)
- **Tests**: Pass (132/132 passed)

---

## Files Changed

### Created
- `src/parllama/coordinators/__init__.py`
- `src/parllama/coordinators/model_job_processor.py` (372 lines)
- `src/parllama/coordinators/execution_coordinator.py` (231 lines)

### Modified
- `src/parllama/app.py` -- removed ~335 lines of inline logic, replaced with thin delegations to coordinators
- `src/parllama/chat_session.py` -- added `_parse_llm_error()`, replaced 2 hardcoded parsing blocks, removed `import ast`
- `src/parllama/widgets/views/options_view.py` -- updated `command_executor`/`template_matcher` references to use `app.execution_coordinator`

---

## Next Steps

1. **ARC-005** (pub/sub consolidation) is the natural follow-up to ARC-001 -- extract `post_message_all` / `notify_subs` into a proper event bus once Textual's message system is better leveraged.
2. **ARC-002** (module-level singleton migration) would further improve testability of the new coordinators.
3. Re-run `/audit` to get an updated AUDIT.md reflecting current state.
