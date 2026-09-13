# Retrieval benchmark ledger

The persisted lexical baseline passes the public recall and warm-retrieval
gates. One explicitly authorized blind private run passed both Recall@5 thresholds;
private native-Linux retrieval timing remains unclaimed.

| Run | Commit | Method | Chunking | Index s | Warm search s | Docs R@5 | Code R@5 | Max span | Conclusion |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| M0 | scaffold | n/a | n/a | n/a | n/a | n/a | n/a | n/a | Harness only |
| M2-I1 | 2a34c0a | SQLite FTS5 BM25 | Python structural + text blocks, max 2000 | 41.414 cold; 5.049 refresh | n/a | n/a | n/a | 2000 | 1,969 files / 17,139 exact chunks; indexing gate passes, ranking unmeasured |
| M2-R1 | 8338e96 | SQLite FTS5 BM25, one warm connection per dataset | Existing M2-I1 index | n/a | 16.014 (199 public questions, k=5) | n/a | n/a | 2000 | 100 docs + 99 code questions preserve order; evaluator's private 200-question run remains unclaimed |
| M2-B1 | c05f1c6 | SQLite FTS5 BM25, one warm connection per dataset | Existing M2-I1 index, max 2000 | n/a | 12.187 (199 public questions, k=10) | 0.870 | 0.606 | 2000 | Both mandatory public recall thresholds pass with ample public timing margin; no ranking change justified |
| M5-C1 | 7cd34f8 | Same mandatory SQLite FTS5 BM25 | Clean checkout, max 2000 | 55 | invalid on WSL/v9fs | 0.800 private | 0.510 private | 2000 | One authorized blind run; Recall gates pass, timing gate unclaimed due clock discontinuity and mounted filesystem |
| M5-C2 | e367ecb | Same mandatory SQLite FTS5 BM25 | Campus NFS4, max 2000 | 10 | 92 (46 docs + 46 code; 200 private questions, k=10) | 0.800 private | 0.510 private | 2000 | Recall/index gates pass; warm retrieval fails by 2s, so mandatory performance work #45 blocks bonus unlock |

## M5-C2 campus reproduction record

- Host: `c2r13s5.42madrid.com`, Ubuntu 5.15 kernel, Intel Core i5-8500 with
  6 cores / 6 threads, 7.6 GiB RAM.
- Filesystem: campus `/sgoinfre` NFS4 mount.
- Commit: merged `e367ecb`.
- Exact evaluator script: `exam_retrieval.sh --student-path .
  --moulinette-path ./moulinette-ubuntu`.
- Index: 10s. Docs: 46s. Code: 46s. Combined: 92s, failing the strict 90s
  gate by 2s (2.22%).
- The user-run campus evaluator reproduced Docs Recall@5 0.800 and Code Recall@5
  0.510 at the same frozen configuration. No parameter changed between the WSL
  and campus runs; no further private-label evaluation or tuning is authorized.
- Conclusion: seek a stable <=80s campus result with unchanged outputs. Query
  caching is not applicable because the mandatory workload contains distinct
  questions in fresh processes.

## Answer generation timing notes

These timings are not retrieval recall benchmarks and do not use private data.

- #14 public cache-only two-question smoke: `answer_dataset` completed in 18.4644s
  after a 5.9469s public-corpus index and 0.6742s retrieval preparation.
- Roadmap review baseline for public code dataset: 99 questions, 40:48 total,
  about 24.73s/question. Observed generation varied roughly 9.84-59.98s/question;
  tokenizer/model setup was not the dominant repeated cost.
- Next evidence slice: fixed 10-15 public-question profiling with phase timings and
  CPU thread counts 4, 8, 10, PyTorch default, and 16. Do not reduce
  `max_new_tokens` for this performance work.

## M5-A1 answer_dataset CPU-thread profiling

- Date: 2026-09-12.
- Branch: `perf/issue-41-answer-dataset-profile`.
- Input: first 10 public code search results with non-empty sources from
  `data/output/search_results/UnansweredQuestions/dataset_code_public.json`.
- Model/cache: Qwen/Qwen3-0.6B local cache only, `token_budget=2048`,
  `max_new_tokens=128`; no private data.
- Script: `uv run python scripts/profile_answer_dataset.py ... --limit 10`.

| Threads | Effective | Total s | Avg s/q | Generation s | Gen share | Fit/tokenize s | Hydrate s | Generated tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 4 | 370.853 | 37.085 | 357.619 | 0.964 | 0.223 | 5.182 | 398 |
| 8 | 8 | 379.500 | 37.950 | 345.370 | 0.910 | 0.220 | 4.679 | 398 |
| 10 | 10 | 316.973 | 31.697 | 305.794 | 0.965 | 0.204 | 4.410 | 398 |
| default | 10 | 331.957 | 33.196 | 320.679 | 0.966 | 0.199 | 4.710 | 398 |
| 16 | 16 | 320.808 | 32.081 | 293.393 | 0.914 | 0.198 | 4.558 | 398 |

Conclusion: generation dominates. Do not optimize retrieval/source hydration,
prompt fitting, caching, or answer length from this evidence. The smallest useful
runtime candidate is removing or parameterizing the hard-coded 4-thread setting;
10 threads was fastest on this host, while PyTorch default also resolved to 10.

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
