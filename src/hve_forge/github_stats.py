"""GitHub statistics command using GitHub Copilot SDK."""

from __future__ import annotations

import asyncio
import json
import os
import stat
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

import typer
from copilot import CopilotClient, MCPLocalServerConfig, MCPServerConfig, SessionConfig, SessionEvent
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text


def _ensure_copilot_cli_executable() -> None:
    """Ensure the bundled Copilot CLI binary has execute permissions.

    The github-copilot-sdk wheel may not preserve executable bits on the
    bundled binary. This function detects and fixes that before the client
    tries to spawn the process.
    """
    # Resolve relative to the copilot package, not our own package
    import copilot as _copilot_pkg

    pkg_dir = Path(_copilot_pkg.__file__).parent
    if sys.platform == "win32":
        binary_path = pkg_dir / "bin" / "copilot.exe"
    else:
        binary_path = pkg_dir / "bin" / "copilot"

    if binary_path.exists() and not os.access(binary_path, os.X_OK):
        binary_path.chmod(binary_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


GITHUB_STATS_SYSTEM_MESSAGE = (
    "You are a GitHub statistics analyst. "
    "Your role is to analyze the current repository using the available GitHub MCP tools "
    "and generate a comprehensive statistics report. "
    "Focus on: repository activity metrics (stars, forks, watchers), contributor statistics, "
    "commit frequency, pull request metrics, issue metrics, and code evolution trends. "
    "Use the GitHub MCP server to pull real data about the repository. "
    "Present findings in a structured, easy-to-read format with clear sections and data visualizations "
    "where appropriate."
)

DEFAULT_PROMPT = (
    "Analyze the GitHub statistics for this repository. "
    "Provide a comprehensive overview with the following sections:\n"
    "1. **Repository Overview**: Basic stats (stars, forks, watchers, language, size)\n"
    "2. **Recent Activity**: Summary of recent commits, PRs, and issues (last 30 days)\n"
    "3. **Contributor Statistics**: Top contributors and their activity patterns\n"
    "4. **Pull Request Metrics**: PR volume, merge time, review patterns\n"
    "5. **Issue Metrics**: Issue creation rate, resolution time, open vs closed\n"
    "6. **Code Evolution**: Language distribution, repository growth trends\n"
    "Use the available GitHub tools to gather real data from the repository."
)


def _build_mcp_servers() -> dict[str, MCPServerConfig]:
    """Build MCP server configurations for the GitHub stats session."""
    servers: dict[str, MCPServerConfig] = {}

    servers["github"] = MCPLocalServerConfig(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={"GITHUB_PERSONAL_ACCESS_TOKEN": os.environ.get("GITHUB_TOKEN", "")},
    )

    return servers


def _build_session_config(model: str) -> SessionConfig:
    """Build the session configuration for GitHub statistics analysis."""
    config: SessionConfig = {
        "model": model,
        "system_message": {"content": GITHUB_STATS_SYSTEM_MESSAGE},
        "mcp_servers": _build_mcp_servers(),
        "streaming": True,
    }
    return config


def _format_tool_arguments(arguments: object) -> str:
    """Format tool call arguments for display."""
    if arguments is None:
        return ""
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
            return json.dumps(parsed, indent=2)
        except (json.JSONDecodeError, TypeError):
            return arguments
    if isinstance(arguments, dict):
        return json.dumps(arguments, indent=2)
    return str(arguments)


def _truncate(text: str, max_length: int = 500) -> str:
    """Truncate text to a maximum length, appending an ellipsis if needed."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "…"


def _tool_label(event: SessionEvent) -> str:
    """Derive a human-readable label for a tool event."""
    tool_name = event.data.tool_name or "unknown"
    mcp_server = event.data.mcp_server_name or ""
    mcp_tool = event.data.mcp_tool_name or ""
    if mcp_server and mcp_tool:
        return f"{mcp_server}/{mcp_tool}"
    if mcp_tool:
        return mcp_tool
    return tool_name


def _make_event_handler(  # noqa: C901 — event dispatch is inherently branchy
    console: Console,
    done: asyncio.Event,
    error_message: list[str],
    message_buffer: list[str],
    *,
    verbose: bool = False,
    live: Live | None = None,
) -> Callable[[SessionEvent], None]:
    """Create the session event handler with rich console output.

    Args:
        console: Rich console instance for output.
        done: Event to signal when the session is finished.
        error_message: List to collect error messages.
        message_buffer: Buffer collecting assistant message deltas.
        verbose: When *True*, show detailed panels for every event.
            When *False* (default), show only a spinner with the current
            activity and the final assistant message.
        live: A :class:`rich.live.Live` context used in non-verbose mode
            to update the spinner in-place.

    Returns:
        A callback suitable for ``session.on()``.
    """

    def on_event(event: SessionEvent) -> None:  # noqa: C901
        event_type = event.type.value

        # ── Tool execution events ─────────────────────────────────────
        if event_type == "tool.execution_start":
            label = _tool_label(event)
            if verbose:
                args_text = _format_tool_arguments(event.data.arguments)
                body = Text(args_text, style="dim") if args_text else Text("(no arguments)", style="dim italic")
                console.print(
                    Panel(
                        body,
                        title=f"[bold cyan]⚙  Calling tool:[/bold cyan] [yellow]{label}[/yellow]",
                        border_style="cyan",
                        expand=False,
                    )
                )
            elif live is not None:
                live.update(Spinner("dots", text=Text.from_markup(f"  Calling [yellow]{label}[/yellow]…")))

        elif event_type == "tool.execution_complete":
            label = _tool_label(event)
            if verbose:
                result_text = ""
                if event.data.result is not None:
                    result_text = _truncate(event.data.result.content)
                body = Text(result_text, style="dim") if result_text else Text("(no output)", style="dim italic")
                console.print(
                    Panel(
                        body,
                        title=f"[bold green]✓  Tool complete:[/bold green] [yellow]{label}[/yellow]",
                        border_style="green",
                        expand=False,
                    )
                )
            elif live is not None:
                live.update(Spinner("dots", text=Text.from_markup(f"  [green]✓[/green] {label}")))

        elif event_type == "tool.execution_progress":
            progress = event.data.progress_message or ""
            if progress and verbose:
                console.print(f"  [dim]⏳ {progress}[/dim]")

        elif event_type == "tool.execution_partial_result":
            partial = event.data.partial_output or ""
            if partial and verbose:
                console.print(f"  [dim]… partial: {_truncate(partial, 200)}[/dim]")

        # ── Assistant message streaming ───────────────────────────────
        elif event_type == "assistant.message_delta":
            delta = event.data.delta_content or ""
            message_buffer.append(delta)

        elif event_type == "assistant.message":
            full_text = "".join(message_buffer)
            message_buffer.clear()
            if full_text.strip():
                if not verbose and live is not None:
                    live.stop()
                console.print()
                console.print(Markdown(full_text))
                console.print()

        # ── Assistant turn lifecycle ──────────────────────────────────
        elif event_type == "assistant.turn_start":
            if verbose:
                console.print(Panel("[bold]Assistant is thinking…[/bold]", border_style="blue", expand=False))
            elif live is not None:
                live.update(Spinner("dots", text="  Thinking…"))

        elif event_type == "assistant.turn_end":
            if verbose:
                console.print(Panel("[bold]Turn complete[/bold]", border_style="blue", expand=False))

        # ── Session lifecycle ─────────────────────────────────────────
        elif event_type == "session.start":
            if verbose:
                console.print("[bold green]Session started[/bold green]")

        elif event_type == "session.error":
            error_content = (
                getattr(event.data, "content", None) or getattr(event.data, "message", None) or str(event.data)
            )
            error_message.append(str(error_content))
            console.print(f"[bold red]Session error:[/bold red] {error_content}")
            done.set()

        elif event_type == "session.idle":
            if not verbose and live is not None:
                live.stop()
            done.set()

    return on_event


async def _run_github_stats(
    prompt: str,
    model: str,
    github_token: str | None,
    *,
    verbose: bool = False,
) -> None:
    """Run a GitHub statistics analysis session using the Copilot SDK."""
    console = Console()

    _ensure_copilot_cli_executable()
    client = CopilotClient({"github_token": github_token} if github_token else None)
    await client.start()

    try:
        session_config = _build_session_config(model)
        session = await client.create_session(session_config)

        done = asyncio.Event()
        error_message: list[str] = []
        message_buffer: list[str] = []

        live: Live | None = None
        if not verbose:
            live = Live(Spinner("dots", text="  Initialising…"), console=console, transient=True)
            live.start()

        on_event = _make_event_handler(
            console,
            done,
            error_message,
            message_buffer,
            verbose=verbose,
            live=live,
        )

        session.on(on_event)
        await session.send({"prompt": prompt})
        await done.wait()

        if live is not None and live.is_started:
            live.stop()

        await session.destroy()

        if error_message:
            console.print(f"\n[bold red]Error during GitHub stats analysis:[/bold red] {error_message[0]}")
            raise typer.Exit(code=1)
    finally:
        await client.stop()


def github_stats(
    prompt: str | None = typer.Option(None, "--prompt", "-p", help="Custom prompt for the GitHub statistics."),
    model: str = typer.Option("gpt-4o", "--model", "-m", help="Model to use for the analysis."),
    github_token: str | None = typer.Option(
        None,
        "--github-token",
        envvar="GITHUB_TOKEN",
        help="GitHub token for authentication. Defaults to GITHUB_TOKEN env var.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed tool call output."),
) -> None:
    """Review GitHub statistics for the repository using GitHub Copilot with MCP servers."""
    console = Console()
    effective_prompt = prompt or DEFAULT_PROMPT
    console.print(Panel("[bold]Starting GitHub statistics analysis…[/bold]", border_style="magenta", expand=False))
    asyncio.run(_run_github_stats(effective_prompt, model, github_token, verbose=verbose))
