# RAG Against the Machine — Hermes Harness

This repository scaffold is an implementation harness for the 42 project **RAG against the machine (subject v2.0)**. It deliberately contains project governance, source-derived constraints, Hermes/Ponytail setup, GitHub workflow templates, progress ledgers, and a minimal runnable Python skeleton — but **no finished retrieval implementation**.

## Start here

1. Read `AGENTS.md`.
2. Read `docs/project/00_BOOTSTRAP.md`.
3. Stage the supplied local sources/data with `scripts/bootstrap-data.sh` (they remain gitignored).
4. Run `uv sync`.
5. Run `make check`.
6. Configure Hermes using `hermes/INSTALL.md`.
7. Create/identify the GitHub repository and its single associated Project.
8. Create the initial issues from `docs/github/INITIAL_BACKLOG.md` or let Hermes create them one by one.
9. Implement only the first approved issue.

## Harness philosophy

The workflow is intentionally issue-first, vertical-slice, benchmark-driven, and evaluator-aware. Public datasets are for iteration. Private datasets remain a holdout. Ponytail reviews every non-trivial diff for over-engineering, but subject/evaluator correctness always wins over deletion.

## Useful commands

```bash
uv sync
make check
make test
make lint
make lint-strict
make context
```

The placeholder CLI can be inspected with:

```bash
uv run python -m src --help
```

It intentionally reports that project commands are not implemented until their issues are completed.
