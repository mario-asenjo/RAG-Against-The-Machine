# RAG Against the Machine — Hermes Harness

This repository implements the 42 project **RAG against the machine (subject v2.0)** incrementally. The current mandatory baseline loads the corpus, preserves exact source spans, applies distinct Python and Markdown/text chunking, and persists a SQLite FTS5 BM25 index. Search and answer commands remain issue-scoped work in progress.

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

The CLI can be inspected and the default corpus indexed with:

```bash
uv run python -m src --help
uv run python -m src index --max_chunk_size 2000
```

The index is written atomically to `data/processed/lexical_index.sqlite3` by default. Corpus and output paths remain configurable:

```bash
uv run python -m src index \
  --corpus_path data/raw/vllm-0.10.1 \
  --save_directory data/processed \
  --max_chunk_size 2000
```

Commands whose implementation issues are still open fail explicitly instead of pretending to be complete.
