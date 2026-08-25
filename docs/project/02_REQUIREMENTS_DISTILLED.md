# Distilled mandatory requirements

## Pipeline
The system must ingest/index the supplied vLLM codebase, retrieve relevant source snippets, pass retrieved context to a small local model, generate grounded answers, and measure retrieval with Recall@k.

## Indexing

- Whole-corpus indexing <= 5 minutes.
- Read useful files from the supplied vLLM repository.
- Two distinct chunking strategies are mandatory:
  - Python code;
  - Markdown/text.
- At least one lexical retrieval method is mandatory:
  - TF-IDF; or
  - BM25.
- `--max_chunk_size` is configurable, defaults to 2000 characters, and emitted chunks/sources must never exceed 2000 characters.
- Persist the index under `data/processed/`.
- Character ranges must refer to the original exact file text.

## Retrieval

Each result contains:

```text
file_path
first_character_index
last_character_index
```

Requirements:

- exact corpus path;
- source width <= 2000 chars;
- ranked top-k;
- single-query and dataset modes;
- docs Recall@5 >= 80%;
- code Recall@5 >= 50%;
- warm retrieval for 200 private questions <= 90 seconds.

## Generation
Use `Qwen/Qwen3-0.6B` by default. Another model may be supported only if the implementation still works with Qwen/Qwen3-0.6B. Answers should be coherent, address the question, and remain mostly grounded in retrieved context.

## Required Pydantic model basis

- `MinimalSource(file_path, first_character_index, last_character_index)`
- `UnansweredQuestion(question_id, question)`
- `AnsweredQuestion(..., sources, answer)`
- `RagDataset(rag_questions)`
- `MinimalSearchResults(question_id, question, retrieved_sources)`
- `MinimalAnswer(..., answer)`
- `StudentSearchResults(search_results, k)`
- `StudentSearchResultsAndAnswer(search_results, k)`

Models may be expanded, but output must preserve the required minimal shape.

## CLI
All commands run as:

```text
uv run python -m src <command> [options]
```

Mandatory commands:

```text
index --max_chunk_size <int>
search <query> --k <int>
search_dataset --dataset_path <path> --k <int> --save_directory <dir>
answer <query> --k <int>
answer_dataset --student_search_results_path <path> --save_directory <dir>
evaluate --student_search_results_path <path> --dataset_path <path>
```

All input/output paths are configurable. Long operations use tqdm. Empty/nonsensical queries, `k=0`, missing files, and malformed JSON must not produce unhandled tracebacks.

## Tooling

- Python >= 3.10.
- `uv sync` from root must work.
- Python Fire CLI.
- Pydantic data models.
- Type hints and docstrings.
- Flake8.
- Mypy with subject flags; strict is a stronger optional gate.
- Tests are strongly recommended but not submitted as grading artifacts by the subject; this harness keeps them in-repo for engineering quality unless the evaluator explicitly forbids them.

## README
Final README must be in English and begin with the exact italicized curriculum sentence required by the subject. It must include Description, Instructions, Resources + AI usage, system architecture, chunking strategy, retrieval method, performance analysis, design decisions, challenges, and example usage.

## Bonus gate
Do not implement bonuses until all mandatory behavior is validated. Bonuses are: semantic embeddings, hybrid retrieval, incremental indexing, caching, local HTTP API.
