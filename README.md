# HVE Forge

## About HyperVelocity Forge

### The Problem

Engineering teams today are flying blind. Velocity, quality, and security signals are scattered across GitHub repositories, CI/CD workflows, and Microsoft 365 collaboration tools — and nobody has time to manually stitch them together. DORA and SPACE metrics promise to quantify engineering effectiveness, but collecting and acting on them requires heroic effort: pulling data from multiple systems, correlating it, and then figuring out what to do next.

Worse, improvement is **reactive**. Teams only discover bottlenecks after a release slips, a security vulnerability ships, or a sprint retrospective surfaces the same problems for the third time. There is no continuous, AI-driven loop that observes, analyzes, and suggests improvements *before* things go wrong.

### Our Solution

**HyperVelocity Forge** (`hve-forge`) is a CLI or GitHub Workflow first tool that gives development teams a unified, AI-powered view of their engineering health — and then *acts on it*. It combines data from GitHub (repos, issues, PRs, workflows, code) and Microsoft 365 (Teams, Outlook, Planner, SharePoint) via MCP servers to surface actionable insights at three distinct levels:

| Level | Scope | What it does |
|-------|-------|--------------|
| **Macro** | Org / cross-repo | Run `hve-forge` locally with GitHub Copilot CLI to aggregate project and M365 data into a unified engineering dashboard — DORA metrics (deployment frequency, lead time, change failure rate, MTTR), SPACE dimensions (satisfaction, performance, activity, communication, efficiency), and team collaboration signals. |
| **Repository** | Single repo | Ship GitHub workflows that continuously analyze repository health using data already in GitHub — PR cycle time, issue staleness, test coverage trends, dependency freshness — and automatically suggest enhancements via issues or PR comments. |
| **Workflow** | Single run | Analyze the output of a CI/CD workflow or a coding-agent run and recommend concrete improvements to speed, quality, and security for the next iteration. |

### How We Leverage MCP

HyperVelocity Forge is built on the **Model Context Protocol (MCP)** to connect the dots between the tools teams already use:

- **GitHub MCP** — pulls repository activity, issues, PRs, commits, workflow runs, and code search results to compute engineering metrics and detect patterns.
- **WorkIQ MCP** — connects to Microsoft 365 to correlate collaboration signals (meeting load, async communication patterns, Planner tasks) with code delivery data, giving a holistic view of team effectiveness.
- **FabricIQ MCP** *(work in progress)* — connects to [Microsoft Fabric](https://www.microsoft.com/en-us/microsoft-fabric) to store, clean, and extract insights from SDLC-related data at scale. By landing raw signals from GitHub and M365 into a Fabric lakehouse, teams can run advanced analytics, build custom Power BI dashboards over historical engineering metrics, and apply Fabric's built-in AI capabilities (Copilot in Fabric, ML models) to detect trends that short-lived API queries miss — e.g., long-term velocity drift, seasonal quality patterns, or cross-team dependency bottlenecks.

By combining these data sources through MCP, insights emerge that no single system can provide alone: *"This team's PR review time spiked the same week their meeting load doubled"* or *"Deployments that skip the staging workflow have a 3x higher change failure rate."*

### Agentic Workflows Integration

We started small — a focused CLI that pulls metrics locally — but we quickly saw the opportunity to make improvement **continuous and autonomous**. With the launch of [GitHub Agentic Workflows](https://github.github.com/gh-aw/), we integrated agentic automation directly into the repository lifecycle:

- **Scheduled analysis workflows** written in natural-language Markdown that run daily to triage issues, assess PR quality, analyze CI failures, and surface improvement suggestions — powered by Copilot, Claude, or Codex as AI engines.
- **Safe, guardrailed automation** that uses safe outputs and sandboxed execution so teams can trust that agentic improvements stay within controlled boundaries.
- **Continuous AI** that augments existing deterministic CI/CD pipelines with intelligent, context-aware recommendations — the repository literally gets better every morning.

### Who This Is For

**Development teams** who want to implement **hypervelocity engineering** — the practice of systematically measuring, analyzing, and accelerating software delivery while maintaining quality and security at scale. Whether you're a tech lead trying to understand where your team's time goes, a platform engineer optimizing CI/CD pipelines, or an engineering manager tracking DORA metrics for your org, HVE Forge meets you where you work: in the terminal and in GitHub.

### Built With

- **[Copilot CLI SDK](https://github.com/github/copilot-sdk)** — powers the local AI-assisted analysis and natural-language interactions.
- **GitHub MCP, WorkIQ MCP & FabricIQ MCP** *(FabricIQ in progress)* — provide the data backbone via Model Context Protocol.
- **[GitHub Agentic Workflows](https://github.github.com/gh-aw/)** — deliver continuous, autonomous repository improvement.
- **Python + Typer** — for a fast, type-safe CLI experience.

> *"Start small, expand later"* — we began with a single CLI command and a clear problem. MCP connections and Agentic Workflows let us scale the solution from a local tool to a continuous, org-wide engineering intelligence platform.

---

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

### Commands

#### `retrospective`

Run a team retrospective using GitHub Copilot with MCP servers. This command analyzes recent repository activity (commits, PRs, issues) and generates a structured retrospective report.

```bash
uv run hve-forge retrospective
```

**Options:**

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--prompt` | `-p` | Custom prompt for the retrospective | Built-in default prompt |
| `--model` | `-m` | Model to use for the retrospective | `gpt-4o` |
| `--github-token` | | GitHub token for authentication | `GITHUB_TOKEN` env var |
| `--verbose` | `-v` | Show detailed tool call output | Off |

**Examples:**

```bash
# Run a retrospective with default settings
uv run hve-forge retrospective

# Run with verbose output to see detailed tool calls
uv run hve-forge retrospective --verbose

# Use a custom prompt and model
uv run hve-forge retrospective --prompt "Focus on the last sprint" --model gpt-4o

# Provide a GitHub token explicitly
uv run hve-forge retrospective --github-token ghp_xxxxxxxxxxxx
```

> **Tip:** Use `--verbose` (or `-v`) to see each MCP tool invocation and its result — useful for debugging or understanding what data the AI is pulling.

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
