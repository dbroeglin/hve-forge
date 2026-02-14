"""Tests for hve_forge.main."""

from typer.testing import CliRunner

from hve_forge.main import app


def test_help_shows_available_commands() -> None:
    """Test that help output lists expected commands."""
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "retrospective" in result.stdout
