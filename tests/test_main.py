"""Tests for hve_forge.main."""

from hve_forge.main import main


def test_main(capsys: object) -> None:
    """Test that main prints the greeting."""
    main()
    captured = capsys.readouterr()  # type: ignore[union-attr]
    assert "Hello from hve-forge!" in captured.out
