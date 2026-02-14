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
    _ensure_copilot_cli_executable,
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


# --- Additional coverage tests ---


def test_format_tool_arguments_non_string_non_dict() -> None:
    """Test formatting an argument that is neither str, dict, nor None."""
    assert _format_tool_arguments(42) == "42"
    assert _format_tool_arguments([1, 2, 3]) == "[1, 2, 3]"


def test_truncate_exact_length() -> None:
    """Test that text exactly at max_length is not truncated."""
    text = "a" * 500
    assert _truncate(text) == text


def test_truncate_default_max_length() -> None:
    """Test truncation with the default max_length of 500."""
    text = "b" * 600
    result = _truncate(text)
    assert len(result) == 501  # 500 chars + ellipsis
    assert result.endswith("…")


def test_build_mcp_servers_with_github_token() -> None:
    """Test that MCP server config picks up GITHUB_TOKEN from environment."""
    with patch.dict("os.environ", {"GITHUB_TOKEN": "test-token-123"}):
        servers = _build_mcp_servers()
    github_env = servers["github"]["env"]
    assert github_env["GITHUB_PERSONAL_ACCESS_TOKEN"] == "test-token-123"


def test_build_mcp_servers_without_github_token() -> None:
    """Test that MCP server config uses empty string when no GITHUB_TOKEN."""
    with patch.dict("os.environ", {}, clear=True):
        servers = _build_mcp_servers()
    github_env = servers["github"]["env"]
    assert github_env["GITHUB_PERSONAL_ACCESS_TOKEN"] == ""


@patch("hve_forge.retrospective.sys")
@patch("hve_forge.retrospective.os")
@patch("hve_forge.retrospective.Path")
def test_ensure_copilot_cli_executable_unix(
    mock_path_cls: MagicMock,
    mock_os: MagicMock,
    mock_sys: MagicMock,
) -> None:
    """Test _ensure_copilot_cli_executable on a Unix-like platform."""
    mock_sys.platform = "linux"

    # Mock the copilot package path
    mock_copilot = MagicMock()
    mock_copilot.__file__ = "/fake/copilot/__init__.py"
    with patch.dict("sys.modules", {"copilot": mock_copilot}):
        mock_pkg_dir = MagicMock()
        mock_path_cls.return_value.parent = mock_pkg_dir
        mock_binary = MagicMock()
        mock_pkg_dir.__truediv__ = MagicMock(side_effect=lambda x: mock_binary if x == "bin" else mock_pkg_dir)
        mock_binary.__truediv__ = MagicMock(return_value=mock_binary)
        mock_binary.exists.return_value = True
        mock_os.access.return_value = False

        _ensure_copilot_cli_executable()

        mock_binary.chmod.assert_called_once()


@patch("hve_forge.retrospective.sys")
@patch("hve_forge.retrospective.os")
@patch("hve_forge.retrospective.Path")
def test_ensure_copilot_cli_executable_already_executable(
    mock_path_cls: MagicMock,
    mock_os: MagicMock,
    mock_sys: MagicMock,
) -> None:
    """Test _ensure_copilot_cli_executable when binary is already executable."""
    mock_sys.platform = "linux"

    mock_copilot = MagicMock()
    mock_copilot.__file__ = "/fake/copilot/__init__.py"
    with patch.dict("sys.modules", {"copilot": mock_copilot}):
        mock_pkg_dir = MagicMock()
        mock_path_cls.return_value.parent = mock_pkg_dir
        mock_binary = MagicMock()
        mock_pkg_dir.__truediv__ = MagicMock(side_effect=lambda x: mock_binary if x == "bin" else mock_pkg_dir)
        mock_binary.__truediv__ = MagicMock(return_value=mock_binary)
        mock_binary.exists.return_value = True
        mock_os.access.return_value = True  # Already executable

        _ensure_copilot_cli_executable()

        mock_binary.chmod.assert_not_called()


def test_event_handler_tool_execution_progress_verbose() -> None:
    """Test that tool execution progress events are handled in verbose mode."""
    import asyncio

    from rich.console import Console

    console = Console(file=MagicMock(), force_terminal=True)
    done = asyncio.Event()
    errors: list[str] = []
    buffer: list[str] = []
    handler = _make_event_handler(console, done, errors, buffer, verbose=True)

    event = MagicMock()
    event.type.value = "tool.execution_progress"
    event.data.progress_message = "Loading data..."

    handler(event)
    # Handler should run without errors for non-empty progress messages


def test_event_handler_tool_execution_progress_no_message() -> None:
    """Test that empty progress messages are silently ignored."""
    import asyncio

    from rich.console import Console

    console = Console(file=MagicMock(), force_terminal=True)
    done = asyncio.Event()
    errors: list[str] = []
    buffer: list[str] = []
    handler = _make_event_handler(console, done, errors, buffer, verbose=True)

    event = MagicMock()
    event.type.value = "tool.execution_progress"
    event.data.progress_message = ""

    handler(event)
    # Empty progress messages should be silently ignored


def test_event_handler_tool_execution_partial_result_verbose() -> None:
    """Test that partial result events are handled in verbose mode."""
    import asyncio

    from rich.console import Console

    console = Console(file=MagicMock(), force_terminal=True)
    done = asyncio.Event()
    errors: list[str] = []
    buffer: list[str] = []
    handler = _make_event_handler(console, done, errors, buffer, verbose=True)

    event = MagicMock()
    event.type.value = "tool.execution_partial_result"
    event.data.partial_output = "partial data"

    handler(event)
    # Handler should run without errors for non-empty partial output


def test_event_handler_tool_execution_partial_result_empty() -> None:
    """Test that empty partial results are silently ignored."""
    import asyncio

    from rich.console import Console

    console = Console(file=MagicMock(), force_terminal=True)
    done = asyncio.Event()
    errors: list[str] = []
    buffer: list[str] = []
    handler = _make_event_handler(console, done, errors, buffer, verbose=True)

    event = MagicMock()
    event.type.value = "tool.execution_partial_result"
    event.data.partial_output = ""

    handler(event)
    # Empty partial output should be silently ignored


def test_event_handler_assistant_message_terse_stops_live() -> None:
    """Test that assistant.message stops live display in non-verbose mode."""
    import asyncio

    from rich.console import Console

    console = Console(file=MagicMock(), force_terminal=True)
    done = asyncio.Event()
    errors: list[str] = []
    buffer: list[str] = ["Hello ", "world"]
    mock_live = MagicMock()
    handler = _make_event_handler(console, done, errors, buffer, verbose=False, live=mock_live)

    event = MagicMock()
    event.type.value = "assistant.message"

    handler(event)
    mock_live.stop.assert_called_once()
    assert buffer == []


def test_event_handler_assistant_message_empty_buffer() -> None:
    """Test that assistant.message with empty buffer does not raise."""
    import asyncio

    from rich.console import Console

    console = Console(file=MagicMock(), force_terminal=True)
    done = asyncio.Event()
    errors: list[str] = []
    buffer: list[str] = []
    handler = _make_event_handler(console, done, errors, buffer, verbose=True)

    event = MagicMock()
    event.type.value = "assistant.message"

    handler(event)
    # Empty buffer should be handled gracefully


def test_event_handler_assistant_turn_start_verbose() -> None:
    """Test that turn start is handled in verbose mode."""
    import asyncio

    from rich.console import Console

    console = Console(file=MagicMock(), force_terminal=True)
    done = asyncio.Event()
    errors: list[str] = []
    buffer: list[str] = []
    handler = _make_event_handler(console, done, errors, buffer, verbose=True)

    event = MagicMock()
    event.type.value = "assistant.turn_start"

    handler(event)
    # Should print a panel in verbose mode without errors


def test_event_handler_assistant_turn_start_terse_updates_live() -> None:
    """Test that turn start updates spinner in non-verbose mode."""
    import asyncio

    from rich.console import Console

    console = Console(file=MagicMock(), force_terminal=True)
    done = asyncio.Event()
    errors: list[str] = []
    buffer: list[str] = []
    mock_live = MagicMock()
    handler = _make_event_handler(console, done, errors, buffer, verbose=False, live=mock_live)

    event = MagicMock()
    event.type.value = "assistant.turn_start"

    handler(event)
    mock_live.update.assert_called_once()


def test_event_handler_assistant_turn_end_verbose() -> None:
    """Test that turn end is handled in verbose mode."""
    import asyncio

    from rich.console import Console

    console = Console(file=MagicMock(), force_terminal=True)
    done = asyncio.Event()
    errors: list[str] = []
    buffer: list[str] = []
    handler = _make_event_handler(console, done, errors, buffer, verbose=True)

    event = MagicMock()
    event.type.value = "assistant.turn_end"

    handler(event)
    # Should print a panel in verbose mode without errors


def test_event_handler_session_start_verbose() -> None:
    """Test that session start is handled in verbose mode."""
    import asyncio

    from rich.console import Console

    console = Console(file=MagicMock(), force_terminal=True)
    done = asyncio.Event()
    errors: list[str] = []
    buffer: list[str] = []
    handler = _make_event_handler(console, done, errors, buffer, verbose=True)

    event = MagicMock()
    event.type.value = "session.start"

    handler(event)
    # Should print session started message without errors


def test_event_handler_session_error_fallback_to_str() -> None:
    """Test that session error falls back to str(data) when no content/message."""
    import asyncio

    from rich.console import Console

    console = Console(file=MagicMock(), force_terminal=True)
    done = asyncio.Event()
    errors: list[str] = []
    buffer: list[str] = []
    handler = _make_event_handler(console, done, errors, buffer, verbose=True)

    event = MagicMock(spec=[])
    event.type = MagicMock()
    event.type.value = "session.error"
    # Use an object without 'content' or 'message' attributes
    event.data = "raw error string"

    handler(event)
    assert done.is_set()
    assert errors == ["raw error string"]


def test_event_handler_tool_complete_verbose_no_result() -> None:
    """Test tool execution complete with no result in verbose mode."""
    import asyncio

    from rich.console import Console

    console = Console(file=MagicMock(), force_terminal=True)
    done = asyncio.Event()
    errors: list[str] = []
    buffer: list[str] = []
    handler = _make_event_handler(console, done, errors, buffer, verbose=True)

    event = MagicMock()
    event.type.value = "tool.execution_complete"
    event.data.tool_name = "some_tool"
    event.data.mcp_server_name = ""
    event.data.mcp_tool_name = ""
    event.data.result = None

    handler(event)
    # Should handle None result gracefully in verbose mode


@patch("hve_forge.retrospective.CopilotClient")
def test_run_retrospective_error_raises_exit(mock_client_class: MagicMock) -> None:
    """Test that _run_retrospective raises typer.Exit on session error."""
    import asyncio

    import pytest
    from click.exceptions import Exit

    from hve_forge.retrospective import _run_retrospective

    mock_client = AsyncMock()
    mock_client_class.return_value = mock_client

    mock_session = MagicMock()
    mock_session.send = AsyncMock()
    mock_session.destroy = AsyncMock()
    mock_client.create_session = AsyncMock(return_value=mock_session)

    def fake_on(callback: object) -> None:
        # Simulate a session error followed by idle
        error_event = MagicMock()
        error_event.type.value = "session.error"
        error_event.data.content = "something broke"
        error_event.data.message = None
        callback(error_event)  # type: ignore[operator]

    mock_session.on = fake_on

    with pytest.raises(Exit):
        asyncio.run(_run_retrospective(DEFAULT_PROMPT, "gpt-4o", None))

    mock_client.stop.assert_awaited_once()


@patch("hve_forge.retrospective.CopilotClient")
def test_run_retrospective_non_verbose_uses_live(mock_client_class: MagicMock) -> None:
    """Test that _run_retrospective uses a Live display in non-verbose mode."""
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

    # Non-verbose mode (default) should use Live display
    asyncio.run(_run_retrospective(DEFAULT_PROMPT, "gpt-4o", None, verbose=False))

    mock_client.start.assert_awaited_once()
    mock_session.send.assert_awaited_once()
    mock_session.destroy.assert_awaited_once()
    mock_client.stop.assert_awaited_once()


@patch("hve_forge.retrospective.CopilotClient")
def test_run_retrospective_verbose_mode(mock_client_class: MagicMock) -> None:
    """Test that _run_retrospective works in verbose mode without Live display."""
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

    asyncio.run(_run_retrospective(DEFAULT_PROMPT, "gpt-4o", None, verbose=True))

    mock_client.start.assert_awaited_once()
    mock_session.send.assert_awaited_once()
    mock_session.destroy.assert_awaited_once()
    mock_client.stop.assert_awaited_once()


def test_tool_label_with_none_values() -> None:
    """Test tool label when MCP fields are None (not empty strings)."""
    event = MagicMock()
    event.data.tool_name = "fallback_tool"
    event.data.mcp_server_name = None
    event.data.mcp_tool_name = None
    # When mcp_server_name is None, the condition `if mcp_server and mcp_tool` is False
    # and `if mcp_tool` is also False, so it falls back to tool_name
    assert _tool_label(event) == "fallback_tool"
