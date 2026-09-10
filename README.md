# RAG Against the Machine — Hermes Harness

This repository implements the 42 project **RAG against the machine (subject v2.0)** incrementally. The current mandatory baseline loads the corpus, preserves exact source spans, applies distinct Python and Markdown/text chunking, persists a SQLite FTS5 BM25 index, and returns ranked exact source locations for individual queries and datasets. The single-query `answer` command grounds Qwen/Qwen3-0.6B in exact indexed chunks; `answer_dataset` remains issue-scoped work in progress.

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
uv run python -m src search "What is paged attention?" --k 5
```

The index is written atomically to `data/processed/lexical_index.sqlite3` by default. Corpus, index, and output paths remain configurable:

```bash
uv run python -m src index \
  --corpus_path data/raw/vllm-0.10.1 \
  --save_directory data/processed \
  --max_chunk_size 2000

uv run python -m src search "What is paged attention?" \
  --index_directory data/processed \
  --k 5

uv run python -m src search_dataset \
  --dataset_path data/datasets/datasets_public/public/UnansweredQuestions/dataset_docs_public.json \
  --index_directory data/processed \
  --save_directory data/output/search_results/UnansweredQuestions \
  --k 5

uv run python -m src evaluate \
  --student_search_results_path \
    data/output/search_results/UnansweredQuestions/dataset_docs_public.json \
  --dataset_path data/datasets/datasets_public/public/AnsweredQuestions/dataset_docs_public.json \
  --max_context_length 2000


uv run python -m src answer "What does Volta refer to in vLLM hardware documentation?" \
  --k 1 \
  --index_directory data/processed \
  --save_path data/output/search_results_and_answer/answer.json \
  --model_cache_directory models/huggingface \
  --token_budget 2048 \
  --max_new_tokens 128
```

`search` prints ranked human-readable locations as
`file_path [first_character_index:last_character_index]`. `search_dataset`
serializes the subject's exact `StudentSearchResults` model to a file named
after the input dataset while preserving question identity and order. Its
default output directory is
`data/output/search_results/UnansweredQuestions`.

`evaluate` validates a `StudentSearchResults` file against an answered
`RagDataset` and prints macro Recall@1/3/5/10 diagnostics. Invalid student,
dataset, and evaluator-configuration inputs exit non-zero with a clear error
and no traceback.

`answer` searches once, loads only exact SQLite source tuples, fits complete
ranked chunks under the real Qwen chat-template budget, prints the answer and
retrieved locations, and writes the exact Pydantic
`StudentSearchResultsAndAnswer` wrapper. With `k=0` or no matches it writes an
explicit abstention without loading model assets. `--local_files_only=True`
requires the pinned Qwen snapshot to exist under `--model_cache_directory`;
`uv sync` installs runtime packages but does not download model weights. See
`docs/project/09_GENERATION_RUNTIME.md` and
`docs/project/10_GROUNDED_ANSWER.md`. `answer_dataset` remains explicitly
unimplemented until issue #14.
