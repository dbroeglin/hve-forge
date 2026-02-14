"""Retrospective command using GitHub Copilot SDK."""

from __future__ import annotations

import asyncio
import os
import sys

import typer
from copilot import CopilotClient, MCPLocalServerConfig, MCPServerConfig, SessionConfig, SessionEvent

RETROSPECTIVE_SYSTEM_MESSAGE = (
    "You are a retrospective facilitator for a software development team. "
    "Your role is to analyze the current repository using the available MCP tools "
    "(GitHub API, Context7, WorkIQ) and generate a comprehensive team retrospective. "
    "Focus on: recent activity (commits, PRs, issues), what went well, what could be improved, "
    "action items, and team collaboration patterns. "
    "Use the GitHub MCP server to pull real data about the repository. "
    "Present findings in a structured retrospective format."
)

DEFAULT_PROMPT = (
    "Perform a retrospective for this repository. "
    "Analyze recent commits, pull requests, issues, and overall project activity. "
    "Structure the retrospective with these sections:\n"
    "1. **Summary**: Overview of recent activity\n"
    "2. **What Went Well**: Positive highlights from recent work\n"
    "3. **What Could Be Improved**: Areas for improvement\n"
    "4. **Action Items**: Concrete next steps\n"
    "5. **Team Collaboration**: Observations about teamwork and contribution patterns\n"
    "Use the available tools to gather real data from the repository."
)


def _build_mcp_servers() -> dict[str, MCPServerConfig]:
    """Build MCP server configurations for the retrospective session."""
    servers: dict[str, MCPServerConfig] = {}

    servers["github"] = MCPLocalServerConfig(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={"GITHUB_PERSONAL_ACCESS_TOKEN": os.environ.get("GITHUB_TOKEN", "")},
    )

    servers["context7"] = MCPLocalServerConfig(
        command="npx",
        args=["-y", "@upstash/context7-mcp@latest"],
    )

    return servers


def _build_session_config(model: str) -> SessionConfig:
    """Build the session configuration for a retrospective."""
    config: SessionConfig = {
        "model": model,
        "system_message": {"content": RETROSPECTIVE_SYSTEM_MESSAGE},
        "mcp_servers": _build_mcp_servers(),
        "streaming": True,
    }
    return config


async def _run_retrospective(
    prompt: str,
    model: str,
    github_token: str | None,
) -> None:
    """Run a retrospective session using the Copilot SDK."""
    client = CopilotClient({"github_token": github_token} if github_token else None)
    await client.start()

    try:
        session_config = _build_session_config(model)
        session = await client.create_session(session_config)

        done = asyncio.Event()
        error_message: list[str] = []

        def on_event(event: SessionEvent) -> None:
            if event.type.value == "assistant.message_delta":
                delta = event.data.delta_content or ""
                sys.stdout.write(delta)
                sys.stdout.flush()
            elif event.type.value == "assistant.message":
                sys.stdout.write("\n")
                sys.stdout.flush()
            elif event.type.value == "session.error":
                error_content = getattr(event.data, "content", str(event.data))
                error_message.append(str(error_content))
                done.set()
            elif event.type.value == "session.idle":
                done.set()

        session.on(on_event)
        await session.send({"prompt": prompt})
        await done.wait()
        await session.destroy()

        if error_message:
            typer.echo(f"\nError during retrospective: {error_message[0]}", err=True)
            raise typer.Exit(code=1)
    finally:
        await client.stop()


def retrospective(
    prompt: str | None = typer.Option(None, "--prompt", "-p", help="Custom prompt for the retrospective."),
    model: str = typer.Option("gpt-4o", "--model", "-m", help="Model to use for the retrospective."),
    github_token: str | None = typer.Option(
        None,
        "--github-token",
        envvar="GITHUB_TOKEN",
        help="GitHub token for authentication. Defaults to GITHUB_TOKEN env var.",
    ),
) -> None:
    """Run a team retrospective using GitHub Copilot with MCP servers."""
    effective_prompt = prompt or DEFAULT_PROMPT
    typer.echo("Starting retrospective analysis...\n")
    asyncio.run(_run_retrospective(effective_prompt, model, github_token))
