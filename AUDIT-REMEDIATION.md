# Audit Remediation Report

> **Project**: parllama (PAR LLAMA)
> **Audit Date**: 2026-10-15
> **Remediation Date**: 2026-10-15
> **Severity Filter Applied**: all
> **Plan Source**: AUDIT.md `## Remediation Plan` (no AUDIT-REMEDIATION-PLAN.md playbook was present)
> **Implementation Model**: Opus 5 (all fix agents)

---

## Execution Summary

| Phase | Status | Agent | Issues Targeted | Resolved | Partial | Manual |
|-------|--------|-------|----------------|----------|---------|--------|
| 0 — Options card (pre-ARC-001) | ✅ | general-purpose | 1 | 1 | 0 | 0 |
| 1 — Critical Security | ✅ | fix-security | 4 | 3 | 1 | 0 |
| 2 — Critical Architecture | ✅ | fix-architecture | 5 | 4 | 1 | 0 |
| 3a — Security (remaining) | ✅ | fix-security | 3 (+SEC-006 by orchestrator) | 4 | 0 | 0 |
| 3b — Architecture (remaining) | ✅ | fix-architecture | 5 | 5 | 0 | 0 |
| 3c — All Code Quality | ✅ | fix-code-quality | 7 (+QA-004 tail by orchestrator) | 7 | 0 | 0 |
| 3d — All Documentation | ✅ | fix-documentation | 14 | 14 | 0 | 0 |
| 4 — Verification | ✅ | orchestrator | — | — | — | — |

**Overall**: 40 of 40 audit issues closed — 38 resolved outright, 2 closed with documented deviations (SEC-002, ARC-004) plus follow-up cards for their remainder. No issue requires manual intervention to complete this run; two items await product decisions (filed as backlog cards).

**Run scale**: 47 commits, 121 files changed, +5,416 / −3,101 lines. Test count 260 → 397, all green at every merge point.

---

## Resolved Issues ✅

### Security
- **[QA-001]** `continue_generation` guard — `src/parllama/chat_session.py` — no-model check moved before any mutation (`_generating` flag, message deletion, `save()`); regression test `test_continue_generation_empty_model_leaves_state_untouched` (failed on old code, passes on fix).
- **[SEC-001]** Credential env scrub — `execution/command_executor.py` — `scrub_credential_env()` drops every variable whose name contains KEY/TOKEN/SECRET/PASSWORD/PASSWD/CREDENTIAL before child execution; confirmation dialog now states the environment-inheritance behavior; unit + end-to-end tests.
- **[SEC-002]** Plaintext provider keys — `settings_manager.py`, `app.py`, options view — keys migrate to the encrypted vault at startup when the vault is unlocked and `PARLLAMA_VAULT_KEY` opens it; Options key entry writes the vault; settings.json holds blanks after migration; 8 disk-level tests. **Deviation**: non-vault users keep plaintext (0600) to preserve unattended startup — product decision filed as backlog card.
- **[SEC-003]** Remote fetch SSRF/integrity — `attachment_utils.py`, `net_guard.py` — public-address check before every request (incl. per-redirect-hop), `FileValidator` on fetched bytes, SHA-256 verification on cache/re-fetch, malformed-port `AttachmentError`; 10+ tests.
- **[SEC-004]** Blocklist limits documented (docs-only, AST-verified unchanged).
- **[SEC-005]** ZIP hardening — `validators/file_validator.py` + `import_fabric.py` — `safe_extract_zip()` with streaming decompressed-byte caps (total + per-entry, partial-file cleanup) and `is_unsafe_zip_entry_name()` rejecting drive-letter/UNC/POSIX-absolute/traversal names; replaced the raw `extractall`.
- **[SEC-006]** MD5 uses annotated as non-cryptographic identifiers (orchestrator, post-merge; the settings_manager site moved to `image_cache.py` in ARC-001 so the note follows the function).
- **[SEC-007]** Update-check exception type — `update_manager.py` now raises only the documented `ValueError` (catches `httpx.HTTPError`/`KeyError`/`TypeError`, calls `raise_for_status`); 4 mock-transport tests.

### Architecture
- **[ARC-001]** settings_manager decomposed — 1,842 → 593 lines; ~130 delegation pairs deleted; 449 call sites migrated to `settings.<group>.<field>`; new `paths.py`, `image_cache.py` (SSRF-guarded via `net_guard.py`), `net_guard.py`.
- **[ARC-002]** Nested v2 serialization — `schema_version: 2`, one-time loader migration (`settings/migration.py`) incl. legacy keys, per-field Pydantic validation, real v1 fixture test; startup-derived fields no longer persisted.
- **[ARC-003]** Side-effect-free singletons — explicit `bootstrap(args)` at composition roots; constructor-time I/O moved to first use; `MemoryManager.set_app()`; subprocess test asserts no import-time file creation.
- **[ARC-004]** App hub — EventBus broadcast at source for session/prompt list events; original-event forwarding (field-complete copy, add-field test); StatusMessage/PsMessage special cases removed; **deviation**: ~20 stop-and-delegate handlers remain, filed as follow-up card (larger redesign).
- **[ARC-005]** Provider fetch registry — `MODEL_LIST_FETCHERS` with shared filter/sort, None-created fallback, configured timeout everywhere, LiteLLM status/data validation.
- **[ARC-006]** ChatSession extraction — `stream_controller.py` + `session_store.py`; the duplicated ~60-line streaming loops collapsed onto one; 11 characterization tests written first; QA-001 semantics preserved; 1,174 → 850 lines.
- **[ARC-007]** One HTTP client — httpx everywhere (requests deleted from src and pyproject, plus urllib3/pydantic-core/google-genai/types-requests pins dropped); `net_guard.open_guarded_stream()` shared guarded client; **deviation from brief's letter**: chose httpx over image_cache's requests because the ollama SDK already makes httpx load-bearing.
- **[ARC-008]** Intent messages — `PrefillCreateModel`/`StartModelChat`; views own their widgets; App no longer reaches into child widgets on these paths.
- **[ARC-009]** SecureFileOps save path — `strict` flag on write helpers; settings save tries strict then relaxed; hand-rolled tempfile fallback deleted.
- **[ARC-010]** Message-barrel imports — all 54 importers moved to per-domain modules; barrel is re-export only.

### Code Quality
- **[QA-002]** Complexity tests — audit's five named functions verified covered (four by earlier phases, verified; site-model refresh: 14 new tests). Bonus bug fix: site-model cache never expired (self-comparison) — corrected.
- **[QA-003]** Dead code — 4 verified-dead symbols deleted (incl. one bypassing SecureFileOperations); live candidates kept with evidence.
- **[QA-004]** Dedup — retry_utils shared decision helper (`exceptions=` now honored), secrets shared clear core, `SessionFileDialogMixin`, input_with_history triple-tab-submit bug fixed; orchestrator completed the tail: execution_view stats pair and grid-navigation pair deduplicated (−28 lines); options_view/rag_view compose pair judged intentional divergence (placeholder skeleton vs full form).
- **[QA-005]** `refresh_site_models` error handling — was a crash path (`@work` exit_on_error closed the app on any network error); now catches and notifies, spinner cleared via `SiteModelsLoaded.refreshed=False`; tests fail on old code.
- **[QA-006]** Inert pylint disable removed (ruff equivalents verified not to fire).
- **[QA-007]** Dead comments/stray debug lines removed; swallowed abort error now logged; test readability fix.
- **[QA-008]** Bugbear (`B`) added to ruff; 5 new findings fixed properly, no noqa.

### Documentation
- **[DOC-001..014]** All landed: themes path, 7 TOC anchors, project_design.md refresh (v2 settings, bootstrap, StreamController/SessionStore, coordinators, new Attachment System + Network Fetch Guard sections, pending-TUI-pass noted), src/parllama/ prefixes + stale plaintext-keys claim corrected, spec status/class name, CI badge (`ci.yml`/main), `docs/guides/release.md`, docstrings for new public symbols, style-guide paths, README TOC completeness + regenerated CLI help, MIT License section, superpowers plans archived to `docs/archive/superpowers/`, `starting_tab` casing documented.

---

## Requires Manual Intervention 🔧

No issue is blocked, but three items need human decisions or review (all filed on the kanban board):

1. **Provider keys for non-vault users** (SEC-002 remainder) — decide between OS-keychain storage, prompting for a vault key, or accepting plaintext-with-0600. Card: "Decide OS-keychain storage…".
2. **`execution_require_confirmation` is now honored from saved settings** — a saved `false` skips the confirmation prompt before running model-generated code. Paul's stored value is `true`; review whether persistence of this flag is acceptable.
3. **Security-review the two hand-flagged changes** before any push: the vault key-migration flow (`settings_manager.py`/`app.py`) and the credential-scrub allow/deny lists (`command_executor.py`).

### Leftover risks (documented, unfixable in this scope)
- `langchain_config.api_key` is still plaintext; SEC-001 scrubs the environment but executed code still runs as the user and can read credential files; SSRF guard does not cover DNS rebinding (TOCTOU between check and connect).

---

## Verification Results

- Format/Lint (ruff): ✅ Pass ("All checks passed!")
- Type Check (pyright): ✅ Pass (0 errors, 0 warnings)
- Tests (pytest): ✅ Pass — 397 passed (260 at audit baseline; +137)
- Global gate: `make checkall` exit 0 at the final merged tree (`7d19ea0`). No `checkall-ci` target exists in this repo (its absence is tracked as ARC-012, left backlog per the plan).
- Per-issue validation: every issue individually verified at its merge (grep of the landed change / named test present / behavior test failing-on-old); no closed card was falsified by a later gate.

---

## Files Changed

47 commits, 121 files, +5,416/−3,101. Highlights:

- **Created**: `src/parllama/{paths,image_cache,net_guard,stream_controller,session_store}.py`, `src/parllama/settings/migration.py`, `src/parllama/screens/session_file_dialog.py`, `docs/guides/release.md`, tests: `test_file_validation_options.py`, `test_provider_key_vault.py`, `test_image_cache.py`, `test_settings_migration.py`, `test_import_side_effects.py`, `test_provider_model_fetch.py`, `test_update_manager.py`, `test_site_model_refresh.py`, `test_site_model_refresh_worker.py`, `test_chat_session_streaming.py`, `test_retry_utils.py`, `test_session_file_dialogs.py`, `test_input_with_history.py`, `test_net_guard.py`, `tests/fixtures/settings_flat_v1.json`
- **Heavily modified**: `settings_manager.py` (1,842→593), `chat_session.py` (1,174→850), `app.py`, `provider_manager.py`, `attachment_utils.py`, `command_executor.py`, `file_validator.py`, `options_view.py`, `secrets_manager.py`, ~35 further consumer modules
- **Removed from dependencies**: `requests`, `urllib3`, `pydantic-core`, `google-genai`, `types-requests`
- **Docs**: `README.md`, `project_design.md`, `docs/reference/configuration.md`, `docs/specs/issue-56-25-attachments.md`, `docs/DOCUMENTATION_STYLE_GUIDE.md`, `CLAUDE.md`; `docs/superpowers/` → `docs/archive/superpowers/`

---

## Incident During the Run

Test runs before this remediation were silently rewriting the real `~/.local/share/parllama/settings.json` (conftest bootstrapped against real data dirs). The Phase 2 gate converted it to the v2 format, which released parllama cannot read. **Fixed**: `tests/conftest.py` now isolates all data dirs; **restored**: the real file was rewritten as flat v1 (verified loading identically under old and new loaders) and a v2 backup kept at `settings.json.arc002-v2-backup`. **Caveat**: the restored content is what earlier test runs last wrote and may not match Paul's last deliberate settings; `settings.json.good` (2025-03) also exists in that directory.

---

## Follow-Up Cards Filed During the Run

All closed or queued on the board:
- Closed in-run: ARC-004 tail evaluation, QA-004 tail dedup, SEC-006 notes.
- Backlog (need decisions/design): "Migrate remaining ~20 stop-and-delegate App handlers" (ARC-004 remainder), "Fix ChatSession salt key mismatch (_salt vs __salt__)", "Fix make publish/test-publish under uv 0.12.1", "Decide OS-keychain storage for provider keys". Pre-existing ARC-012 (Makefile gate/checkall-ci) remains backlog per the plan's phase tables.

---

## Next Steps

1. Review the three manual-intervention items above.
2. Work is on branch `fix/audit-remediation` (local). Merge to `main` and push are separate, explicit steps.
3. Re-run `/audit` to get an updated AUDIT.md reflecting the new state.
