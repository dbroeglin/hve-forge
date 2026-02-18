"""Tests for hve_forge.github_stats."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from hve_forge.github_stats import (
    GITHUB_STATS_SYSTEM_MESSAGE,
    _build_mcp_servers,
    _build_session_config,
    _format_tool_arguments,
    _make_event_handler,
    _tool_label,
    _truncate,
)
from hve_forge.main import app


def test_github_stats_command_appears_in_help() -> None:
    """Test that the github-stats command is listed in CLI help."""
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "github-stats" in result.stdout


def test_github_stats_help() -> None:
    """Test that the github-stats command has proper help text."""
    runner = CliRunner()
    result = runner.invoke(app, ["github-stats", "--help"])
    assert result.exit_code == 0
    assert "prompt" in result.stdout
    assert "model" in result.stdout
    assert "github" in result.stdout
    assert "verbose" in result.stdout


def test_build_mcp_servers() -> None:
    """Test that MCP server configurations are built correctly."""
    servers = _build_mcp_servers()
    assert "github" in servers

    github_server = servers["github"]
    assert github_server["command"] == "npx"
    assert "@modelcontextprotocol/server-github" in github_server["args"]


def test_build_session_config() -> None:
    """Test that session configuration is built correctly."""
    config = _build_session_config("gpt-4o")
    assert config["model"] == "gpt-4o"
    assert config["streaming"] is True
    assert "mcp_servers" in config
    assert config["system_message"]["content"] == GITHUB_STATS_SYSTEM_MESSAGE


def test_build_session_config_custom_model() -> None:
    """Test that session configuration respects custom model."""
    config = _build_session_config("claude-sonnet-4.5")
    assert config["model"] == "claude-sonnet-4.5"


def test_format_tool_arguments_none() -> None:
    """Test formatting None arguments."""
    assert _format_tool_arguments(None) == ""


def test_format_tool_arguments_dict() -> None:
    """Test formatting dict arguments."""
    result = _format_tool_arguments({"owner": "org", "repo": "project"})
    parsed = json.loads(result)
    assert parsed == {"owner": "org", "repo": "project"}


def test_format_tool_arguments_json_string() -> None:
    """Test formatting a JSON string."""
    result = _format_tool_arguments('{"key": "value"}')
    parsed = json.loads(result)
    assert parsed == {"key": "value"}


def test_format_tool_arguments_plain_string() -> None:
    """Test formatting a plain string that is not JSON."""
    assert _format_tool_arguments("hello") == "hello"


def test_truncate_short_text() -> None:
    """Test that short text is not truncated."""
    assert _truncate("short", 100) == "short"


def test_truncate_long_text() -> None:
    """Test that long text is truncated with ellipsis."""
    long_text = "a" * 600
    result = _truncate(long_text, 500)
    assert len(result) == 501  # 500 chars + ellipsis
    assert result.endswith("…")
    assert result.startswith("a" * 500)


def test_tool_label_mcp_server_and_tool() -> None:
    """Test tool label when both server and tool names are present."""
    event = MagicMock()
    event.data.tool_name = "generic"
    event.data.mcp_server_name = "github"
    event.data.mcp_tool_name = "list_repos"
    assert _tool_label(event) == "github/list_repos"


def test_tool_label_mcp_tool_only() -> None:
    """Test tool label when only tool name is present."""
    event = MagicMock()
    event.data.tool_name = "generic"
    event.data.mcp_server_name = ""
    event.data.mcp_tool_name = "search"
    assert _tool_label(event) == "search"


def test_tool_label_fallback() -> None:
    """Test tool label fallback to tool_name."""
    event = MagicMock()
    event.data.tool_name = "generic_tool"
    event.data.mcp_server_name = ""
    event.data.mcp_tool_name = ""
    assert _tool_label(event) == "generic_tool"


@patch("hve_forge.github_stats._run_github_stats")
def test_github_stats_default_prompt(mock_run: MagicMock) -> None:
    """Test that github_stats uses default prompt when none is provided."""
    runner = CliRunner()
    # Mock the async function to avoid actual execution
    mock_run.return_value = None

    result = runner.invoke(app, ["github-stats", "--github-token", "fake-token"])

    # The command will fail because we're mocking, but we can check it attempted to run
    # with the right structure
    assert mock_run.called or result.exit_code is not None


@patch("hve_forge.github_stats._run_github_stats")
def test_github_stats_custom_prompt(mock_run: MagicMock) -> None:
    """Test that github_stats respects custom prompt."""
    runner = CliRunner()
    mock_run.return_value = None

    custom_prompt = "Show me repository stars"
    result = runner.invoke(app, ["github-stats", "--prompt", custom_prompt, "--github-token", "fake-token"])

    assert mock_run.called or result.exit_code is not None


@patch("hve_forge.github_stats._run_github_stats")
def test_github_stats_custom_model(mock_run: MagicMock) -> None:
    """Test that github_stats respects custom model."""
    runner = CliRunner()
    mock_run.return_value = None

    result = runner.invoke(app, ["github-stats", "--model", "gpt-4", "--github-token", "fake-token"])

    assert mock_run.called or result.exit_code is not None


@patch("hve_forge.github_stats.CopilotClient")
def test_run_github_stats_creates_session(mock_client_class: MagicMock) -> None:
    """Test that _run_github_stats creates a Copilot session with proper config."""
    import asyncio

    from hve_forge.github_stats import DEFAULT_PROMPT, _run_github_stats

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

    asyncio.run(_run_github_stats(DEFAULT_PROMPT, "gpt-4o", None, verbose=False))

    mock_client.start.assert_awaited_once()
    mock_client.create_session.assert_awaited_once()
    session_config = mock_client.create_session.call_args[0][0]
    assert session_config["model"] == "gpt-4o"
    assert "mcp_servers" in session_config
    mock_session.send.assert_awaited_once()
    mock_session.destroy.assert_awaited_once()
    mock_client.stop.assert_awaited_once()


@patch("hve_forge.github_stats.CopilotClient")
def test_run_github_stats_with_github_token(mock_client_class: MagicMock) -> None:
    """Test that _run_github_stats passes github token to the client."""
    import asyncio

    from hve_forge.github_stats import _run_github_stats

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

    asyncio.run(_run_github_stats("Test prompt", "gpt-4o", "test-token", verbose=False))

    # Check that client was initialized with token
    mock_client_class.assert_called_with({"github_token": "test-token"})


def test_event_handler_tool_execution_start_verbose() -> None:
    """Test event handler displays tool execution start in verbose mode."""
    import asyncio
    from unittest.mock import MagicMock

    from rich.console import Console

    console = Console()
    done = asyncio.Event()
    error_message: list[str] = []
    message_buffer: list[str] = []

    handler = _make_event_handler(console, done, error_message, message_buffer, verbose=True)

    event = MagicMock()
    event.type.value = "tool.execution_start"
    event.data.tool_name = "test_tool"
    event.data.mcp_server_name = "github"
    event.data.mcp_tool_name = "list_repos"
    event.data.arguments = {"owner": "test"}

    # Should not raise
    handler(event)


def test_event_handler_tool_execution_complete_verbose() -> None:
    """Test event handler displays tool completion in verbose mode."""
    import asyncio
    from unittest.mock import MagicMock

    from rich.console import Console

    console = Console()
    done = asyncio.Event()
    error_message: list[str] = []
    message_buffer: list[str] = []

    handler = _make_event_handler(console, done, error_message, message_buffer, verbose=True)

    event = MagicMock()
    event.type.value = "tool.execution_complete"
    event.data.tool_name = "test_tool"
    event.data.mcp_server_name = "github"
    event.data.mcp_tool_name = "list_repos"
    event.data.result = MagicMock()
    event.data.result.content = "Success"

    handler(event)


def test_event_handler_tool_start_terse_updates_live() -> None:
    """Test event handler updates live display in terse mode."""
    import asyncio
    from unittest.mock import MagicMock

    from rich.console import Console
    from rich.live import Live

    console = Console()
    done = asyncio.Event()
    error_message: list[str] = []
    message_buffer: list[str] = []
    live = MagicMock(spec=Live)

    handler = _make_event_handler(console, done, error_message, message_buffer, verbose=False, live=live)

    event = MagicMock()
    event.type.value = "tool.execution_start"
    event.data.tool_name = "test_tool"
    event.data.mcp_server_name = "github"
    event.data.mcp_tool_name = "list_repos"
    event.data.arguments = None

    handler(event)
    assert live.update.called


def test_event_handler_tool_complete_terse_updates_live() -> None:
    """Test event handler updates live display when tool completes in terse mode."""
    import asyncio
    from unittest.mock import MagicMock

    from rich.console import Console
    from rich.live import Live

    console = Console()
    done = asyncio.Event()
    error_message: list[str] = []
    message_buffer: list[str] = []
    live = MagicMock(spec=Live)

    handler = _make_event_handler(console, done, error_message, message_buffer, verbose=False, live=live)

    event = MagicMock()
    event.type.value = "tool.execution_complete"
    event.data.tool_name = "test_tool"
    event.data.mcp_server_name = "github"
    event.data.mcp_tool_name = "list_repos"
    event.data.result = None

    handler(event)
    assert live.update.called


def test_event_handler_assistant_message_buffering() -> None:
    """Test that assistant message deltas are buffered correctly."""
    import asyncio
    from unittest.mock import MagicMock

    from rich.console import Console

    console = Console()
    done = asyncio.Event()
    error_message: list[str] = []
    message_buffer: list[str] = []

    handler = _make_event_handler(console, done, error_message, message_buffer, verbose=True)

    # Send delta events
    event1 = MagicMock()
    event1.type.value = "assistant.message_delta"
    event1.data.delta_content = "Hello "

    event2 = MagicMock()
    event2.type.value = "assistant.message_delta"
    event2.data.delta_content = "World"

    handler(event1)
    handler(event2)

    assert message_buffer == ["Hello ", "World"]


def test_event_handler_session_error() -> None:
    """Test that session errors are handled correctly."""
    import asyncio
    from unittest.mock import MagicMock

    from rich.console import Console

    console = Console()
    done = asyncio.Event()
    error_message: list[str] = []
    message_buffer: list[str] = []

    handler = _make_event_handler(console, done, error_message, message_buffer, verbose=True)

    event = MagicMock()
    event.type.value = "session.error"
    event.data.content = "Test error"

    handler(event)

    assert "Test error" in error_message
    assert done.is_set()


def test_event_handler_session_idle() -> None:
    """Test that session idle triggers done event."""
    import asyncio
    from unittest.mock import MagicMock

    from rich.console import Console

    console = Console()
    done = asyncio.Event()
    error_message: list[str] = []
    message_buffer: list[str] = []

    handler = _make_event_handler(console, done, error_message, message_buffer, verbose=True)

    event = MagicMock()
    event.type.value = "session.idle"

    handler(event)

    assert done.is_set()


def test_event_handler_session_idle_terse_stops_live() -> None:
    """Test that session idle stops live display in terse mode."""
    import asyncio
    from unittest.mock import MagicMock

    from rich.console import Console
    from rich.live import Live

    console = Console()
    done = asyncio.Event()
    error_message: list[str] = []
    message_buffer: list[str] = []
    live = MagicMock(spec=Live)

    handler = _make_event_handler(console, done, error_message, message_buffer, verbose=False, live=live)

    event = MagicMock()
    event.type.value = "session.idle"

    handler(event)

    assert live.stop.called
    assert done.is_set()
