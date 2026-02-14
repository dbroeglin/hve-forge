"""Tests for hve_forge.main."""

from typer.testing import CliRunner

from hve_forge.main import app


def test_hello_command() -> None:
    """Test that hello command prints 'Hello World!'."""
    runner = CliRunner()
    result = runner.invoke(app, ["hello"])
    assert result.exit_code == 0
    assert "Hello World!" in result.stdout
