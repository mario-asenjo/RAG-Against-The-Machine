# Retrieval benchmark ledger

The persisted lexical baseline passes the public recall and warm-retrieval
gates. Private evaluator performance remains unclaimed.

| Run | Commit | Method | Chunking | Index s | Warm search s | Docs R@5 | Code R@5 | Max span | Conclusion |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| M0 | scaffold | n/a | n/a | n/a | n/a | n/a | n/a | n/a | Harness only |
| M2-I1 | 2a34c0a | SQLite FTS5 BM25 | Python structural + text blocks, max 2000 | 41.414 cold; 5.049 refresh | n/a | n/a | n/a | 2000 | 1,969 files / 17,139 exact chunks; indexing gate passes, ranking unmeasured |
| M2-R1 | 8338e96 | SQLite FTS5 BM25, one warm connection per dataset | Existing M2-I1 index | n/a | 16.014 (199 public questions, k=5) | n/a | n/a | 2000 | 100 docs + 99 code questions preserve order; evaluator's private 200-question run remains unclaimed |
| M2-B1 | c05f1c6 | SQLite FTS5 BM25, one warm connection per dataset | Existing M2-I1 index, max 2000 | n/a | 12.187 (199 public questions, k=10) | 0.870 | 0.606 | 2000 | Both mandatory public recall thresholds pass with ample public timing margin; no ranking change justified |

## M2-R1 reproduction record

- Date/time: 2026-08-29 13:33:19-13:33:35 +02:00.
- Branch/SHA: `feat/issue-9-search-dataset` at `8338e96`.
- Inputs: public unanswered docs (100) and code (99) datasets extracted from
  `docs/extra/datasets_public.zip`; persisted M2-I1 index with 1,969 files and
  17,139 chunks, maximum chunk size 2,000.
- Command, run once for each dataset in sequence:

  ```text
  uv run python -m src search_dataset --dataset_path <dataset> --k 5 --save_directory <temporary-output> --index_directory data/processed
  ```
- Warm policy: index construction was outside the timed region; there was no
  query warm-up. Each duration includes Python startup, input validation, one
  SQLite connection, retrieval, model serialization, and output writing.
- Result: docs 7.324 s; code 8.689 s; combined 16.014 s. All 199 question IDs
  and texts retained their order. All outputs validated as
  `StudentSearchResults`; 995 paths/offsets were valid and maximum span was
  2,000. Recall was not calculated because #11 is intentionally still open.
- Change/conclusion: first reproducible batch-throughput smoke; comfortably
  below the timing gate, with no ranking-quality claim or optimization action.

## M2-B1 reproduction record

- Date: 2026-08-29.
- Branch/SHA: `perf/issue-10-public-retrieval-baseline` at `c05f1c6`.
- Retrieval host: Windows 10/Git Bash, CPython 3.14.6 through `uv`; persisted
  M2-I1 index with 1,969 files, 17,139 chunks, and maximum span 2,000.
- Commands, run once per public unanswered dataset:

  ```text
  uv run python -m src search_dataset --dataset_path data/datasets/datasets_public/public/UnansweredQuestions/dataset_docs_public.json --k 10 --save_directory data/output/search_results/UnansweredQuestions
  uv run python -m src search_dataset --dataset_path data/datasets/datasets_public/public/UnansweredQuestions/dataset_code_public.json --k 10 --save_directory data/output/search_results/UnansweredQuestions
  ```
- Warm timing: docs 6.720 s; code 5.467 s; combined 12.187 s. Timings include
  Python startup, validation, retrieval, serialization, and output writing.
- Validation host: WSL Ubuntu 24.04 with the supplied `moulinette-ubuntu` binary,
  `k=10`, and `max_context_length=2000`. Both result files were valid.
- Docs (100 questions): Recall@1 0.600, Recall@3 0.780, Recall@5 0.870,
  Recall@10 0.890.
- Code (99 questions): Recall@1 0.354, Recall@3 0.545, Recall@5 0.606,
  Recall@10 0.667.
- Conclusion: the lexical baseline clears the required public Docs Recall@5
  >= 0.80 and Code Recall@5 >= 0.50. Existing public index and warm retrieval
  timings are comfortably below 300 s and 90 s respectively, but private
  evaluator timing remains unclaimed. Defer code-recall tuning until a measured
  mandatory need appears.
