"""Smoke tests for the harness before project implementation starts."""

from src.__main__ import RagCli


def test_scaffold_status_is_explicit() -> None:
    """The scaffold should not pretend mandatory functionality exists."""
    assert "Harness ready" in RagCli.status()
