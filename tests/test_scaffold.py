"""Smoke tests for the completed project entry point."""

from src.adapters.cli import RagCli


def test_cli_status_reports_complete_launcher_help() -> None:
    """The status no longer advertises completed commands as future work."""
    assert RagCli.status() == (
        "Harness ready. All required RAG commands are implemented; use `api` "
        "as the first argument for the optional local FastAPI server."
    )
