# Copilot Instructions for HVE Forge

## Build & Run

This project uses [UV](https://docs.astral.sh/uv/) for all Python tooling — do not use `pip`, `venv`, or `python` directly. Always prefix commands with `uv run`.

```bash
uv sync                  # Install/update dependencies
uv run hve-forge         # Run the CLI
```

## Testing

```bash
uv run pytest            # Run full test suite
uv run pytest tests/test_main.py::test_main  # Run a single test
uv run pytest -k "pattern"                   # Run tests matching a pattern
```

## Linting, Formatting & Type Checking

```bash
uv run ruff check .              # Lint
uv run ruff check . --fix        # Lint with auto-fix
uv run ruff format .             # Format
uv run mypy src/                 # Type check (strict mode)
```

Run all checks before committing:

```bash
uv run ruff check . && uv run ruff format . --check && uv run mypy src/ && uv run pytest
```

## Code Conventions

- **Type annotations are required on all functions** — mypy runs in strict mode.
- **Line length: 120 characters** (configured in `pyproject.toml`).
- **Ruff lint rules**: `E, F, I, N, W, UP, B, A, SIM, TCH` — includes import sorting (`I`), naming (`N`), `flake8-bugbear` (`B`), and type-checking imports (`TCH`).
- Use `from __future__ import annotations` or the `TCH` pattern for type-checking-only imports.
- All modules and public functions should have docstrings (see existing code for style).

## Architecture

- **`src/hve_forge/`** — main package using the `src` layout. Entry point is `main:main`, registered as the `hve-forge` console script.
- **`tests/`** — pytest test suite. Tests import from `hve_forge` directly (the package is installed in dev mode via `uv sync`).
- **Build system**: Hatchling. Wheel packages `src/hve_forge`.

## Dependencies

```bash
uv add <package>              # Runtime dependency
uv add --group dev <package>  # Dev dependency
```
