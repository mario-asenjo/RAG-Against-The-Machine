"""Install this repository's Hermes skill into the active Hermes home."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_SKILL = ROOT / "hermes" / "skills" / "rag-against-machine"


def hermes_home() -> Path:
    """Return the active Hermes home directory."""
    configured = os.environ.get("HERMES_HOME")
    if configured:
        return Path(configured).expanduser()

    try:
        completed = subprocess.run(
            ["hermes", "config", "path"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return Path.home() / ".hermes"

    config_path = completed.stdout.strip()
    if not config_path:
        return Path.home() / ".hermes"
    return Path(config_path).expanduser().parent


def main() -> None:
    """Install the project skill into the active Hermes skills directory."""
    target = hermes_home() / "skills" / "development" / "rag-against-machine"
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PROJECT_SKILL, target)
    print(f"Installed project skill at: {target}")


if __name__ == "__main__":
    main()
