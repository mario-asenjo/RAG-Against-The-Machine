"""Validate that the Hermes harness keeps its critical governance files."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "AGENTS.md",
    "README.md",
    "pyproject.toml",
    "Makefile",
    "docs/project/01_SOURCE_OF_TRUTH.md",
    "docs/project/02_REQUIREMENTS_DISTILLED.md",
    "docs/project/03_EVALUATION_CONTRACT.md",
    "docs/progress/CURRENT.md",
    "docs/progress/RISKS.md",
    "docs/github/INITIAL_BACKLOG.md",
    ".github/pull_request_template.md",
    "hermes/PONYTAIL.md",
    "hermes/skills/rag-against-machine/SKILL.md",
)


def main() -> None:
    """Exit with an error if a critical harness file is absent or empty."""
    errors: list[str] = []
    for relative in REQUIRED:
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing: {relative}")
        elif path.stat().st_size == 0:
            errors.append(f"empty: {relative}")

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    required_ignores = (
        "data/raw/",
        "data/processed/",
        "data/datasets/",
        "data/output/",
    )
    for required_ignore in required_ignores:
        if required_ignore not in gitignore:
            errors.append(f".gitignore must contain: {required_ignore}")

    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for invariant in (
        "Qwen/Qwen3-0.6B",
        "Docs Recall@5 >= 80%",
        "Code Recall@5 >= 50%",
        "<= 300 seconds",
        "200 questions <= 90 seconds",
        "moulinette",
        "Ponytail",
        "GitHub Project",
    ):
        if invariant not in agents:
            errors.append(f"AGENTS.md missing invariant text: {invariant}")

    if errors:
        message = "Context validation failed:\n- " + "\n- ".join(errors)
        raise SystemExit(message)
    print("Context validation passed.")


if __name__ == "__main__":
    main()
