"""Tests for hve_forge.retrospective."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from hve_forge.main import app
from hve_forge.retrospective import (
    DEFAULT_PROMPT,
    RETROSPECTIVE_SYSTEM_MESSAGE,
    _build_mcp_servers,
    _build_session_config,
)


def test_retrospective_command_appears_in_help() -> None:
    """Test that the retrospective command is listed in CLI help."""
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "retrospective" in result.stdout


def test_retrospective_help() -> None:
    """Test that the retrospective command has proper help text."""
    runner = CliRunner()
    result = runner.invoke(app, ["retrospective", "--help"])
    assert result.exit_code == 0
    assert "prompt" in result.stdout
    assert "model" in result.stdout
    assert "github" in result.stdout


def test_build_mcp_servers() -> None:
    """Test that MCP server configurations are built correctly."""
    servers = _build_mcp_servers()
    assert "github" in servers
    assert "context7" in servers

    github_server = servers["github"]
    assert github_server["command"] == "npx"
    assert "@modelcontextprotocol/server-github" in github_server["args"]

    context7_server = servers["context7"]
    assert context7_server["command"] == "npx"
    assert "@upstash/context7-mcp@latest" in context7_server["args"]


def test_build_session_config() -> None:
    """Test that session configuration is built correctly."""
    config = _build_session_config("gpt-4o")
    assert config["model"] == "gpt-4o"
    assert config["streaming"] is True
    assert "mcp_servers" in config
    assert config["system_message"]["content"] == RETROSPECTIVE_SYSTEM_MESSAGE


def test_build_session_config_custom_model() -> None:
    """Test that session configuration respects custom model."""
    config = _build_session_config("claude-sonnet-4.5")
    assert config["model"] == "claude-sonnet-4.5"


@patch("hve_forge.retrospective.asyncio.run")
def test_retrospective_default_prompt(mock_asyncio_run: MagicMock) -> None:
    """Test that retrospective uses the default prompt when none is provided."""
    runner = CliRunner()
    result = runner.invoke(app, ["retrospective"])
    assert result.exit_code == 0
    assert "Starting retrospective analysis..." in result.stdout
    mock_asyncio_run.assert_called_once()
    call_args = mock_asyncio_run.call_args[0][0]
    # The coroutine was passed to asyncio.run; verify it was created
    assert call_args is not None


@patch("hve_forge.retrospective.asyncio.run")
def test_retrospective_custom_prompt(mock_asyncio_run: MagicMock) -> None:
    """Test that retrospective uses a custom prompt when provided."""
    runner = CliRunner()
    result = runner.invoke(app, ["retrospective", "--prompt", "custom prompt"])
    assert result.exit_code == 0
    assert "Starting retrospective analysis..." in result.stdout
    mock_asyncio_run.assert_called_once()


@patch("hve_forge.retrospective.asyncio.run")
def test_retrospective_custom_model(mock_asyncio_run: MagicMock) -> None:
    """Test that retrospective uses a custom model when provided."""
    runner = CliRunner()
    result = runner.invoke(app, ["retrospective", "--model", "gpt-5"])
    assert result.exit_code == 0
    mock_asyncio_run.assert_called_once()


@patch("hve_forge.retrospective.CopilotClient")
def test_run_retrospective_creates_session(mock_client_class: MagicMock) -> None:
    """Test that _run_retrospective creates a Copilot session with proper config."""
    import asyncio

    from hve_forge.retrospective import _run_retrospective

    mock_client = AsyncMock()
    mock_client_class.return_value = mock_client

    mock_session = MagicMock()
    mock_session.send = AsyncMock()
    mock_session.destroy = AsyncMock()
    mock_client.create_session = AsyncMock(return_value=mock_session)

    # Simulate the session going idle when `on` is called.
    def fake_on(callback: object) -> None:
        event = MagicMock()
        event.type.value = "session.idle"
        callback(event)  # type: ignore[operator]

    mock_session.on = fake_on

    asyncio.run(_run_retrospective(DEFAULT_PROMPT, "gpt-4o", None))

    mock_client.start.assert_awaited_once()
    mock_client.create_session.assert_awaited_once()
    session_config = mock_client.create_session.call_args[0][0]
    assert session_config["model"] == "gpt-4o"
    assert "mcp_servers" in session_config
    mock_session.send.assert_awaited_once()
    mock_session.destroy.assert_awaited_once()
    mock_client.stop.assert_awaited_once()


@patch("hve_forge.retrospective.CopilotClient")
def test_run_retrospective_with_github_token(mock_client_class: MagicMock) -> None:
    """Test that _run_retrospective passes github token to the client."""
    import asyncio

    from hve_forge.retrospective import _run_retrospective

    mock_client = AsyncMock()
    mock_client_class.return_value = mock_client

    mock_session = MagicMock()
    mock_session.send = AsyncMock()
    mock_session.destroy = AsyncMock()
    mock_client.create_session = AsyncMock(return_value=mock_session)

    def fake_on(callback: object) -> None:
        event = MagicMock()
        event.type.value = "session.idle"
        callback(event)  # type: ignore[operator]

    mock_session.on = fake_on

    asyncio.run(_run_retrospective(DEFAULT_PROMPT, "gpt-4o", "test-token"))

    mock_client_class.assert_called_once_with({"github_token": "test-token"})
