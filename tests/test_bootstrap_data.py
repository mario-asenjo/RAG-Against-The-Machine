"""Tests for staging supplied archive layouts in a clean project."""

from __future__ import annotations

import subprocess
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def write_zip(path: Path, files: dict[str, str]) -> None:
    """Create one tiny archive with the supplied directory shape."""
    with ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def test_bootstrap_data_preserves_public_and_private_archive_layouts(
    tmp_path: Path,
) -> None:
    """Stage canonical trees without flattening or double nesting."""
    project = tmp_path / "project"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    script = scripts / "bootstrap-data.sh"
    script.write_bytes(
        (ROOT / "scripts/bootstrap-data.sh").read_text().encode()
    )

    vllm = tmp_path / "vllm.zip"
    public = tmp_path / "public.zip"
    private = tmp_path / "private.zip"
    write_zip(vllm, {"vllm-0.10.1/module.py": "source"})
    write_zip(
        public,
        {
            "datasets_public/public/AnsweredQuestions/answered.json": "{}",
            "datasets_public/public/UnansweredQuestions/unanswered.json": "{}",
        },
    )
    write_zip(
        private,
        {
            "private/AnsweredQuestions/answered.json": "{}",
            "private/UnansweredQuestions/unanswered.json": "{}",
        },
    )

    completed = subprocess.run(
        [
            "bash",
            "scripts/bootstrap-data.sh",
            "--vllm",
            "../vllm.zip",
            "--public",
            "../public.zip",
            "--private",
            "../private.zip",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    datasets = project / "data/datasets"
    assert (
        datasets
        / "datasets_public/public/AnsweredQuestions/answered.json"
    ).is_file()
    assert (
        datasets
        / "datasets_public/public/UnansweredQuestions/unanswered.json"
    ).is_file()
    assert (datasets / "private/AnsweredQuestions/answered.json").is_file()
    assert (datasets / "private/UnansweredQuestions/unanswered.json").is_file()
    assert not (datasets / "AnsweredQuestions").exists()
    assert not (datasets / "UnansweredQuestions").exists()
    assert not (datasets / "private/private").exists()
    assert "data/datasets/datasets_public/public/" in completed.stdout
    assert "data/datasets/private/" in completed.stdout
