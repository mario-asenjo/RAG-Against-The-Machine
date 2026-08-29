# Retrieval benchmark ledger

Indexing and public warm-retrieval baselines exist; recall remains unmeasured.

| Run | Commit | Method | Chunking | Index s | Warm search s | Docs R@5 | Code R@5 | Max span | Conclusion |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| M0 | scaffold | n/a | n/a | n/a | n/a | n/a | n/a | n/a | Harness only |
| M2-I1 | 2a34c0a | SQLite FTS5 BM25 | Python structural + text blocks, max 2000 | 41.414 cold; 5.049 refresh | n/a | n/a | n/a | 2000 | 1,969 files / 17,139 exact chunks; indexing gate passes, ranking unmeasured |
| M2-R1 | 8338e96 | SQLite FTS5 BM25, one warm connection per dataset | Existing M2-I1 index | n/a | 16.014 (199 public questions, k=5) | n/a | n/a | 2000 | 100 docs + 99 code questions preserve order; evaluator's private 200-question run remains unclaimed |

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
