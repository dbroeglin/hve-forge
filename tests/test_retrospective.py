"""Tests for hve_forge.retrospective."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from hve_forge.main import app
from hve_forge.retrospective import (
    DEFAULT_PROMPT,
    RETROSPECTIVE_SYSTEM_MESSAGE,
    _build_mcp_servers,
    _build_session_config,
    _format_tool_arguments,
    _make_event_handler,
    _tool_label,
    _truncate,
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
    assert "verbose" in result.stdout


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
    result = _truncate("a" * 100, 50)
    assert len(result) == 51  # 50 chars + ellipsis
    assert result.endswith("…")


def test_tool_label_mcp_server_and_tool() -> None:
    """Test tool label with both MCP server and tool name."""
    event = MagicMock()
    event.data.tool_name = "list_commits"
    event.data.mcp_server_name = "github"
    event.data.mcp_tool_name = "list_commits"
    assert _tool_label(event) == "github/list_commits"


def test_tool_label_mcp_tool_only() -> None:
    """Test tool label with only MCP tool name."""
    event = MagicMock()
    event.data.tool_name = "list_commits"
    event.data.mcp_server_name = ""
    event.data.mcp_tool_name = "list_commits"
    assert _tool_label(event) == "list_commits"


def test_tool_label_fallback() -> None:
    """Test tool label falls back to tool_name."""
    event = MagicMock()
    event.data.tool_name = "my_tool"
    event.data.mcp_server_name = ""
    event.data.mcp_tool_name = ""
    assert _tool_label(event) == "my_tool"


@patch("hve_forge.retrospective.asyncio.run")
def test_retrospective_default_prompt(mock_asyncio_run: MagicMock) -> None:
    """Test that retrospective uses the default prompt when none is provided."""
    runner = CliRunner()
    result = runner.invoke(app, ["retrospective"])
    assert result.exit_code == 0
    assert "Starting retrospective analysis" in result.stdout
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
    assert "Starting retrospective analysis" in result.stdout
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


# --- Verbose-mode handler tests ---


def test_event_handler_tool_execution_start_verbose() -> None:
    """Test that tool execution start events show a panel in verbose mode."""
    import asyncio

    from rich.console import Console

    console = Console(file=MagicMock(), force_terminal=True)
    done = asyncio.Event()
    errors: list[str] = []
    buffer: list[str] = []
    handler = _make_event_handler(console, done, errors, buffer, verbose=True)

    event = MagicMock()
    event.type.value = "tool.execution_start"
    event.data.tool_name = "list_commits"
    event.data.mcp_server_name = "github"
    event.data.mcp_tool_name = "list_commits"
    event.data.arguments = {"owner": "org", "repo": "project"}

    handler(event)


def test_event_handler_tool_execution_complete_verbose() -> None:
    """Test that tool execution complete events show a panel in verbose mode."""
    import asyncio

    from rich.console import Console

    console = Console(file=MagicMock(), force_terminal=True)
    done = asyncio.Event()
    errors: list[str] = []
    buffer: list[str] = []
    handler = _make_event_handler(console, done, errors, buffer, verbose=True)

    event = MagicMock()
    event.type.value = "tool.execution_complete"
    event.data.tool_name = "list_commits"
    event.data.mcp_server_name = "github"
    event.data.mcp_tool_name = "list_commits"
    event.data.result.content = "some result content"

    handler(event)


# --- Non-verbose (terse) handler tests ---


def test_event_handler_tool_start_terse_updates_live() -> None:
    """Test that tool start updates the Live spinner in non-verbose mode."""
    import asyncio

    from rich.console import Console

    console = Console(file=MagicMock(), force_terminal=True)
    done = asyncio.Event()
    errors: list[str] = []
    buffer: list[str] = []
    mock_live = MagicMock()
    handler = _make_event_handler(console, done, errors, buffer, verbose=False, live=mock_live)

    event = MagicMock()
    event.type.value = "tool.execution_start"
    event.data.tool_name = "list_commits"
    event.data.mcp_server_name = "github"
    event.data.mcp_tool_name = "list_commits"
    event.data.arguments = {}

    handler(event)
    mock_live.update.assert_called_once()


def test_event_handler_tool_complete_terse_updates_live() -> None:
    """Test that tool complete updates the Live spinner in non-verbose mode."""
    import asyncio

    from rich.console import Console

    console = Console(file=MagicMock(), force_terminal=True)
    done = asyncio.Event()
    errors: list[str] = []
    buffer: list[str] = []
    mock_live = MagicMock()
    handler = _make_event_handler(console, done, errors, buffer, verbose=False, live=mock_live)

    event = MagicMock()
    event.type.value = "tool.execution_complete"
    event.data.tool_name = "list_commits"
    event.data.mcp_server_name = "github"
    event.data.mcp_tool_name = "list_commits"

    handler(event)
    mock_live.update.assert_called_once()


# --- Shared handler tests ---


def test_event_handler_assistant_message_buffering() -> None:
    """Test that assistant message deltas are buffered and flushed."""
    import asyncio

    from rich.console import Console

    console = Console(file=MagicMock(), force_terminal=True)
    done = asyncio.Event()
    errors: list[str] = []
    buffer: list[str] = []
    handler = _make_event_handler(console, done, errors, buffer, verbose=True)

    # Send deltas
    for word in ["Hello", " ", "world"]:
        delta_event = MagicMock()
        delta_event.type.value = "assistant.message_delta"
        delta_event.data.delta_content = word
        handler(delta_event)

    assert buffer == ["Hello", " ", "world"]

    # Send complete message event to flush
    msg_event = MagicMock()
    msg_event.type.value = "assistant.message"
    handler(msg_event)

    assert buffer == []


def test_event_handler_session_error() -> None:
    """Test that session errors are captured and signal done."""
    import asyncio

    from rich.console import Console

    console = Console(file=MagicMock(), force_terminal=True)
    done = asyncio.Event()
    errors: list[str] = []
    buffer: list[str] = []
    handler = _make_event_handler(console, done, errors, buffer, verbose=True)

    event = MagicMock()
    event.type.value = "session.error"
    event.data.content = "something went wrong"
    event.data.message = None

    handler(event)

    assert done.is_set()
    assert errors == ["something went wrong"]


def test_event_handler_session_idle() -> None:
    """Test that session idle signals done."""
    import asyncio

    from rich.console import Console

    console = Console(file=MagicMock(), force_terminal=True)
    done = asyncio.Event()
    errors: list[str] = []
    buffer: list[str] = []
    handler = _make_event_handler(console, done, errors, buffer, verbose=True)

    event = MagicMock()
    event.type.value = "session.idle"

    handler(event)

    assert done.is_set()


def test_event_handler_session_idle_terse_stops_live() -> None:
    """Test that session idle stops the Live display in non-verbose mode."""
    import asyncio

    from rich.console import Console

    console = Console(file=MagicMock(), force_terminal=True)
    done = asyncio.Event()
    errors: list[str] = []
    buffer: list[str] = []
    mock_live = MagicMock()
    handler = _make_event_handler(console, done, errors, buffer, verbose=False, live=mock_live)

    event = MagicMock()
    event.type.value = "session.idle"

    handler(event)

    assert done.is_set()
    mock_live.stop.assert_called_once()
