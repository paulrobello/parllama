# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Model Sort Selector**: Sort local and site models by size or name via dropdown in both Local and Site model tabs. Sort preference persists across restarts (#50).
- **Template Picker for Ctrl+R**: When pressing Ctrl+R on a message with no auto-matching template (e.g. non-fenced content), a modal dialog now lists all enabled templates for manual selection instead of silently failing (#65).

### Fixed

- **Provider Disable Checkbox**: Fixed "Unknown provider" toast error when toggling provider disable checkboxes — provider name casing mismatch between widget ID and enum lookup.
- **`/add.image` Spinner Bug**: Fixed infinite spinner when `/add.image` is used without a prompt — now validates that a prompt is provided before executing. Also added support for quoted filenames with single or double quotes.

### Security

- **SEC-002**: Eliminated shell injection vulnerability in command executor. Content from LLM responses is now always written to temp files — never interpolated into shell commands. Replaced `create_subprocess_shell` with `create_subprocess_exec` + `shlex.split`.

### Architecture

- **ARC-001**: Extracted `ModelJobProcessor` and `ExecutionCoordinator` from `ParLlamaApp`, reducing app.py from 1,094 to ~759 lines (31%)
- **ARC-002**: Converted all 8 module-level singletons to lazy initialization via `__getattr__`, eliminating import-time side effects and removing the pytest guard
- **ARC-003**: Decomposed Settings (810-line God Class) into 10 Pydantic config group models with full backward compatibility
- **ARC-004**: Split monolithic `messages.py` (539 lines, 70 message types) into 8 domain modules with re-export barrel
- **ARC-005**: Extracted inline pub/sub logic into dedicated `EventBus` class

### Code Quality

- **QA-001/QA-002**: Replaced magic number `err_msg[18:]` + `ast.literal_eval` with `_parse_llm_error()` using `json.loads()`, deduplicated in two call sites
- **QA-004**: Replaced 115-line `on_input_submitted` if/elif chain in OptionsView with declarative mapping tables
- **QA-005**: Narrowed 44 `except Exception` instances to specific types across 24 files; eliminated all 13 silent `except Exception: pass` blocks
- **QA-007**: Consolidated three identical catch blocks in `do_create_model` into single failure path

### Documentation

- **DOC-001**: Created `CHANGELOG.md` with version history from v0.2.5 through v0.8.4; trimmed README What's New section
- **DOC-002**: Regenerated `help.md` with all 9 missing slash commands, removed spurious entries
- **DOC-003**: Created `CONTRIBUTING.md` with development setup, code style, PR process, and conventions

## [0.8.4] - 2025-05-01

### Fixed

- **First Run Fix**: Fixed error message appearing on first run when `settings.json` doesn't exist yet (#69)
- **Python 3.11 Compatibility Fix**: Fixed syntax errors when running on Python 3.11
  - Replaced PEP 695 `type` statement syntax (Python 3.12+) with `TypeAlias` annotations
  - Replaced PEP 695 generic class syntax `class Foo[T]` with `TypeVar`-based generics
  - Parenthesized multi-exception `except` clauses for Python 3.11 compatibility
  - Set ruff target version to `py311` to match `requires-python` and prevent future regressions

## [0.8.3] - 2025-04-28

### Fixed

- **Textual Revert**: Reverted to prior version of textual package due to bug in newer version

## [0.8.2] - 2025-04-25

### Changed

- **Updated Dependencies**: Upgraded core dependencies to latest versions
  - langchain 1.0.7 (from 0.3.27)
  - textual 6.6.0 (from 6.1.0)
  - par-ai-core 0.5.3 (from 0.3.2)
  - ollama 0.6.1 (from 0.5.1)
  - Multiple security and infrastructure library updates
- **Dependency Cleanup**: Optimized `uv.lock` file for better performance

## [0.8.1] - 2025-04-20

### Added

- **Python 3.14 Support**: Added full compatibility for Python 3.14 while maintaining backward compatibility with Python 3.11+
  - Updated project configuration to support Python 3.11, 3.12, 3.13, and 3.14
  - CI/CD pipelines default to Python 3.14 for builds and testing
  - Code quality tools (ruff, pyright) configured to target Python 3.14
  - Modernized codebase to use Python 3.14 features (type statement, generic type parameters)

### Changed

- **Updated Dependencies**: Refreshed dependency lock file with latest compatible versions

## [0.8.0] - 2025-04-15

### Added

- **Python 3.13 Support**: Added compatibility for Python 3.13 while maintaining support for Python 3.11 and 3.12
  - Updated project configuration to support Python 3.11, 3.12, and 3.13
  - CI/CD pipelines default to Python 3.13 for builds and testing
  - Code quality tools (ruff, pyright) configured for Python 3.11 minimum compatibility
  - Dependency updates for multi-version Python support

### Changed

- **Updated Dependencies**: Refreshed dependency lock file with latest compatible versions

## [0.7.0] - 2025-04-01

### Changed

- **Configurable Security Patterns**: Enhanced execution security with user-customizable safety controls
  - Security patterns now configurable through Options page instead of hardcoded
  - Default patterns focused only on filesystem safety (`rm`, `del`, `mkfs`, `dd`, `/dev/`)
  - User can add/remove security patterns via comma-separated input field
  - Changes take effect immediately without requiring application restart
  - Critical security patterns (`sudo`, `exec`, `eval`) always remain protected
  - Fixes false positives that were blocking legitimate Python f-string usage

- **Improved Execution Result Formatting**: Cleaner display of code execution results
  - CLI parameter scripts now show as `python -c <script>` instead of messy escaped code
  - Executed code displayed in clean syntax-highlighted blocks for short scripts (10 lines or fewer)
  - Smart language detection for proper syntax highlighting (Python, JavaScript, Bash)
  - Intelligent command truncation for long commands with logical break points
  - File-based executions remain unchanged for optimal readability

## [0.6.1] - 2025-03-15

### Fixed

- **gRPC Warning Suppression**: Fixed annoying gRPC ALTS warnings on startup
  - Configured Google Generative AI to use REST transport instead of gRPC
  - Eliminates "All log messages before absl::InitializeLog() is called" warnings
  - Resolves "ALTS creds ignored" and "Not running on GCP" messages
  - Provides clean startup experience without affecting functionality
- **Memory View Fix**: Fixed crash in Memory tab due to missing TextArea widget ID
  - Added missing `id="memory_textarea"` attribute to prevent `AttributeError`
  - Ensures proper widget identification for memory management functionality

## [0.6.0] - 2025-03-01

### Added

- **Memory System**: Comprehensive persistent user context across all conversations
  - Dedicated Memory tab for managing personal information and preferences
  - Automatic memory injection as first message in new conversations
  - AI-powered memory updates via slash commands (`/remember`, `/forget`, `/memory.status`, `/memory.clear`)
  - Real-time synchronization between slash commands and Memory tab interface
  - Secure local storage with comprehensive file validation

## [0.5.0] - 2025-02-15

### Added

- **Template Execution System**: Added secure code execution feature with configurable command allowlists
  - Execute code snippets and commands directly from chat messages using Ctrl+R
  - Comprehensive security controls including command validation and content filtering
  - Configurable execution settings in Options tab (execution enabled toggle, allowed commands list)
  - Support for multiple programming languages and command-line tools
  - Settings now properly persist between application sessions

## [0.4.0] - 2025-02-01

### Fixed

- Fixed type checking issue with `ClickableLabel` widget accessing incorrect property
- Changed from accessing `renderable` to `content` property to align with Textual API

## [0.3.28] - 2025-01-20

### Changed

- Fix some outdated dependencies

### Fixed

- Fixed delete chat tab on macOS sometimes not working
- Streamlined markdown fences

## [0.3.27] - 2025-01-15

### Fixed

- Fixed Fabric import due to upstream library changes (PR #61)
- Added better Markdown streaming support thanks to upstream library changes
- Fixed chat tab send bar layout issues
- Fixed thinking fence not showing correctly sometimes

## [0.3.26] - 2025-01-10

### Added

- **Enhanced Fabric Import with Progress Tracking**
- **Increased File Size Limits for Better Usability**
- Enhanced URL validation to preserve case sensitivity for case-sensitive endpoints
- Implemented comprehensive file validation and security system
- Added `FileValidator` class with security checks for:
  - File size limits (configurable per file type: images, JSON, ZIP)
  - Extension validation against allowed lists
  - Path security to prevent directory traversal attacks
  - Content validation for JSON, images, and ZIP files
  - ZIP bomb protection with compression ratio checks
- Created `SecureFileOperations` utility
- Added new file validation configuration tools
- Added validation for quantization levels with list of valid options
- Added specific error messages for quantization requirements (F16/F32 base models)
- Implemented comprehensive configuration management system
  - Added 24 configurable settings for timers, timeouts, and UI behavior
- Implemented centralized state management system
- Enhanced provider cache system with configurable per-provider durations
- Added comprehensive provider disable functionality with checkboxes for all AI providers
  - Disabled providers are excluded from model refresh operations and UI dropdowns to prevent timeouts
- Added automatic local model list refresh after successful model downloads

### Changed

- Improved security logging and error handling throughout secrets management
- Enhanced security for all JSON operations
- Updated UI to clarify quantization requirements in model creation
- Updated quantization documentation to clarify native Ollama support vs Docker requirements
- Major code quality and type safety improvements

### Fixed

- Improved error handling for model creation with better error messages
- Fixed memory leaks using `WeakSet` for subscriptions and bounded job queue
- Fixed critical threading race conditions in job processing system
- Enhanced exception handling across all job methods (pull, push, copy, create)
- Improved error logging and user notifications for all job operations
- Added state transition logging for debugging threading issues
- Fixed delete key on Mac sometimes not working

## [0.3.25] - 2024-12-20

### Fixed

- Fixed tab in input history causing a crash
- Fixed create new model causing crash
- Fix hard coded config loading

## [0.3.24] - 2024-12-15

### Added

- Sort local models by size then name
- Add support for http basic auth when setting base url for providers

## [0.3.23] - 2024-12-10

### Fixed

- Fixed possible crash on local model details dialog

## [0.3.22] - 2024-12-05

### Added

- Add option to import markdown files into session via slash command `/session.import` and hot key Ctrl+I
- Added slash command `/session.summarize` to summarize and replace entire conversation into a single 1 paragraph message

### Changed

- Tree-sitter package no longer installed by default

## [0.3.21] - 2024-11-28

### Added

- Added LLM config options for OpenAI Reasoning Effort, and Anthropic's Reasoning Token Budget
- Better display in chat area for "thinking" portions of a LLM response

### Changed

- Data and cache locations now use proper XDG locations

### Fixed

- Fix error caused by LLM response containing certain markup
- Fixed issues caused by deleting a message from chat while it's still being generated by the LLM

## [0.3.20] - 2024-11-20

### Fixed

- Fix unsupported format string error caused by missing temperature setting

## [0.3.19] - 2024-11-15

### Fixed

- Fix missing package error caused by previous update

## [0.3.18] - 2024-11-10

### Changed

- Updated dependencies for some major performance improvements

## [0.3.17] - 2024-11-05

### Added

- Added "thinking" fence for deepseek thought output
- Much better support for displaying max input context size

### Fixed

- Fixed crash on startup if Ollama is not available
- Fixed markdown display issues around fences

## [0.3.16] - 2024-10-28

### Added

- Added providers xAI, OpenRouter, Deepseek and LiteLLM

## [0.3.15] - 2024-10-22

### Added

- Added copy button to the fence blocks in chat markdown for easy code copy

## [0.3.14] - 2024-10-18

### Fixed

- Fix crash caused by some models having missing fields in model file

## [0.3.13] - 2024-10-15

### Fixed

- Handle clipboard errors

## [0.3.12] - 2024-10-10

### Fixed

- Fixed bug where changing providers that have custom URLs would break other providers
- Fixed bug where changing Ollama base URL would cause connection timed out

## [0.3.11] - 2024-10-05

### Added

- Added ability to set max context size for Ollama and other providers that support it
- Limited support for LLamaCpp running in OpenAI Mode
- Added ability to cycle through fences in selected chat message and copy to clipboard with `ctrl+shift+c`
- Added theme selector

### Changed

- Updated core AI library and dependencies

### Fixed

- Various bug fixes and performance improvements
- Fixed crash due to upstream library update

## [0.3.10] - 2024-09-28

### Added

- Images are now stored in chat session JSON files
- Added API key checks for online providers

### Fixed

- Fixed crash issues on fresh installs

## [0.3.9] - 2024-09-22

### Added

- Image support for models that support them using `/add.image` slash command
- Add history support for both single and multi line input modes

### Fixed

- Fixed crash on models that don't have a license
- Fixed last model used not getting used with new sessions

## [0.3.8] - 2024-09-15

### Added

- New session config panel docked to right side of chat tab (more settings coming soon)

### Changed

- Major rework of core to support providers other than Ollama
- Better counting of tokens (still not always 100% accurate)

### Added

- Added support for the following online providers: OpenAI, Anthropic, Groq, Google

## [0.3.7] - 2024-09-10

### Fixed

- Fix for possible crash when there is more than one model loaded into Ollama

## [0.3.6] - 2024-09-05

### Added

- Added option to save chat input history and set its length
- Added cache for Fabric import to speed up subsequent imports

### Fixed

- Fixed tab switch issue on startup

## [0.3.5] - 2024-09-01

### Added

- Added first time launch welcome
- Added Options tab which exposes more options than are available via command line switches
- Added option to auto check for new versions
- Added ability to import custom prompts from [Fabric](https://github.com/danielmiessler/fabric)
- Added toggle between single and multi line input (Note: auto complete and command history features not available in multi line edit mode)

## [0.3.4] - 2024-08-25

### Added

- Added custom prompt library support (Work in progress)
- Added CLI option and environment var to enable auto naming of sessions using LLM (Work in progress)
- Added tokens per second stats to session info line on chat tab

### Fixed

- Fixed app crash when it can't contact Ollama server for PS info
- Fixed slow startup when you have a lot of models available locally
- Fixed slow startup and reduced memory utilization when you have many / large chats
- Fixed session unique naming bug where it would always add a "1" to the session name
- Fixed app sometimes slowing down during LLM generation
- Issue where some footer items are not clickable has been resolved by a library PAR LLAMA depends on

### Changed

- Major rework of internal message handling

## [0.3.3] - 2024-08-20

### Added

- Added ability to edit existing messages. Select message in chat list and press "e" to edit, then "escape" to exit edit mode
- Add chat input history access via up / down arrow while chat message input has focus
- Added `/session.system_prompt` command to set system prompt in current chat tab

## [0.3.2] - 2024-08-15

### Added

- Chat tabs now have a session info bar with info like current / max context length
- Added conversation stop button to abort LLM response
- Added ability to delete messages from session
- More model details displayed on model detail screen

### Changed

- Better performance when changing session params on chat tab

### Fixed

- Ollama ps stats bar now works with remote connections except for CPU / GPU percentages which Ollama's API does not provide

## [0.3.1] - 2024-08-10

### Added

- Add chat tabs to support multiple sessions
- Added CLI option to prevent saving chat history to disk

### Changed

- Renamed / namespaced chat slash commands for better consistency and grouping

### Fixed

- Fixed application crash when Ollama binary not found

## [0.3.0] - 2024-08-05

### Added

- Added chat history panel and management to chat page

## [0.2.51] - 2024-08-01

### Fixed

- Fix missing dependency in package

## [0.2.5] - 2024-07-28

### Added

- Added slash commands to chat input
- Added ability to export chat to markdown file

### Changed

- Ctrl+C on local model list will jump to chat tab and select currently selected local model
- Ctrl+C on chat tab will copy selected chat message

[0.8.4]: https://github.com/paulrobello/parllama/releases/tag/v0.8.4
[0.8.3]: https://github.com/paulrobello/parllama/releases/tag/v0.8.3
[0.8.2]: https://github.com/paulrobello/parllama/releases/tag/v0.8.2
[0.8.1]: https://github.com/paulrobello/parllama/releases/tag/v0.8.1
[0.8.0]: https://github.com/paulrobello/parllama/releases/tag/v0.8.0
[0.7.0]: https://github.com/paulrobello/parllama/releases/tag/v0.7.0
[0.6.1]: https://github.com/paulrobello/parllama/releases/tag/v0.6.1
[0.6.0]: https://github.com/paulrobello/parllama/releases/tag/v0.6.0
[0.5.0]: https://github.com/paulrobello/parllama/releases/tag/v0.5.0
[0.4.0]: https://github.com/paulrobello/parllama/releases/tag/v0.4.0
[0.3.28]: https://github.com/paulrobello/parllama/releases/tag/v0.3.28
[0.3.27]: https://github.com/paulrobello/parllama/releases/tag/v0.3.27
[0.3.26]: https://github.com/paulrobello/parllama/releases/tag/v0.3.26
[0.3.25]: https://github.com/paulrobello/parllama/releases/tag/v0.3.25
[0.3.24]: https://github.com/paulrobello/parllama/releases/tag/v0.3.24
[0.3.23]: https://github.com/paulrobello/parllama/releases/tag/v0.3.23
[0.3.22]: https://github.com/paulrobello/parllama/releases/tag/v0.3.22
[0.3.21]: https://github.com/paulrobello/parllama/releases/tag/v0.3.21
[0.3.20]: https://github.com/paulrobello/parllama/releases/tag/v0.3.20
[0.3.19]: https://github.com/paulrobello/parllama/releases/tag/v0.3.19
[0.3.18]: https://github.com/paulrobello/parllama/releases/tag/v0.3.18
[0.3.17]: https://github.com/paulrobello/parllama/releases/tag/v0.3.17
[0.3.16]: https://github.com/paulrobello/parllama/releases/tag/v0.3.16
[0.3.15]: https://github.com/paulrobello/parllama/releases/tag/v0.3.15
[0.3.14]: https://github.com/paulrobello/parllama/releases/tag/v0.3.14
[0.3.13]: https://github.com/paulrobello/parllama/releases/tag/v0.3.13
[0.3.12]: https://github.com/paulrobello/parllama/releases/tag/v0.3.12
[0.3.11]: https://github.com/paulrobello/parllama/releases/tag/v0.3.11
[0.3.10]: https://github.com/paulrobello/parllama/releases/tag/v0.3.10
[0.3.9]: https://github.com/paulrobello/parllama/releases/tag/v0.3.9
[0.3.8]: https://github.com/paulrobello/parllama/releases/tag/v0.3.8
[0.3.7]: https://github.com/paulrobello/parllama/releases/tag/v0.3.7
[0.3.6]: https://github.com/paulrobello/parllama/releases/tag/v0.3.6
[0.3.5]: https://github.com/paulrobello/parllama/releases/tag/v0.3.5
[0.3.4]: https://github.com/paulrobello/parllama/releases/tag/v0.3.4
[0.3.3]: https://github.com/paulrobello/parllama/releases/tag/v0.3.3
[0.3.2]: https://github.com/paulrobello/parllama/releases/tag/v0.3.2
[0.3.1]: https://github.com/paulrobello/parllama/releases/tag/v0.3.1
[0.3.0]: https://github.com/paulrobello/parllama/releases/tag/v0.3.0
[0.2.51]: https://github.com/paulrobello/parllama/releases/tag/v0.2.51
[0.2.5]: https://github.com/paulrobello/parllama/releases/tag/v0.2.5
