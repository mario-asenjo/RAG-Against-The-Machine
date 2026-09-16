"""Contract checks for the evaluator-facing README."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FIRST_LINE = (
    "*This project has been created as part of the 42 curriculum by masenjo.*"
)
REQUIRED_SECTIONS = (
    "## Description",
    "## Instructions",
    "## Resources",
    "## System Architecture",
    "## Chunking Strategy",
    "## Retrieval Method",
    "## Performance Analysis",
    "## Design Decisions",
    "## Challenges and Limitations",
    "## Example Usage",
)


def test_readme_matches_subject_contract() -> None:
    """Keep the exact first line and every subject-required section."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert readme.splitlines()[0] == REQUIRED_FIRST_LINE
    for section in REQUIRED_SECTIONS:
        assert section in readme
