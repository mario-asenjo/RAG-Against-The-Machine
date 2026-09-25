"""Tests for `python -m src` CLI/API dispatch."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import uvicorn

from src import launcher

ROOT = Path(__file__).resolve().parents[1]


def test_first_api_argument_dispatches_only_to_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reserved first argument selects the Uvicorn launcher."""
    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(
        launcher,
        "run_api",
        lambda arguments: calls.append(("api", arguments)),
    )
    monkeypatch.setattr(
        launcher,
        "run_cli",
        lambda: calls.append(("cli", [])),
    )

    launcher.main(["api", "--port", "9000"])

    assert calls == [("api", ["--port", "9000"])]


def test_every_other_first_argument_preserves_fire_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Required evaluator commands remain on the existing Fire path."""
    calls: list[str] = []
    monkeypatch.setattr(
        launcher,
        "run_api",
        lambda arguments: calls.append("api"),
    )
    monkeypatch.setattr(launcher, "run_cli", lambda: calls.append("cli"))

    launcher.main(["search", "question"])

    assert calls == ["cli"]


def test_api_runner_uses_localhost_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uvicorn loads the FastAPI factory on localhost with one worker."""
    options: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        uvicorn,
        "run",
        lambda target, **kwargs: options.append((target, kwargs)),
    )

    launcher.run_api(["--port", "9001", "--log-level", "warning"])

    assert options == [
        (
            "src.adapters.http:create_app",
            {
                "factory": True,
                "host": "127.0.0.1",
                "port": 9001,
                "log_level": "warning",
                "workers": 1,
            },
        )
    ]


def test_module_api_help_is_explicit_and_does_not_start_server() -> None:
    """The reserved launcher mode owns clear help without entering Fire."""
    result = subprocess.run(
        [sys.executable, "-m", "src", "api", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "127.0.0.1" in result.stdout
    assert "--port" in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize("port", ("-1", "65536"))
def test_module_api_rejects_invalid_port_without_traceback(port: str) -> None:
    """Invalid TCP ports remain clean launcher usage errors."""
    result = subprocess.run(
        [sys.executable, "-m", "src", "api", "--port", port],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "must be between 0 and 65535" in result.stderr
    assert "traceback" not in result.stderr.lower()


def test_module_non_api_command_still_runs_fire() -> None:
    """The launcher leaves the required Fire command path unchanged."""
    result = subprocess.run(
        [sys.executable, "-m", "src", "status"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.startswith("Harness ready.")
    assert result.stderr == ""
