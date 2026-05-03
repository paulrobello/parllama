# Project Audit Report

> **Project**: PAR LLAMA
> **Date**: 2026-05-03
> **Stack**: Python 3.11+, Textual TUI, Pydantic, asyncio, Rich
> **Audited by**: Claude Code Audit System

---

## Executive Summary

PAR LLAMA is a feature-rich TUI application with a solid security foundation (encrypted secrets vault, atomic file operations, comprehensive validation) and good developer tooling. However, the codebase suffers from two systemic architectural issues: `app.py` has grown into a 1,094-line God Object that handles routing, job processing, and UI coordination, and every manager is instantiated as a module-level singleton, creating import-time side effects and making testing extremely difficult. The most critical security risk is that provider API keys are stored in plaintext in `settings.json` despite an existing encrypted vault system. Remediation of the top issues is estimated at 2–3 focused sprints, with the God Object decomposition being the highest-effort item.

### Issue Count by Severity

| Severity | Architecture | Security | Code Quality | Documentation | Total |
|----------|:-----------:|:--------:|:------------:|:-------------:|:-----:|
| Critical | 2 | 2 | 2 | 2 | **8** |
| High     | 4 | 3 | 5 | 4 | **16** |
| Medium   | 6 | 5 | 5 | 5 | **21** |
| Low      | 4 | 4 | 5 | 5 | **18** |
| **Total** | **16** | **14** | **17** | **16** | **63** |

---

## Critical Issues (Resolve Immediately)

### [SEC-001] Provider API Keys Stored in Plaintext in settings.json
- **Area**: Security
- **Location**: `src/parllama/settings_manager.py:631`
- **Description**: `save_settings_to_file()` calls `self.model_dump()` which serializes the entire Settings model including the `provider_api_keys` dictionary in plaintext to `~/.local/share/parllama/settings.json`. The application has a dedicated `SecretsManager` with AES-GCM encryption, but it is not used for these keys. File permissions on `settings.json` are not restricted (unlike `secrets.json` which gets `0o600`).
- **Impact**: Any local user or process that can read `settings.json` obtains all configured LLM provider API keys. Malware or a rogue process can exfiltrate keys to incur charges or access private data.
- **Remedy**: Route provider API keys through the existing `SecretsManager` vault. At minimum, exclude `provider_api_keys` from `model_dump()` output and apply `0o600` permissions to `settings.json`.

### [SEC-002] Command Execution via Shell with Incomplete Sanitization
- **Area**: Security
- **Location**: `src/parllama/execution/command_executor.py:247`
- **Description**: `_execute_foreground` and `_execute_background` use `asyncio.create_subprocess_shell()` which passes the full command string to the system shell. The escaping only handles single quotes and does not prevent `$()` command substitution, backtick execution, or newline injection. The security pattern checks are substring-based and can be bypassed with mixed case or shell metacharacters.
- **Impact**: An LLM response containing crafted shell metacharacters can achieve arbitrary command execution when interpolated into the command template.
- **Remedy**: Use `asyncio.create_subprocess_exec()` with a properly split argument list, or write content to temp files and pass the file path instead of interpolating into shell commands.

### [ARC-001] God Object: ParLlamaApp (1,094 lines) Violates Single Responsibility
- **Area**: Architecture
- **Location**: `src/parllama/app.py`
- **Description**: `ParLlamaApp` contains 55 message dispatch calls, 30+ `@on()` handlers, directly processes Ollama model jobs (pull, push, copy, create), manages the job queue, initializes the execution system, handles clipboard operations, and owns all manager singletons. It is simultaneously the application entry point, event bus, job processor, model operation coordinator, and execution orchestrator.
- **Impact**: Any change to model operations, chat routing, execution, or message dispatch requires modifying `app.py`. Creates merge conflicts, slows velocity, and makes the system fragile.
- **Remedy**: Extract `ModelJobProcessor` for model operations, `MessageRouter` for pub/sub logic, and `ExecutionCoordinator` for the execution system. The app should compose these, not implement them inline.

### [ARC-002] Module-Level Singleton Instantiation Creates Import-Time Side Effects
- **Area**: Architecture
- **Location**: `settings_manager.py:810`, `chat_manager.py:324`, `provider_manager.py:281`, `ollama_data_manager.py:415`, `secrets_manager.py:803`, `theme_manager.py:140`, `update_manager.py:68`, `memory_manager.py:159`
- **Description**: Every manager is instantiated at module import time as a module-level global. `Settings.__init__()` parses CLI arguments, creates directories, and loads from disk. Tests require a `pytest` guard in Settings to avoid parsing real CLI args.
- **Impact**: Importing any module that transitively imports `settings_manager` triggers CLI argument parsing and filesystem operations. Tests cannot easily swap settings without monkeypatching module globals. Circular import risk.
- **Remedy**: Adopt lazy initialization or a dependency injection container. Create an `AppContext` class that lazily constructs managers on first access. Remove the pytest guard and inject args explicitly.

### [QA-001] Magic Number in Error Parsing with ast.literal_eval
- **Area**: Code Quality
- **Location**: `src/parllama/chat_session.py:412-414`, `src/parllama/chat_session.py:447-449`
- **Description**: Error messages are parsed using a hardcoded offset `err_msg[18:]` followed by `ast.literal_eval`. The magic number 18 assumes a specific error message prefix format. If the format changes or the message is shorter than 18 characters, this raises `IndexError` or parses garbage data.
- **Impact**: Runtime crash on any error message shorter than 18 characters. Silent data corruption on format changes. Security risk from `ast.literal_eval` on untrusted input.
- **Remedy**: Use `json.loads()` with try/except instead. Strip the known prefix explicitly using `str.removeprefix()`. Add a length check before slicing.

### [QA-002] Duplicated Error Parsing Logic
- **Area**: Code Quality
- **Location**: `src/parllama/chat_session.py:411-414` and `src/parllama/chat_session.py:446-449`
- **Description**: The exact same error parsing block (magic number slicing + `ast.literal_eval`) is copy-pasted in two exception handlers within `send_chat()`.
- **Impact**: Same crash/security risk in two code paths. Any fix must be applied in both locations.
- **Remedy**: Extract into `_parse_llm_error(self, err_msg: str) -> str` and call from both catch blocks.

### [DOC-001] Missing CHANGELOG.md
- **Area**: Documentation
- **Location**: Missing at project root
- **Description**: No `CHANGELOG.md` file exists. Version history is embedded in the README "What's new" section covering v0.3.26 through v0.8.4. The README is bloated to 700+ lines with changelog content that belongs in its own file.
- **Impact**: Users and contributors cannot track changes in a standard, machine-readable format. Downstream tools cannot parse it.
- **Remedy**: Create `CHANGELOG.md`. Move version entries from README "What's new" to the new file. Keep only a link in the README.

### [DOC-002] help.md Out of Sync with Implemented Slash Commands
- **Area**: Documentation
- **Location**: `src/parllama/help.md`
- **Description**: The in-app help file is missing several implemented commands: `/session.provider`, `/session.import`, `/session.summarize`, `/session.clear_system_prompt`, `/history.clear`, `/remember`, `/forget`, `/memory.clear`, `/memory.status`. It also lists spurious entries (paths like `/.ollama`, `/usr`) that are not commands.
- **Impact**: Users cannot discover the Memory System or other features from within the application.
- **Remedy**: Regenerate help.md to match the command list in `chat_view.py:334-358`. Remove spurious entries. Ensure every command in `handle_command()` is listed.

---

## High Priority Issues

### [ARC-003] Settings Class is 810-Line God Class Mixing Configuration, CLI Parsing, and I/O
- **Area**: Architecture
- **Location**: `src/parllama/settings_manager.py`
- **Description**: `Settings` (Pydantic `BaseModel`) contains 100+ fields spanning model operations, provider config, UI theming, execution security, retry policies, and more. Its `__init__` parses CLI args, migrates legacy directories, creates directories, loads from disk, and applies env var overrides. `load_from_file` is a 250-line hand-written deserializer duplicating Pydantic's built-in capability.
- **Remedy**: Split into configuration groups using Pydantic nested models. Use Pydantic's serialization/deserialization. Move CLI parsing to `__main__.py` or `cli.py`.

### [ARC-004] Monolithic 539-Line Message Definitions File
- **Area**: Architecture
- **Location**: `src/parllama/messages/messages.py`
- **Description**: All 50+ message dataclass types in a single flat file spanning 7+ domains (model operations, session, chat, prompt, provider, execution, UI). Acts as a coupling magnet -- nearly every module imports from it.
- **Remedy**: Split into domain-specific modules (`model_messages.py`, `session_messages.py`, etc.). Keep `__init__.py` as a re-export barrel.

### [ARC-005] Manual pub/sub Duplicates Textual's Message Propagation
- **Area**: Architecture
- **Location**: `src/parllama/app.py:725-743`
- **Description**: Custom pub/sub system (`RegisterForUpdates` + `post_message_all`) coexists with Textual's `@on()` decorator-based handling. Two parallel dispatch mechanisms for the same messages.
- **Remedy**: Consolidate on Textual's message system. If broadcast semantics are needed, create a typed event bus leveraging Textual's message pump.

### [ARC-006] Tight Coupling Between app.py and Specific View Widgets
- **Area**: Architecture
- **Location**: `src/parllama/app.py` (lines 300, 322, 458, 675, 754-776, 1010-1016)
- **Description**: `ParLlamaApp` directly references `self.main_screen.local_view`, `.chat_view`, `.create_view`, etc. and manipulates their internal state. Contains 5-level-deep property chains (Law of Demeter violation).
- **Remedy**: Views should expose high-level methods. Use messages for coordination instead of direct widget access.

### [SEC-003] Execution Confirmation Can Be Bypassed by Configuration
- **Area**: Security
- **Location**: `src/parllama/app.py:956-960`
- **Description**: The confirmation check is `if requires_confirmation and settings.execution_require_confirmation`. Both `execution_require_confirmation` and `execution_enabled` are loaded from user-editable `settings.json`. A compromised settings file can silently enable arbitrary execution.
- **Remedy**: Make the confirmation requirement a hardcoded default that cannot be disabled via configuration for dangerous patterns.

### [SEC-004] User-Configurable Security Patterns Create Bypass Risk
- **Area**: Security
- **Location**: `src/parllama/settings_manager.py:207-213`, `src/parllama/execution/command_executor.py:113`
- **Description**: The `execution_security_patterns` list is loaded from `settings.json`. The critical patterns appended in `command_executor.py` are also incomplete (missing `chmod`, `wget`, `curl`, `nc`, `/etc/passwd`, etc.).
- **Remedy**: Merge user patterns with a comprehensive hardcoded denylist. User patterns should be additive only.

### [SEC-005] PARLLAMA_VAULT_KEY Environment Variable Exposes Vault Password
- **Area**: Security
- **Location**: `src/parllama/secrets_manager.py:74-76`
- **Description**: The SecretsManager reads the vault password from `PARLLAMA_VAULT_KEY` env var on startup. Environment variables are visible to child processes, `/proc/<pid>/environ`, and may be logged by monitoring tools.
- **Remedy**: Remove or deprecate the env var auto-unlock. Require interactive password entry or use a file descriptor/pipe.

### [QA-003] God Object: ParLlamaApp (Duplicate with ARC-001)
- **Area**: Code Quality
- **Location**: `src/parllama/app.py`
- **Description**: Same root issue as ARC-001 but from code quality perspective: 67 methods, 40+ `except Exception` blocks in one file, triplicated error handling in `do_create_model`.
- **Remedy**: Same as ARC-001. Extract coordinators.

### [QA-004] God Object: OptionsView (839 lines) with Massive if/elif Chains
- **Area**: Code Quality
- **Location**: `src/parllama/widgets/views/options_view.py:601-784`
- **Description**: `on_input_submitted` is a 115-line chain of `elif` branches mapping widget IDs to settings fields. Adding a new provider requires edits in 4+ places.
- **Remedy**: Build a declarative mapping from widget ID to (settings_field, type_converter, side_effect). Use a single dispatch loop.

### [QA-005] Excessive Generic Exception Catching (40+ instances)
- **Area**: Code Quality
- **Location**: Multiple files across the codebase
- **Description**: Over 40 instances of `except Exception as e`, 13 silently swallowing exceptions with bare `except Exception: pass`. `secrets_manager.py` alone has 13 broad-except blocks.
- **Remedy**: Catch specific exception types. Where broad catches are needed, always log with traceback. Audit all bare `except Exception: pass` blocks.

### [QA-006] Settings Class Mixing Configuration, Business Logic, and I/O (Duplicate with ARC-003)
- **Area**: Code Quality
- **Location**: `src/parllama/settings_manager.py`
- **Description**: Same root issue as ARC-003 from code quality perspective. The `fetch_and_cache_image` function (unrelated to settings) is defined at module level in this file.
- **Remedy**: Separate `Settings` (data model) from `SettingsManager` (I/O). Move `fetch_and_cache_image` to image utilities.

### [QA-007] Duplicated Model Creation Error Handling in app.py
- **Area**: Code Quality
- **Location**: `src/parllama/app.py:454-532`
- **Description**: `do_create_model` catches `ollama.ResponseError`, `ConnectError`, and generic `Exception` in three near-identical catch blocks, each constructing the same `LocalModelCreated` message with `success=False`.
- **Remedy**: Use a single try/except with a consolidated failure path.

### [DOC-003] Missing CONTRIBUTING.md
- **Area**: Documentation
- **Location**: Missing at project root
- **Description**: README has a brief "Contributing" section covering only pre-commit and linting. No PR process, code review expectations, branch naming, or commit conventions.
- **Remedy**: Create `CONTRIBUTING.md` with development setup, code style, PR checklist, and conventions.

### [DOC-004] README Data Directory Default is Misleading
- **Area**: Documentation
- **Location**: `README.md` (line 226, 484)
- **Description**: CLI help says data directory "Defaults to ~/.local/share/parllama" but Themes section says "~/.parllama/themes". The code auto-migrates from the old path, but docs still show it.
- **Remedy**: Update all references to consistently state `~/.local/share/parllama`. Document the auto-migration.

### [DOC-005] Docstrings Lack Parameter and Return Documentation
- **Area**: Documentation
- **Location**: 71 of 90 files with functions
- **Description**: Only 19 of 105 Python files contain Google-style `Args:`/`Returns:`/`Raises:` sections. The rest have bare one-line docstrings. Example: `provider_manager.get_model_name_fuzzy()` is documented as "Get model name fuzzy."
- **Remedy**: Add full Google-style docstrings to public functions. Prioritize managers and utility modules.

### [DOC-006] Bug Report Template Irrelevant for TUI Application
- **Area**: Documentation
- **Location**: `.github/ISSUE_TEMPLATE/bug_report.md`
- **Description**: Template asks for "Browser" and "Smartphone" info (generic GitHub default). Should ask for terminal emulator, Python version, Ollama version.
- **Remedy**: Customize for TUI: collect OS, terminal emulator, Python version, parllama version, provider, and reproduction steps.

---

## Medium Priority Issues

### Architecture

- **[ARC-007] Inconsistent file abstraction**: Raw `os.remove()` alongside `SecureFileOperations`. Add `delete_file` method to `SecureFileOperations`. (`chat_manager.py:148`, `settings_manager.py:698`)

- **[ARC-008] State management split**: `AppStateManager` exists but workers check `settings.shutting_down` directly. Replace with `state_manager.current_state == AppState.SHUTDOWN`. (`state_manager.py`, `settings_manager.py:688`, `chat_session.py:47`)

- **[ARC-009] Duplicate ProviderConfig dictionaries**: Three dicts (`provider_api_keys`, `provider_cache_hours`, `disabled_providers`) manually enumerate `LlmProvider` values. Create a `ProviderSettings` dataclass. (`settings_manager.py:88-134`)

- **[ARC-010] Missing ruff lint rules**: Only selects `E4`, `E5`, `E7`, `E9`, `F`, `W`, `UP`, `I`. Missing `C901` (complexity), `B` (bugbear), `SIM` (simplify). Add with `max-complexity = 15`. (`ruff.toml:42`)

- **[ARC-011] Mixed HTTP client libraries**: Both `httpx` and `requests` in dependencies. Standardize on `httpx`. (`pyproject.toml:64,66`)

- **[ARC-012] No abstraction boundary for par_ai_core**: Direct imports from `par_ai_core` across dozens of files. Create a `provider_adapter.py` facade. (Throughout codebase)

### Security

- **[SEC-006] Substring match for security patterns**: `if pattern in content_lower` can be bypassed with whitespace or mixed case. Use regex with word boundaries. (`command_executor.py:126`)

- **[SEC-007] Docker connection without TLS on Windows**: Connects to `tcp://127.0.0.1:2375` with `tls=False`. Use port 2376 with TLS or named pipes. (`docker_utils.py:54`)

- **[SEC-008] ast.literal_eval on untrusted error messages**: `ast.literal_eval(err_msg[18:])` on LLM provider error messages. Use `json.loads()` instead. (`chat_session.py:413, 448`)

- **[SEC-009] Insecure fallback write on secure write failure**: When `SecureFileOperations` fails, falls back to plain `json.dump()` with no validation. Remove fallback or raise exception. (`settings_manager.py:643-652`)

- **[SEC-010] Insecure random module for retry jitter**: `random.random()` used for jitter. Acceptable for current use but document as intentionally non-cryptographic. (`retry_utils.py:64`)

### Code Quality

- **[QA-008] Global singleton proliferation**: 7+ module-level singletons, 34 files import global `settings`. Makes testing and isolation difficult. (Throughout codebase)

- **[QA-009] 33 commented-out debug statements**: Scattered `# self.log_it(...)` calls. Remove and use proper logging levels. (`chat_session.py`, `chat_message_container.py`, others)

- **[QA-010] shared.py TODO and duplicated literal lists**: Same string list defined twice. Define once and derive both TypeAlias and list. (`messages/shared.py:7-43`)

- **[QA-011] Inconsistent error logging**: 17 `print()` calls in production code (invisible in TUI), plus `log_it()` and `logging` module used inconsistently. Standardize on `logging`. (`docker_utils.py`, `ollama_data_manager.py`, others)

- **[QA-012] Redundant `__ne__` implementation**: Python 3 auto-derives `__ne__` from `__eq__`. Remove dead code. (`chat_session.py:483-487`)

### Documentation

- **[DOC-007] README TOC non-ASCII character**: Trailing Unicode character on line 36 may break anchor links. Remove it.

- **[DOC-008] No architecture docs in docs/**: `project_design.md` lives at root, not in `docs/architecture/`. Move or symlink. (`docs/` directory)

- **[DOC-009] No troubleshooting documentation**: Common errors (Ollama not running, API key invalid, WSL issues) not organized as a reference. Create `docs/troubleshooting/common-errors.md`.

- **[DOC-010] README Videos section references v0.3.5**: Demo video is 5 major versions behind. Update or add disclaimer.

- **[DOC-011] release_announcement.md stale**: Advertises v0.7.0, current is v0.8.4. Update or remove.

---

## Low Priority / Improvements

### Architecture

- **[ARC-013] Commented-out features**: `SecretsView` and `RagView` tabs commented out in `main_screen.py`. Remove dead code or add feature flags.
- **[ARC-014] utils.py mixes concerns**: Contains CLI parsing, UI helpers, path utilities. Split into `cli.py` and `widgets/helpers.py`.
- **[ARC-015] Tests cover messaging infrastructure, not business logic**: No tests for `ChatSession`, `ChatManager`, `ProviderManager`, `Settings`, `SecureFileOperations` core logic.
- **[ARC-016] pyrightconfig.json targets Python 3.14 but minimum is 3.11**: Set `pythonVersion: "3.11"` to match minimum.

### Security

- **[SEC-011] Redundant path traversal check**: `if ".." in path_str` after `path.resolve()` is ineffective since resolved paths never contain `..`. Validate against base directory instead. (`file_validator.py:110`)
- **[SEC-012] Background processes not tracked**: `_execute_background` doesn't add to `_active_processes`, so `terminate_all_processes()` is always empty. (`command_executor.py:293-312`)
- **[SEC-013] Secure memory clear ineffective in CPython**: `_secure_clear_string` zeroes a copy, not the original immutable string. Known Python limitation. (`secrets_manager.py:196-217`)
- **[SEC-014] No integrity check on settings.json**: No HMAC or checksum on settings file. Tampered file could weaken security controls.

### Code Quality

- **[QA-013] 12 redefined-builtin suppressions for `id` parameter**: Textual framework convention; acceptable but could be project-wide pylint disable in `pyproject.toml`.
- **[QA-014] `_shutting_down` field on Pydantic BaseModel**: Should use `PrivateAttr(default=False)` instead of plain class attribute. (`settings_manager.py:48`)
- **[QA-015] ChatView docstring mismatch**: Says "viewing application logs" but class is the chat view. (`chat_view.py:84`)
- **[QA-016] LocalModelPushRequested docstring copy-paste error**: Says "model pull" but class handles push. (`messages.py:157`)
- **[QA-017] Legacy data migration runs at import time**: Migration code in `settings_manager.py` runs every import. Add migration marker check.

### Documentation

- **[DOC-012] README lacks architecture overview section**: Add 3-5 sentence summary with link to `project_design.md`.
- **[DOC-013] docs/ directory contains only images and style guide**: Missed opportunity for organized documentation.
- **[DOC-014] CLAUDE.md/AGENTS.md don't reference documentation style guide**: Add link to `docs/DOCUMENTATION_STYLE_GUIDE.md`.
- **[DOC-015] Theme section shows stale default path**: References `~/.parllama/themes` instead of `~/.local/share/parllama/themes`. (`README.md:484-486`)
- **[DOC-016] No CI status or coverage badges**: Add GitHub Actions and coverage badges to README.

---

## Detailed Findings

### Architecture & Design

The codebase follows a layered architecture with clear domain models (`ChatSession`, `ChatMessageContainer`, `ParllamaChatMessage`) and a typed message bus (50+ dataclass messages). The `SecureFileOperations` and `FileValidator` modules demonstrate genuine security investment. The `AppStateManager` implements proper state machine semantics with validated transitions and thread-safe locks.

However, two systemic patterns undermine the architecture: (1) the `ParLlamaApp` God Object centralizes too many responsibilities, and (2) module-level singletons create import-time side effects. These patterns make the codebase difficult to test, extend, and maintain. The Settings class compounds this by mixing Pydantic data modeling with CLI parsing, file I/O, and business logic in an 810-line class. The manual pub/sub system duplicates Textual's built-in message propagation, creating two parallel dispatch mechanisms that developers must understand.

The 50+ message types in a single flat file (`messages/messages.py`) act as a coupling magnet. The tight coupling between `app.py` and specific view widgets (including 5-level-deep property chains) means any UI restructuring breaks the app layer.

### Security Assessment

The project has a strong cryptographic foundation: the `SecretsManager` uses PBKDF2-HMAC-SHA256 with 600,000 iterations and AES-256-GCM for encryption. The `SecureFileOperations` layer implements atomic writes with `os.fsync()`, backup/restore, ZIP bomb detection, and comprehensive file validation. The `.gitignore` properly excludes sensitive paths.

The most critical security gap is that provider API keys bypass the encrypted vault entirely and are stored in plaintext in `settings.json`. Combined with the command execution system's use of `create_subprocess_shell()` with insufficient input sanitization, an attacker who can influence LLM output could execute arbitrary commands and exfiltrate stored credentials. The execution confirmation can be silently disabled via a compromised settings file. The `PARLLAMA_VAULT_KEY` environment variable undermines the vault architecture by exposing the password in process memory.

No hardcoded secrets were found in source code, and no unsafe deserialization (`pickle`, unsafe `yaml.load`) was detected.

### Code Quality

The codebase has consistent type annotations enforced via pyright, good linting discipline with ruff, and solid developer tooling (Makefile with standard targets). The message bus refactor to typed Textual messages is a genuine improvement.

The primary code quality concern is error handling: 40+ `except Exception` blocks, 13 silently swallowing exceptions. The `ast.literal_eval` with magic number slicing in `chat_session.py` is a correctness bug that will crash on any error message shorter than 18 characters. The same fragile parsing is duplicated in two locations. The `OptionsView` uses 115-line if/elif chains that are error-prone to maintain.

Test coverage is estimated at <15%. The 18 test files (2,413 LOC vs 19,783 production LOC) primarily cover messaging infrastructure, not business logic. Key untested areas include `app.py` (1,094 LOC), `settings_manager.py` (810 LOC), `chat_session.py` (687 LOC), all widget classes, and the entire `execution/` package.

### Documentation Review

The project has a comprehensive README covering installation, CLI arguments, environment variables, and multiple quick-start workflows. The `DOCUMENTATION_STYLE_GUIDE.md` is excellent with practical templates. The `project_design.md` provides detailed architecture documentation. 104 of 105 Python files contain docstrings.

The most critical documentation gap is the in-app help (`help.md`) being significantly out of sync with implemented slash commands. Users cannot discover the Memory System, Template Execution, or session management features from within the application. The missing `CHANGELOG.md` forces version history into the README, bloating it to 700+ lines. The bug report template asks for browser/smartphone information irrelevant to a TUI application.

---

## Remediation Roadmap

### Immediate Actions (Before Next Deployment)
1. SEC-001: Route provider API keys through SecretsManager vault
2. SEC-002: Replace `create_subprocess_shell` with `create_subprocess_exec`
3. QA-001/QA-002: Fix `ast.literal_eval` error parsing in `chat_session.py`

### Short-term (Next 1-2 Sprints)
1. ARC-001: Extract `ModelJobProcessor` and `MessageRouter` from `app.py`
2. ARC-002: Migrate singletons to lazy initialization
3. ARC-003: Split Settings into nested Pydantic models
4. SEC-003/SEC-004: Harden execution confirmation and security patterns
5. DOC-001: Create `CHANGELOG.md`
6. DOC-002: Regenerate `help.md`

### Long-term (Backlog)
1. ARC-004: Split `messages.py` into domain modules
2. ARC-005: Consolidate pub/sub on Textual's message system
3. QA-005: Audit and fix all broad exception catches
4. ARC-015: Add business logic test coverage
5. DOC-005: Add full Google-style docstrings to public APIs
6. DOC-003: Create `CONTRIBUTING.md`

---

## Positive Highlights

1. **Strong cryptographic vault implementation**: PBKDF2-HMAC-SHA256 with 600K iterations and AES-256-GCM. Exceeds OWASP minimums.

2. **Comprehensive file validation system**: `SecureFileOperations` implements atomic writes with fsync, backup/restore, path traversal prevention, extension whitelisting, ZIP bomb detection, and filename sanitization.

3. **Proper state machine in AppStateManager**: Validated state transitions, thread-safe locks per concern, and `can_start_operation` guard. Well-designed.

4. **Excellent documentation style guide**: `DOCUMENTATION_STYLE_GUIDE.md` is thorough with practical templates for guides, architecture notes, and troubleshooting docs.

5. **Consistent type annotations**: All public APIs typed, enforced by pyright in CI. Good foundation for maintainability.

6. **Well-structured domain model hierarchy**: `ChatMessageContainer` base class with clean protocol implementation (`__iter__`, `__len__`, `__getitem__`). Good use of Composite pattern.

7. **Good developer tooling**: Makefile with all standard targets, `uv` for dependency management, ruff + pyright configuration, thorough CLAUDE.md.

8. **MessageSink pattern**: Clean abstraction enabling non-Textual objects to emit messages through the app's message pump. Pragmatic solution to the "managers are not widgets" problem.

---

## Audit Confidence

| Area | Files Reviewed | Confidence |
|------|---------------|-----------|
| Architecture | 30+ source files, all managers, screens, views | High |
| Security | All crypto, execution, validation, and auth code | High |
| Code Quality | All files >500 LOC, test directory, lint config | High |
| Documentation | All .md files, docstring sampling across 105 files | High |

---

## Remediation Plan

> This section is generated by the audit and consumed directly by `/fix-audit`.
> It pre-computes phase assignments and file conflicts so the fix orchestrator
> can proceed without re-analyzing the codebase.

### Phase Assignments

#### Phase 1 -- Critical Security (Sequential, Blocking)
<!-- Issues that must be fixed before anything else. -->

| ID | Title | File(s) | Severity |
|----|-------|---------|----------|
| SEC-001 | Provider API keys stored in plaintext | `src/parllama/settings_manager.py` | Critical |
| SEC-002 | Command execution via shell injection | `src/parllama/execution/command_executor.py` | Critical |

#### Phase 2 -- Critical Architecture (Sequential, Blocking)
<!-- Issues that restructure the codebase; must complete before Code Quality fixes. -->

| ID | Title | File(s) | Severity | Blocks |
|----|-------|---------|----------|--------|
| ARC-001 | God Object ParLlamaApp | `src/parllama/app.py` | Critical | QA-003, QA-007, ARC-005, ARC-006 |
| ARC-002 | Module-level singleton instantiation | 8 manager files | Critical | QA-008, ARC-015 |
| ARC-003 | Settings God class | `src/parllama/settings_manager.py` | High | QA-006, ARC-009 |

#### Phase 3 -- Parallel Execution
<!-- All remaining work, safe to run concurrently by domain. -->

**3a -- Security (remaining)**

| ID | Title | File(s) | Severity |
|----|-------|---------|----------|
| SEC-003 | Execution confirmation bypass | `src/parllama/app.py` | High |
| SEC-004 | User-configurable security patterns | `src/parllama/execution/command_executor.py` | High |
| SEC-005 | PARLLAMA_VAULT_KEY env var | `src/parllama/secrets_manager.py` | High |
| SEC-006 | Substring security pattern matching | `src/parllama/execution/command_executor.py` | Medium |
| SEC-007 | Docker without TLS on Windows | `src/parllama/docker_utils.py` | Medium |
| SEC-008 | ast.literal_eval on untrusted input | `src/parllama/chat_session.py` | Medium |
| SEC-009 | Insecure fallback write | `src/parllama/settings_manager.py` | Medium |
| SEC-010 | Insecure random for jitter | `src/parllama/retry_utils.py` | Medium |

**3b -- Architecture (remaining)**

| ID | Title | File(s) | Severity |
|----|-------|---------|----------|
| ARC-004 | Monolithic messages.py | `src/parllama/messages/messages.py` | High |
| ARC-005 | Manual pub/sub duplication | `src/parllama/app.py` | High |
| ARC-006 | Tight coupling to view widgets | `src/parllama/app.py`, `src/parllama/screens/main_screen.py` | High |
| ARC-007 | Inconsistent file abstraction | `src/parllama/chat_manager.py`, `src/parllama/settings_manager.py` | Medium |
| ARC-008 | State management split | `src/parllama/state_manager.py`, `src/parllama/settings_manager.py` | Medium |
| ARC-009 | Duplicate ProviderConfig dicts | `src/parllama/settings_manager.py` | Medium |
| ARC-010 | Missing ruff lint rules | `ruff.toml` | Medium |
| ARC-011 | Mixed HTTP client libraries | `pyproject.toml` | Medium |
| ARC-012 | No abstraction for par_ai_core | Multiple files | Medium |

**3c -- Code Quality (all)**

| ID | Title | File(s) | Severity |
|----|-------|---------|----------|
| QA-001 | Magic number in error parsing | `src/parllama/chat_session.py` | Critical |
| QA-002 | Duplicated error parsing logic | `src/parllama/chat_session.py` | Critical |
| QA-003 | God Object ParLlamaApp | `src/parllama/app.py` | High |
| QA-004 | God Object OptionsView | `src/parllama/widgets/views/options_view.py` | High |
| QA-005 | Excessive generic exception catching | Multiple files | High |
| QA-006 | Settings mixing concerns | `src/parllama/settings_manager.py` | High |
| QA-007 | Duplicated model creation errors | `src/parllama/app.py` | High |
| QA-008 | Global singleton proliferation | Multiple files | Medium |
| QA-009 | 33 commented-out debug statements | Multiple files | Medium |
| QA-010 | shared.py duplicated lists | `src/parllama/messages/shared.py` | Medium |
| QA-011 | Inconsistent error logging | Multiple files | Medium |
| QA-012 | Redundant __ne__ implementation | `src/parllama/chat_session.py` | Medium |

**3d -- Documentation (all)**

| ID | Title | File(s) | Severity |
|----|-------|---------|----------|
| DOC-001 | Missing CHANGELOG.md | (new file) | Critical |
| DOC-002 | help.md out of sync | `src/parllama/help.md` | Critical |
| DOC-003 | Missing CONTRIBUTING.md | (new file) | High |
| DOC-004 | README data directory misleading | `README.md` | High |
| DOC-005 | Docstrings lack param/return docs | 71 source files | High |
| DOC-006 | Bug report template irrelevant | `.github/ISSUE_TEMPLATE/bug_report.md` | High |
| DOC-007 | README TOC non-ASCII character | `README.md` | Medium |
| DOC-008 | No architecture docs in docs/ | `docs/` directory | Medium |
| DOC-009 | No troubleshooting documentation | (new file) | Medium |
| DOC-010 | README videos section outdated | `README.md` | Medium |
| DOC-011 | release_announcement.md stale | `release_announcement.md` | Medium |

### File Conflict Map
<!-- Files touched by issues in multiple domains. Fix agents must read current file state
     before editing -- a prior agent may have already changed these. -->

| File | Domains | Issues | Risk |
|------|---------|--------|------|
| `src/parllama/app.py` | Security + Architecture + Code Quality | SEC-003, ARC-001, ARC-005, ARC-006, QA-003, QA-007 | Read before edit |
| `src/parllama/settings_manager.py` | Security + Architecture + Code Quality + Documentation | SEC-001, SEC-009, ARC-003, ARC-009, QA-006, DOC-005 | Read before edit |
| `src/parllama/execution/command_executor.py` | Security + Code Quality | SEC-002, SEC-004, SEC-006 | Read before edit |
| `src/parllama/chat_session.py` | Security + Architecture + Code Quality | SEC-008, ARC-008, QA-001, QA-002, QA-012 | Read before edit |
| `src/parllama/secrets_manager.py` | Architecture + Security | ARC-002, SEC-005, SEC-013 | Read before edit |
| `src/parllama/chat_manager.py` | Architecture + Code Quality | ARC-002, ARC-007, QA-008 | Read before edit |
| `src/parllama/messages/messages.py` | Architecture + Code Quality | ARC-004, QA-016 | Read before edit |
| `README.md` | Documentation (multiple) | DOC-004, DOC-007, DOC-010, DOC-012, DOC-015, DOC-016 | Read before edit |

### Blocking Relationships
<!-- Explicit dependency declarations from audit agents.
     Format: [blocker issue] -> [blocked issue] -- reason -->

- ARC-001 -> QA-003, QA-007: ParLlamaApp split reorganizes code that QA-003 and QA-007 also target
- ARC-001 -> ARC-005, ARC-006: pub/sub consolidation and widget decoupling depend on app.py being split first
- ARC-002 -> QA-008, ARC-015: singleton migration must complete before test coverage and singleton cleanup work
- ARC-003 -> QA-006, ARC-009: Settings refactor must complete before code quality and provider config work targeting settings_manager.py
- SEC-001 -> QA-006: SEC-001 restructures API key serialization, changing model_dump output shape that QA-006 also targets
- SEC-002 -> SEC-004, SEC-006: switching from create_subprocess_shell to create_subprocess_exec changes the entire command pipeline
- ARC-004 -> ARC-005: message domain partitioning informs which handlers belong to which coordinator

### Dependency Diagram

```mermaid
graph TD
    P1["Phase 1: Critical Security"]
    P2["Phase 2: Critical Architecture"]
    P3a["Phase 3a: Security (remaining)"]
    P3b["Phase 3b: Architecture (remaining)"]
    P3c["Phase 3c: Code Quality"]
    P3d["Phase 3d: Documentation"]
    P4["Phase 4: Verification"]

    P1 --> P2
    P2 --> P3a & P3b & P3c & P3d
    P3a & P3b & P3c & P3d --> P4

    ARC001["ARC-001"] -->|blocks| QA003["QA-003"]
    ARC001["ARC-001"] -->|blocks| QA007["QA-007"]
    ARC002["ARC-002"] -->|blocks| QA008["QA-008"]
    ARC003["ARC-003"] -->|blocks| QA006["QA-006"]
    SEC001["SEC-001"] -->|blocks| QA006["QA-006"]
    SEC002["SEC-002"] -->|blocks| SEC004["SEC-004"]
    ARC004["ARC-004"] -->|blocks| ARC005["ARC-005"]
