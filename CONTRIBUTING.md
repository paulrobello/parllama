# Contributing to PAR LLAMA

This guide covers how to set up a development environment, follow project conventions, and submit changes.

## Table of Contents

- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Development Workflow](#development-workflow)
- [Commit Conventions](#commit-conventions)
- [Pull Request Process](#pull-request-process)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [License](#license)

## Development Setup

### Prerequisites

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/) package manager
- GNU-compatible `make`
- [Ollama](https://ollama.com/download) (for local testing with LLM features)
- Git

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Clone and set up

```bash
git clone https://github.com/paulrobello/parllama.git
cd parllama
make setup
```

This runs `uv lock` and `uv sync` to create the virtual environment and install all dependencies.

### Install pre-commit hooks

Pre-commit runs formatting, linting, and type checking before each commit.

```bash
uv tool install pre-commit
pre-commit install
```

Run against all files to verify the setup:

```bash
pre-commit run --all-files
```

### Run the application

```bash
make dev    # Development mode with hot reload
make run    # Normal mode
```

## Code Style

| Convention | Standard |
|---|---|
| Python version | 3.11+ (configured in `ruff.toml` as `py311`) |
| Type annotations | Required on all functions and methods |
| Docstring style | Google-style with `Args`, `Returns`, `Raises` sections |
| Line length | 120 characters |
| Formatter | ruff (`make format`) |
| Linter | ruff (`make lint`) |
| Type checker | pyright (`make typecheck`) |
| Import sorting | ruff isort (combined-as-imports enabled) |

### Ruff configuration

The project uses ruff with the following rule selections in `ruff.toml`:

- `E4`, `E5`, `E7`, `E9` -- pycodestyle errors
- `F` -- Pyflakes
- `W` -- pycodestyle warnings
- `UP` -- pyupgrade
- `I` -- isort

Docstring code formatting is enabled.

## Development Workflow

### Before every commit

Run the full check suite. This is also what CI runs:

```bash
make checkall
```

This is equivalent to running each step individually:

```bash
make format    # Reformat with ruff
make lint      # Lint with ruff (--fix)
make typecheck # Static type check with pyright
```

If `make checkall` passes locally, the pre-commit hooks and CI pipeline will pass.

### Common make targets

| Target | Command | Description |
|---|---|---|
| `make setup` | `uv lock && uv sync` | First-time setup |
| `make dev` | `textual run --dev` | Run with hot reload |
| `make test` | `pytest` | Run the test suite |
| `make checkall` | format + lint + typecheck | Full quality gate |
| `make package` | `uv build` | Build distributable package |

## Commit Conventions

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
type(scope): short description

Optional longer description.
```

Common types:

| Type | Use for |
|---|---|
| `feat` | New features |
| `fix` | Bug fixes |
| `docs` | Documentation changes |
| `style` | Formatting, no logic change |
| `refactor` | Code restructuring without behavior change |
| `test` | Adding or updating tests |
| `chore` | Build, tooling, or dependency updates |
| `perf` | Performance improvements |

Examples:

```
feat(chat): add export to HTML format
fix(provider): resolve timeout on model list refresh
docs(readme): update installation instructions
```

## Pull Request Process

1. **Fork the repository** and create a branch from `main`.

2. **Branch naming**: Use descriptive, lowercase, hyphen-separated names.

   ```
   feat/chat-html-export
   fix/provider-timeout
   docs/contributing-guide
   ```

3. **Make your changes** and ensure `make checkall` passes.

4. **Add tests** for new utilities and data models when practical. UI component changes may rely on manual testing.

5. **Update documentation** if your change affects user-facing behavior, configuration, or public APIs.

6. **Open a pull request** against the `main` branch.

   - Include a clear description of what the PR does and why.
   - Reference any related issues.
   - Confirm that `make checkall` passes.

7. **Code review**: Maintainers will review the PR. Address feedback by pushing additional commits.

### What maintainers check

- `make checkall` passes with no errors
- Pre-commit hooks pass
- New functionality has tests where practical
- Public APIs have Google-style docstrings
- Documentation is updated for user-facing changes
- No unnecessary scope creep beyond the PR purpose

## Project Structure

```
src/parllama/
  app.py              # Textual application entry point
  screens/            # Full-screen layouts (main, save session, import)
  widgets/             # Reusable UI components (chat, model lists, inputs)
    views/             # Tab-based views (chat, local models, site models, options)
  messages/            # Typed event dataclasses for component communication
  coordinators/        # Job processing and event coordination
  execution/           # Template execution and command running
  models/              # Data models and session configuration
  validators/          # File validation and security checks
  settings/            # Settings persistence and management
  dialogs/             # Modal dialog widgets
  prompt_utils/        # Prompt parsing and Fabric import
  themes/              # Theme loading and management
tests/                 # pytest test suite
```

Key source files:

| File | Purpose |
|---|---|
| `src/parllama/app.py` | Application class, message routing, job dispatch |
| `src/parllama/settings_manager.py` | Settings model, CLI parsing, persistence |
| `src/parllama/provider_manager.py` | Provider model caching and refresh |
| `src/parllama/chat_session.py` | Chat session logic and LLM communication |
| `src/parllama/secure_file_ops.py` | Atomic file operations with validation |
| `src/parllama/secrets_manager.py` | Encrypted credential storage |

## Testing

### Run the test suite

```bash
make test
```

### Run with coverage

```bash
make coverage
```

### Where to add tests

Test files live in the `tests/` directory at the project root. Name files with the `test_` prefix.

Add tests for:

- New utility functions and data models
- Message routing and event handling
- Provider and manager logic
- File validation and security operations

UI components (widgets, views, screens) are harder to unit test. Manual testing is acceptable for these.

### Test configuration

The test suite uses `pytest` with `conftest.py` for shared fixtures. The project uses the standard `tests/` layout.

## License

By contributing to PAR LLAMA, you agree that your contributions will be licensed under the [MIT License](LICENSE).
