"""Contract checks for the native-campus evidence runner."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_campus_runner_reenters_root_before_each_step() -> None:
    """Recover from an NFS-invalidated inherited working directory."""
    script = (ROOT / "scripts/campus_test.sh").read_text(encoding="utf-8")
    run_step = script.split("run_step() {", 1)[1].split("\n}", 1)[0]

    root_guard = 'cd "$ROOT" && pwd -P >/dev/null'
    assert root_guard in run_step
    assert run_step.index(root_guard) < run_step.index('time "$@"')
