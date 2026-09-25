# Retrieval benchmark ledger

The persisted lexical baseline passes the public recall and warm-retrieval
gates. One explicitly authorized blind private run passed both Recall@5 thresholds,
and the later unanswered-input native-Linux confirmation passed the timing gate
without reopening private labels.

| Run | Commit | Method | Chunking | Index s | Warm search s | Docs R@5 | Code R@5 | Max span | Conclusion |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| M0 | scaffold | n/a | n/a | n/a | n/a | n/a | n/a | n/a | Harness only |
| M2-I1 | 2a34c0a | SQLite FTS5 BM25 | Python structural + text blocks, max 2000 | 41.414 cold; 5.049 refresh | n/a | n/a | n/a | 2000 | 1,969 files / 17,139 exact chunks; indexing gate passes, ranking unmeasured |
| M2-R1 | 8338e96 | SQLite FTS5 BM25, one warm connection per dataset | Existing M2-I1 index | n/a | 16.014 (199 public questions, k=5) | n/a | n/a | 2000 | 100 docs + 99 code questions preserve order; evaluator's private 200-question run remains unclaimed |
| M2-B1 | c05f1c6 | SQLite FTS5 BM25, one warm connection per dataset | Existing M2-I1 index, max 2000 | n/a | 12.187 (199 public questions, k=10) | 0.870 | 0.606 | 2000 | Both mandatory public recall thresholds pass with ample public timing margin; no ranking change justified |
| M5-C1 | 7cd34f8 | Same mandatory SQLite FTS5 BM25 | Clean checkout, max 2000 | 55 | invalid on WSL/v9fs | 0.800 private | 0.510 private | 2000 | One authorized blind run; Recall gates pass, timing gate unclaimed due clock discontinuity and mounted filesystem |
| M5-C2 | e367ecb | Same mandatory SQLite FTS5 BM25 | Campus NFS4, max 2000 | 10 | 92 (46 docs + 46 code; 200 private questions, k=10) | 0.800 private | 0.510 private | 2000 | Recall/index gates pass; warm retrieval fails by 2s, so mandatory performance work #45 blocks bonus unlock |
| M5-P1 | local #45 candidate | Same BM25 with 64 MiB per-connection SQLite page cache | Existing public index, max 2000 | n/a | 5.445 median (199 public questions, k=10; home Windows) | 0.870 | 0.606 | 2000 | 31.83% faster than 7.987s local median across three CLI pairs; byte-identical output; campus NFS confirmation still required |
| M5-C3 | 6ff741a | Same BM25 with 64 MiB per-connection SQLite page cache | Campus NFS4, max 2000 | 10.172 | 8.193 (4.079 docs + 4.114 code; 200 private unanswered questions, k=10) | not rerun | not rerun | 2000 previously pinned | Mandatory timing passes with 81.807s headroom; host and dirty-runner differences prevent assigning the full 91.09% reduction to page cache |
| M5-F1 | 010e568 | Final mandatory SQLite FTS5 BM25 | Disposable clean checkout, supplied public corpus, max 2000 | 3.551 | 4.926 (2.314 docs + 2.612 code; 199 public questions, k=10) | 0.870 | 0.606 | 2000 | Final public rehearsal reproduces Recall, output shape, all mandatory commands, Qwen smokes and edge behavior |
| B1-I1 | #19 branch | Schema-v2 BM25 plus explicit file-level incremental updates | Full public corpus, SHA-256 manifest, max 2000 | 8.430 cold full; 2.527 one-file median vs 3.004 comparable full; 1.513 no-op median | 7.638 (3.676 docs + 3.961 code; 199 public questions, k=10) | 0.870 | 0.606 | 2000 | Mandatory output hashes/Recall unchanged; final three rounds show 15.90% median one-file gain, exact reused-slice/lifecycle/FTS validation and full-rebuild equivalence |
| B2-S1 | #17 branch | Optional all-MiniLM-L6-v2 cosine; BM25 remains default | Same canonical 17,134 chunks, 384-d normalized tensor | 379.690 full lexical+semantic; 19.797 one-file update; 5.603 no-op | 14.082 semantic vs 3.887 lexical (199 public questions, k=10) | 0.440 semantic / 0.870 lexical | 0.404 semantic / 0.606 lexical | 2000 | 27,862,262-byte artifact; standalone semantic underperforms BM25, so no default change or tuning |
| B3-H1 | #18 branch | Optional equal-weight RRF over existing BM25 + MiniLM ranks | Existing canonical chunks/indexes; fixed rank constant 60; top-k from each mode | n/a; no new artifact/build | 28.821 hybrid vs 4.987 lexical vs 22.794 semantic (199 public questions, k=10) | 0.790 hybrid / 0.870 lexical / 0.440 semantic | 0.596 hybrid / 0.606 lexical / 0.404 semantic | 2000 | Hybrid improves Code R@10 to 0.707 but reduces other BM25 cutoffs; stays explicit with no weight tuning |
| B4-C1 | #20 branch | Optional SQLite exact-query retrieval-result cache for lexical / semantic / hybrid | Same canonical 17,134 chunks; revision + signature + exact-query hash + k key | n/a; lazy table in lexical SQLite | Median hit 0.974 / 1.029 / 1.454s vs no-cache 4.058 / 18.862 / 34.667s (lexical / semantic / hybrid; 199 questions) | unchanged: 0.870 / 0.440 / 0.790 | unchanged: 0.606 / 0.404 / 0.596 | 2000 | No-cache/miss/hit hashes and Recall identical; misses add overhead, so cache stays explicit and never stores generated answers |

## B4-C1 persistent retrieval cache record

- Date/branch: 2026-09-24, `feat/issue-20-persistent-retrieval-cache`.
- Fixed public input: canonical 1,969-file / 17,134-chunk SQLite index, 100 Docs +
  99 Code distinct questions, `k=10`, two CLI processes per observation, three rounds;
  no private data.
- Key: cache schema 1, canonical `index_revision`, deterministic mode/configuration
  signature, SHA-256 of exact UTF-8 query and `k`. Values contain only ordered exact
  `MinimalSource` JSON validated by Pydantic and canonical chunk identity.
- Lexical no-cache/miss/hit observations: 3.967/4.061/4.058s,
  4.197/4.450/4.320s, 0.946/0.994/0.974s; medians 4.058/4.320/0.974s.
- Semantic no-cache/miss/hit observations: 18.831/18.928/18.862s,
  18.917/19.798/18.910s, 0.996/1.029/1.067s; medians 18.862/18.917/1.029s.
- Hybrid no-cache/miss/hit observations: 35.330/34.667/31.555s,
  82.488/31.266/36.291s, 4.376/1.454/1.189s; medians
  34.667/36.291/1.454s. First-round host outliers are retained.
- Every no-cache/miss/hit JSON hash matched within its mode. Fresh Recall@1/3/5/10
  exactly reproduced B2/B3: lexical Docs 0.600/0.780/0.870/0.890 and Code
  0.354/0.545/0.606/0.667; semantic Docs 0.270/0.410/0.440/0.530 and Code
  0.263/0.333/0.404/0.465; hybrid Docs 0.450/0.700/0.790/0.870 and Code
  0.323/0.495/0.596/0.707.
- All modes retained 199 questions / 1,990 sources and maximum span 2,000. Each stored
  199 rows. Logical bytes were 284,934 lexical, 308,166 semantic and 333,404 hybrid;
  SQLite allocated 438,272/471,040/507,904 bytes from free pages, so the
  37,699,584-byte file did not grow in these runs.
- Distinct first-seen misses did not improve and added validation/write overhead. This
  bonus targets actual repetition and does not replace mandatory uncached performance.
  `answer` may cache only lexical retrieval; Qwen output is never cached.
- Full details are in `docs/project/20_PERSISTENT_RETRIEVAL_CACHE.md`; raw traces and
  copied indexes remain ignored under `data/output/issue20/`.

## B3-H1 hybrid retrieval record

- Date/branch: 2026-09-23, `feat/issue-18-hybrid-retrieval`.
- Fixed public input: canonical relative `data/raw/vllm-0.10.1`, 1,969 files,
  17,134 chunks, 100 docs + 99 code questions, `k=10`; no private data.
- Fusion: equal-weight reciprocal rank fusion over the existing top-10 lists, fixed
  rank constant 60, exact path/offset deduplication, deterministic identity ties.
- Recall@1/3/5/10: lexical Docs 0.600/0.780/0.870/0.890, semantic Docs
  0.270/0.410/0.440/0.530, hybrid Docs 0.450/0.700/0.790/0.870.
- Recall@1/3/5/10: lexical Code 0.354/0.545/0.606/0.667, semantic Code
  0.263/0.333/0.404/0.465, hybrid Code 0.323/0.495/0.596/0.707.
- Timings: lexical 2.374s docs + 2.613s code = 4.987s; semantic 11.437s +
  11.357s = 22.794s; hybrid 14.418s + 14.403s = 28.821s.
- All outputs validate as `StudentSearchResults`, preserve `k=10`, contain at most ten
  exact sources per question, and have maximum span 2,000. Lexical hashes remain frozen.
- Exact cross-mode duplicate rate, defined as summed per-question identity intersections
  divided by total lexical top-10 candidates, was 244/1,000 (24.40%) Docs and 137/990
  (13.84%) Code; semantic candidate denominators were equal in size.
- Hybrid improved only Code Recall@10 over BM25. Public probes of rank constants and
  a 20-candidate pool produced no broad gain, so neither became configuration. No
  default, dependency, persisted artifact, private-label or campus change was made.
- Full details are in `docs/project/19_HYBRID_RETRIEVAL.md`; generated outputs remain
  ignored.

## B2-S1 semantic retrieval record

- Date/branch: 2026-09-20, `feat/issue-17-semantic-embeddings`.
- Fixed public input: canonical relative `data/raw/vllm-0.10.1`, 1,969 files,
  17,134 canonical chunks, 100 docs + 99 code questions, `k=10`; no private data.
- Pinned MiniLM revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, CPU
  float32, attention-mask mean pooling, L2 normalization, max length 256.
- BM25 Recall@1/3/5/10: Docs 0.600/0.780/0.870/0.890 and Code
  0.354/0.545/0.606/0.667. Search took 1.819s + 2.069s = 3.887s.
- Semantic Recall@1/3/5/10: Docs 0.270/0.410/0.440/0.530 and Code
  0.263/0.333/0.404/0.465. Final post-review search took
  7.077s + 7.005s = 14.082s.
- Full lexical+semantic construction took 379.690s. One changed-file semantic update
  took 19.797s and a validated no-op took 5.603s. The artifact was 27,862,262 bytes
  with shape `(17134, 384)`.
- Lexical docs/code output SHA-256 values remained exactly frozen. The optional full
  semantic timing exceeds 300s on this host, but the mandatory lexical-only default
  and its timing gate are unchanged. See `docs/project/18_SEMANTIC_EMBEDDINGS.md`.

## B1-I1 incremental indexing record

- Date/branch: 2026-09-18, `feat/issue-19-incremental-indexing`.
- Fixed public input: canonical relative `data/raw/vllm-0.10.1`, 1,969 accepted
  files, 17,134 exact chunks, `max_chunk_size=2000`; no private data.
- Fresh schema-v2 full build took 8.430s. An unchanged explicit incremental run took
  2.961s without replacing SQLite or changing revision.
- Public `k=10` search took 3.676s docs + 3.961s code = 7.638s. Output SHA-256 and
  Recall@1/3/5/10 exactly matched the frozen mandatory baseline; maximum span stayed
  2,000.
- A disposable corpus copy received one changed file per round with incremental/full
  execution order rotated after all independent-review fixes. Incremental times were
  25.125/2.527/2.520s; full rebuilds 3.023/2.996/3.004s; no-ops
  1.557/1.511/1.513s. Medians were 2.527/3.004/1.513s, a 15.90% incremental
  improvement. Every canonical chunk/result matched its clean
  full rebuild and each no-op kept revision unchanged.
- The first final incremental observation was a 25.125s host outlier. It is retained
  in the raw record and table; the three-run median is used rather than deleting it.
- The 37,670,912-byte canonical artifact passed `PRAGMA integrity_check`, held 1,969
  manifest rows (122 zero-chunk files), and had 17,134 chunk + 17,134 FTS rows.
- An initial absolute-path run was rejected as quality evidence after correctly
  producing absolute source paths that could not match canonical ground truth. The
  relative-path rerun above is authoritative. Full details are in
  `docs/project/17_INCREMENTAL_INDEXING.md`; generated traces remain ignored.

## M5-F1 final public clean-checkout rehearsal

- Disposable detached worktree at #15 commit `010e568`; supplied vLLM/public
  archives staged only under ignored paths with `scripts/bootstrap-data.sh`.
- Fresh `.venv`: `uv sync --locked` installed 44 packages; `make check` passed
  context, Flake8, mypy over 38 files and 126 tests; strict mypy passed.
- Indexed 1,969 documents into 17,134 chunks in 3.551s.
- Public `k=10`: docs 2.314s, code 2.612s, 4.926s combined. Local evaluation
  reproduced Docs 0.600/0.780/0.870/0.890 and Code
  0.354/0.545/0.606/0.667 at Recall@1/3/5/10.
- Both outputs revalidated as `StudentSearchResults`: 199 questions, 1,990
  retrieved sources, exact `k=10`, and maximum span 2,000.
- `search`, `search_dataset`, `evaluate`, model-free `answer --k 0`, a cache-only
  public Volta answer, and a two-question cache-only `answer_dataset` all passed.
  The Volta answer was `Volta refers to SM 7.0.` from one exact source; batch
  ID/question/source/`k` identity revalidated.
- The four supplied edge-command equivalents returned expected exits 2/0/0/2 and
  no tracebacks. Runtime artifacts, corpus, index, outputs and model cache remained
  ignored; no private data was staged or used.

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
- Conclusion: optimize against repeatable local public runs first, requiring a
  stable >=15% improvement with unchanged outputs. Use at most one later campus
  confirmation. Query caching is not applicable because the mandatory workload
  contains distinct questions in fresh processes.

## M5-P1 local retrieval optimization

- Fixed workload: two fresh CLI processes over 100 public docs plus 99 public code
  questions, `k=10`, existing 35.230 MiB SQLite index, one warm-up pair followed by
  three measured pairs.
- Baseline combined runs: 8.015s, 7.987s, 7.967s; median 7.987s.
- 64 MiB page-cache runs: 5.445s, 5.631s, 5.187s; median 5.445s.
- Median improvement: 31.83%. Baseline/candidate output files were byte-identical.
- Public recall stayed Docs 0.600/0.780/0.870/0.890 and Code
  0.354/0.545/0.606/0.667 at Recall@1/3/5/10.
- Phase profiling attributed 99.92% of the baseline to FTS execution. Read-only /
  immutable URI and temp-store changes did not help. mmap was slightly faster but
  rejected as a riskier filesystem-dependent choice for the actual NFS target.
- This is a home Windows measurement, not a campus result. Details and the one-run
  confirmation rule are in `docs/project/15_RETRIEVAL_PERFORMANCE.md`.

## M5-C3 native campus confirmation

- Date/run: 2026-09-15, `evaluations/campus/2026-09-15_18-09-20/`.
- Commit: merged PR #47 at `6ff741a`; host `c3r4s5.42madrid.com`, Intel i5-8500,
  6 cores, 7.6 GiB RAM, `/sgoinfre` NFS4, Python 3.10.12, uv 0.12.15.
- Index: 10.172s for 1,969 documents and 17,134 chunks.
- Private unanswered retrieval only: docs 4.079s, code 4.114s, combined 8.193s.
  The <=90s gate passes with 81.807s headroom.
- Private labels/Moulinette were not opened or run. Prior Recall aggregates were
  not re-evaluated and remain separate M5-C2 evidence.
- Compared with M5-C2's 92s observation, elapsed time fell 83.807s / 91.09%
  (11.23x). Treat this as a cross-host confirmation, not causal attribution:
  host/load differed and the runner integrity report contained an uncaptured
  local `scripts/campus_test.sh` modification.
- `uv sync`, 124-test `make check`, public Qwen single/batch smokes, exact batch
  identity, and edge exam 4/4 also passed. Every runner step exited 0.

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
