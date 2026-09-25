"""Dispatch `python -m src` to Fire or the local Uvicorn server."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

import uvicorn

from src.adapters.cli import main as run_cli


def _port(value: str) -> int:
    """Return one valid TCP port for Uvicorn."""
    port = int(value)
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("must be between 0 and 65535")
    return port


def _api_parser() -> argparse.ArgumentParser:
    """Build dedicated help for the reserved `api` launcher mode."""
    parser = argparse.ArgumentParser(
        prog="python -m src api",
        description=(
            "Run the local FastAPI adapter on 127.0.0.1 using the "
            "Uvicorn application factory."
        ),
    )
    parser.add_argument("--port", type=_port, default=8000)
    parser.add_argument(
        "--log-level",
        choices=("critical", "error", "warning", "info", "debug", "trace"),
        default="info",
    )
    return parser


def run_api(arguments: Sequence[str]) -> None:
    """Run the local Uvicorn server in factory mode with one worker."""
    options = _api_parser().parse_args(list(arguments))
    uvicorn.run(
        "src.adapters.http:create_app",
        factory=True,
        host="127.0.0.1",
        port=options.port,
        log_level=options.log_level,
        workers=1,
    )


def main(arguments: Sequence[str] | None = None) -> None:
    """Reserve `api`; otherwise preserve Python Fire dispatch."""
    selected = list(sys.argv[1:] if arguments is None else arguments)
    if selected[:1] == ["api"]:
        run_api(selected[1:])
        return
    run_cli()
