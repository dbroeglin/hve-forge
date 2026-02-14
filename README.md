# HVE Forge

## Prerequisites

- **Python 3.12+**
- **[UV](https://docs.astral.sh/uv/)** — a fast Python package and project manager

### Installing UV

If you don't have UV installed yet, install it with one of the following methods:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip
pip install uv

# Or via Homebrew
brew install uv
```

After installation, verify it works:

```bash
uv --version
```

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/dbroeglin/hve-forge.git
cd hve-forge
```

### 2. Install dependencies

UV manages the virtual environment and dependencies for you. A single command sets everything up:

```bash
uv sync
```

This will:
- Download and install the correct Python version (if needed)
- Create a `.venv` virtual environment in the project directory
- Install all project and development dependencies

### 3. Run the project

```bash
uv run hve-forge
```

### Running with `uvx` (no install needed)

Once published to PyPI, anyone can run the tool without installing it:

```bash
uvx hve-forge
```

To test `uvx` locally during development:

```bash
uvx --from . hve-forge
```

## Development

### Project Structure

```
hve-forge/
├── src/
│   └── hve_forge/       # Main package source code
│       ├── __init__.py
│       └── main.py
├── tests/               # Test suite
│   ├── __init__.py
│   └── test_main.py
├── pyproject.toml       # Project metadata & tool configuration
├── .python-version      # Pinned Python version
└── uv.lock              # Locked dependency versions
```

### Running Tests

```bash
uv run pytest
```

With verbose output:

```bash
uv run pytest -v
```

### Linting & Formatting

The project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Check for lint errors
uv run ruff check .

# Auto-fix lint errors
uv run ruff check . --fix

# Format code
uv run ruff format .

# Check formatting without modifying files
uv run ruff format . --check
```

### Type Checking

The project uses [mypy](https://mypy.readthedocs.io/) in strict mode:

```bash
uv run mypy src/
```

### Adding Dependencies

```bash
# Add a runtime dependency
uv add <package>

# Add a development dependency
uv add --group dev <package>

# Remove a dependency
uv remove <package>
```

### Running all checks

Before committing, run the full suite of checks:

```bash
uv run ruff check .
uv run ruff format . --check
uv run mypy src/
uv run pytest
```

## Publishing to PyPI

Once the package is ready for release, publish it to PyPI so users can run it via `uvx hve-forge`:

```bash
# Build the package
uv build

# Publish to PyPI (requires a PyPI API token)
uv publish
```

To publish to TestPyPI first:

```bash
uv publish --index https://test.pypi.org/simple/
```

After publishing, anyone with UV can run the tool directly:

```bash
uvx hve-forge
```

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
