# Session log

Append compact, factual entries. Do not duplicate full PR descriptions.

## 2026-09-25 — #56 adapter-neutral orchestration extraction
- Verified #20 / PR #55 merged at `9f0fb32`, fast-forwarded main, created child #56
  linked from parent #21, added it to Project #12 in In Progress, and opened
  `refactor/issue-56-extract-pipeline-orchestration`. The user-owned roadmap prompt
  remains untracked and untouched.
- Captured a 125-test indexing/retrieval/answer baseline, then moved full/incremental /
  semantic lifecycle and lexical/semantic/hybrid/cache selection out of `RagCli`.
- Added Pydantic index/retrieval/answer commands, structured index outcomes,
  `RagApplication`, one cohesive `PipelineOperations` port, and concrete
  `LocalPipelineOperations`. Fire signatures, progress, formatting, files and errors stay
  adapter-owned; `answer_dataset` and evaluation remain unchanged.
- Added direct shared single/batch/answer tests and a no-peer-adapter import guard. No HTTP
  route/server/framework/dependency was added; FastAPI versus stdlib remains a #21
  decision after this seam merges.
- Full gates passed with 190 tests and strict mypy over 51 files. All six public lexical /
  semantic / hybrid Docs/Code JSON hashes exactly matched their frozen values; no private
  data or campus run was used. Independent Ponytail-full architecture review returned
  ACEPTAR with no blocking ceremony or scope finding.

## 2026-09-24 — #20 persistent retrieval cache
- Verified #18 / PR #54 merged, fast-forwarded local main, created
  `feat/issue-20-persistent-retrieval-cache`, removed the resolved blocked label,
  assigned #20 and moved Project #12 to In Progress. The unrelated roadmap prompt
  remains untracked and untouched.
- RED failed collection because `src.infrastructure.cache` did not exist. Added one lazy
  SQLite `query_cache` table keyed by cache schema, canonical `index_revision`, stable
  retriever signature, exact-query SHA-256 and `k`; values contain only ordered exact
  `MinimalSource` JSON.
- Added explicit `--cache=True` to lexical/semantic/hybrid `search` and `search_dataset`.
  `answer` may cache only its lexical source retrieval while Qwen always runs;
  `answer_dataset` remains unchanged because it never retrieves. No generated-answer
  cache, TTL/LRU, cleanup framework, service, dependency or second database was added.
- Pydantic plus canonical chunk-identity validation rejects corrupt rows. Query/`k` /
  mode/model/fusion/revision changes miss, duplicate batch queries retrieve once, and
  retrieval/write failures create no successful row. A first validation implementation
  issued one SQLite lookup per source and measured 83.926s for a lexical hit; loading the
  17,134 canonical identities once fixed the root cause and reduced the final median hit
  to 0.974s.
- Three-round public no-cache/miss/hit medians over 199 questions were lexical
  4.058/4.320/0.974s, semantic 18.862/18.917/1.029s and hybrid
  34.667/36.291/1.454s. The hybrid first-round 82.488s miss / 4.376s hit outliers are
  retained. Cached/uncached hashes and all Recall cutoffs matched; maximum span stayed
  2,000. No private data was used.
- Each mode stored 199 rows using 284,934-333,404 logical bytes and
  438,272-507,904 allocated bytes. Existing free pages absorbed them, so the
  37,699,584-byte SQLite file did not grow in this run.
- Final local gates passed: 16 cache tests, 186-test `make check`, strict mypy over 46
  files, Flake8, context validation and `git diff --check`. Independent Ponytail-full
  review returned ACEPTAR; a parallel correctness review timed out without a finding.

## 2026-09-23 — #18 hybrid retrieval
- Verified #17 / PR #53 merged at `41bdb01`, fast-forwarded local main, removed #18's
  resolved blocked label, assigned it and moved Project #12 to In Progress. The user's
  unrelated roadmap prompt remains untracked and untouched.
- RED failed collection because `fuse_ranked_sources` did not exist. Added one pure
  equal-weight RRF function with fixed rank constant 60, exact source deduplication,
  distinct overlapping spans and deterministic identity ties.
- Added explicit `--hybrid=True` to `search` and `search_dataset`, reusing existing
  lexical/semantic single and batch paths. Default lexical and explicit semantic modes
  remain unchanged; semantic+hybrid fails clearly. No index, artifact, dependency,
  model, answer path, cache, service, score calibration or tuning knob was added.
- Focused tests cover cross-mode and same-mode duplicates, single-mode candidates,
  canonical ties, near duplicates, limits, single/dataset CLI contracts, stale semantic
  output preservation and traceback-free flag conflicts.
- Public 199-question benchmark: hybrid Docs Recall@1/3/5/10
  0.450/0.700/0.790/0.870; hybrid Code 0.323/0.495/0.596/0.707. Only Code R@10
  improves over BM25. Hybrid took 28.821s versus 4.987s lexical and 22.794s semantic.
- All outputs passed Pydantic shape/`k`/span checks; lexical hashes remained frozen.
  Exact cross-mode duplicate rate was 244/1,000 (24.40%) Docs and 137/990 (13.84%)
  Code, using total lexical top-10 candidates as the denominator.
  Rank-constant and deeper-pool probes produced no broad gain and were not configured.
  No private labels or campus evidence was used.
- Independent correctness review accepted the slice. Ponytail review gaps for exact
  adapter paths, dataset flag conflict and duplicate-rate evidence were applied. Final
  gates: 11 focused tests, 170-test `make check`, strict mypy over 44 files, Flake8,
  context validation and `git diff --check` passed.

## 2026-09-20 — #17 semantic embeddings
- Started from merged #19 at `4b850dc`; kept the unrelated roadmap prompt untracked.
  Removed `blocked`, assigned #17, and moved Project #12 to In Progress.
- RED failed collection because `src.infrastructure.semantic` did not exist. Added one
  pinned raw-Transformers MiniLM CPU adapter, Pydantic metadata, atomic tensor artifact,
  exact canonical identities, explicit index/search flags, and cosine top-k retrieval.
- Reused #19's sole update plan and canonical SQLite chunks. Changed files invalidate
  all vectors; unchanged files reuse exact tensor rows. No dependency, vector database,
  hybrid fusion, alternate hashing/chunking, cache, service, or answer-path change.
- Focused tests cover full/no-op/rebuild/update/failure/stale/search/CLI behavior,
  pooling/normalization, exact paths/offsets, deterministic ties, and lexical fallback
  cleanup. A semantic failure after SQLite advancement preserves the old stale artifact.
- Public benchmark over 1,969 files / 17,134 chunks and 199 questions retained exact
  lexical hashes and Recall. MiniLM Recall@1/3/5/10 was Docs
  0.270/0.410/0.440/0.530 and Code 0.263/0.333/0.404/0.465 versus stronger BM25.
- Full lexical+semantic build took 379.690s; one-file update 19.797s; no-op 5.603s;
  artifact 27,862,262 bytes / `(17134, 384)`. No private data or campus run was used.
- Independent reviews found two real lifecycle/ranking gaps: same-number stale semantic
  state after corrupt lexical fallback and nondeterministic tied `topk`. Lexical-only
  full builds now remove the projection, and top-k boundary ties use canonical order.
- Fresh final gates: 87 focused lexical/semantic/answer/README tests; `make check` with
  159 tests; strict mypy over 42 files; Flake8, context and `git diff --check` passed.

## 2026-09-18 — #19 incremental lexical indexing
- Started from mandatory-audited `87a5c26`; preserved the unrelated CLI edit in named
  stash `user-cli-validation-changes-do-not-publish` and kept the local roadmap prompt
  untracked and untouched.
- Observed RED at collection for the missing incremental lifecycle models/use case.
  Added schema-v2 file hashes, `index_revision`, canonical rank order, explicit
  `--incremental=True`, true no-op, changed-file-only chunking, transactional copy
  updates, integrity validation, atomic replacement and safe visible fallback.
- Fifteen focused tests cover lifecycle state, exact-byte no-op, zero-chunk files,
  exact-source validation, mixed/rename equivalence, stale-term removal, invalid UTF-8,
  SQLite/replacement failure preservation, incompatible schema, inconsistent metadata,
  impossible bounds, complete manifest identity, missing postings and coherent
  chunk-text/FTS corruption fallback.
- Fresh public canonical regression retained 1,969 files / 17,134 chunks, exact frozen
  docs/code output hashes, Recall@1/3/5/10 and 2,000 maximum span. Search took 7.638s
  combined; integrity and chunk/FTS counts passed.
- Three final one-file public-copy rounds measured 2.527s incremental versus 3.004s
  comparable full rebuild median (15.90% faster) and 1.513s no-op median. Every artifact
  matched its equivalent clean full rebuild. No private labels or campus tuning used.
- Independent Ponytail review found and reproduced missing pre-no-op metadata/FTS
  integrity checks plus an optional-manifest fixture shortcut. The manifest is now
  mandatory; one validated state loader checks schema, counts, orphans, spans, ranks,
  FTS external-content integrity and SQLite integrity before no-op/update and after
  mutation. Follow-up reviews found missing chunk-to-manifest bounds, incomplete file
  identity, then missing exact-slice validation for reused chunks; all now have
  permanent regressions and trigger safe rebuild rather than a corrupt no-op.
- Focused tests, 141-test `make check`, strict mypy over 40 files, Flake8 and
  `git diff --check` pass after applying the review findings.
- Final independent Ponytail-full follow-up returned `ACEPTAR` with no remaining
  practical blocker.

## 2026-09-10 — #14 sequential answer_dataset
- Started from merged #13 / PR #39 at `baea9a4`; protected the unrelated local
  12048/1280 budget edit in named stash `user-budget-12048-1280-do-not-publish`.
- RED: all 10 new acceptance cases failed against the placeholder. Implemented one
  sequential loop over validated prior search results, shared #13 answer flow, one
  lazy generator, one lazy/shared/closed SQLite connection, stderr tqdm, and atomic
  Pydantic replacement under the input filename. No retrieval or private data.
- Focused tests pass 40/40. `uv sync --locked`, `make check` (121 tests in 31.68s),
  strict mypy over 34 files, Flake8, context validation, and `git diff --check` pass.
- Public cache-only smoke indexed 1,969 files/17,134 chunks in 5.9469s, prepared two
  `k=1` searches in 0.6742s, and answered both sequentially in 18.4644s. Output
  identity/source lists matched input exactly; the weak second source led Qwen to
  abstain. This is integration evidence, not a quality/private/cache-availability claim.
- One final Ponytail-full review kept the minimal stdlib design and added only a
  replacement-failure regression that kills a possible direct-write implementation;
  the existing production atomic path required no change.

## 2026-09-12 — Post-#40 roadmap triage
- Read `docs/prompts/RAG_MASTER_ROADMAP_MANDATORY_AND_ALL_BONUSES.md` and recorded
  the findings in `docs/project/12_POST_MANDATORY_ROADMAP.md`.
- Current #40 follow-ups are documentation/planning plus the already-identified
  tqdm UX correction; no bonus code belongs in #40.
- Accepted next order: profile `answer_dataset`, benchmark CPU threads, #25 clean
  checkout, #15 defense README, then bonuses #19 -> #17 -> #18 -> #20 -> #21.
- Recorded that performance work must not reduce `max_new_tokens`, shorten answers,
  or add StaticCache without a dedicated benchmark. Private #16 remains blocked
  until explicit authorization.

## 2026-09-12 — #14 nested tqdm follow-up
- Kept #40 mandatory-only and fixed the progress UX in place: dataset tqdm uses
  `position=0, leave=True`; Qwen tokenizer/model/generation phases use
  `position=1, leave=False` during `answer_dataset`.
- Replaced the one-phase generation tick with a tiny Transformers streamer hook
  that updates the generation bar by generated tokens while skipping the prompt
  echo. No answer length, retrieval, cache, concurrency, or backend change.
- Focused checks: `uv run pytest tests/test_answer_dataset.py tests/test_answer.py -q`
  passed with 41 tests. Full `make check` passed with 122 tests in 51.01s;
  strict mypy/Flake8 via `make lint-strict` and `git diff --check` passed.

## 2026-09-12 — #41 public answer_dataset profiling
- Created #41, added it to Project #12, and moved it to In Progress after #40
  merged into main at `96aeee8`.
- Added `scripts/profile_answer_dataset.py`, a public-data profiler over the
  existing answer use case, exact SQLite loader, and Qwen adapter. It records
  source hydration, supported-context lookup, prompt fitting/tokenization,
  generation, prompt/generated tokens, and source counts.
- Ran 10 public code questions for thread settings 4, 8, 10, PyTorch default, and
  16 with `max_new_tokens=128`. Raw JSON lives under ignored
  `data/output/profiling/issue41/`.
- Best total time on this host was explicit 10 threads: 316.973s total / 31.697s
  per question. Current production 4-thread setting took 370.853s. Generation
  dominated every run at 91-97%; source hydration and prompt fitting were small.
  No private data, answer shortening, cache, retrieval change, or concurrency.

## 2026-09-13 — #25 clean checkout and authorized #16 holdout
- Created a disposable worktree at merged `7cd34f8`, staged the supplied corpus,
  public/private datasets, exams and Moulinette, then ran under WSL/v9fs.
- `bootstrap-data.sh` failed because public-root discovery selected its own staging
  directory; filed #43 and used an equivalent manual archive staging workaround.
- Fresh WSL `.venv`: `uv sync --locked` installed 44 packages; `make check` passed
  122 tests. The supplied edge exam passed 4/4. Public search/search_dataset /
  evaluate/answer/answer_dataset smokes and Pydantic identity checks passed.
- Mario explicitly authorized one blind private retrieval run. Indexing passed in
  55s; aggregate Docs Recall@5 was 0.800 PASS and Code Recall@5 was 0.510 PASS.
  No private answered file or question-level result was inspected or copied.
- The script's docs timing crossed a WSL clock discontinuity and was invalid; code
  search reported 115s on mounted v9fs. The private timing gate remains unclaimed
  and the blind evaluation will not be rerun. Campus-native timing remains.
- No production code changed. Tracked status stayed clean; generated/evaluator
  artifacts stayed ignored and the injected `exams/` tree remained unstaged.
- Final post-documentation gates passed: context, Flake8, normal/strict mypy and
  122 tests. Pytest took 909.48s on v9fs, so no timing claim is derived from it.
- Added `scripts/campus_test.sh` to PR #44 for the pending native-Linux follow-up.
  It times setup/check/index/private-unanswered retrieval/public Qwen smokes, saves
  all stdout/stderr with `tee`, validates public batch identity, and prints the
  exact log path to paste back. It never evaluates private labels.
- Script checks passed: `bash -n`, `--help`, a stubbed complete success, and a
  forced-step-failure run proving later steps continue, the log remains complete,
  and the final exit/status reports failure. Final `make check` passed 122 tests;
  strict mypy, Flake8, context validation, and `git diff --check` passed.
- Corrected #43's target after Mario clarified that public archive nesting is
  required: bootstrap must produce `data/datasets/datasets_public/public/`, not
  flattened question directories. Data-layout docs and the campus runner now use
  that exact path; #43 still owns the bootstrap implementation.

## 2026-09-13 — Campus evaluation evidence and #45 plan
- Reviewed all 12 local `evaluations/` artifacts without committing generated
  data: two DOCX transcripts, the campus log, edge summary, and eight edge logs.
- On native campus Ubuntu over `/sgoinfre` NFS4 at merged `e367ecb`, indexing
  passed in 10s and private Recall@5 passed at Docs 0.800 / Code 0.510. Retrieval
  took 46s + 46s = 92s, failing the <=90s gate by 2s.
- Edge artifacts confirm 4/4 real traceback-free outcomes. The answer transcript
  reports 88/100 valid docs questions and three generated answers, but contains
  no final human pass/fail judgment; no formal answer-quality pass is claimed.
- The campus runner's post-check uv steps failed because the NFS working directory
  became unstatable; manual evaluator commands succeeded afterward. Plan: re-enter
  `$ROOT` per runner step rather than masking command failures.
- Created #45 for mandatory uncached retrieval profiling. Persistent query cache
  remains a bonus and cannot help 200 distinct first-seen evaluator questions.
  Compare SQLite options locally one at a time and require unchanged outputs plus
  a stable material gain before retaining a production optimization.

## 2026-09-13 — #43 bootstrap fix on PR #46
- Added one synthetic archive regression reproducing the supplied vLLM, public,
  and private top-level layouts. RED reached the real public `cp: cannot stat`
  failure after correcting a Windows test-path/CRLF harness issue.
- Replaced ambiguous `find */public|private` discovery with exact supplied roots.
  Public nesting is preserved at `data/datasets/datasets_public/public/`; private
  data lands once at `data/datasets/private/`; stale flattened public directories
  are removed.
- Focused test passed. A disposable run against all three real supplied archives
  verified corpus/public/private destinations, no flattened public directories,
  and no `private/private`; the disposable tree was removed.
- Final gates: focused bootstrap test and `bash -n` passed; `make check` passed
  with 123 tests in 87.13s; Flake8, context validation, normal/strict mypy over
  36 files, and `git diff --check` passed.
- Revised #45 per Mario's direction: optimize and repeat locally, require a stable
  >=15% gain, then use at most one campus confirmation rather than iterating there.

## 2026-09-14 — #45 local mandatory retrieval optimization
- Started `perf/issue-45-nfs-retrieval` from merged PR #46 at `c77aa91`; moved #45
  to In Progress and assigned M5 while preserving the unrelated untracked roadmap
  prompt.
- Used only the public 100-doc/99-code datasets and existing public index. Phase
  profiling found 99.92% of local time in FTS execution; the 35.230 MiB index had
  SQLite's approximately 2 MiB default page cache.
- Compared current, read-only, immutable, temp-store, 32/64 MiB page-cache, and mmap
  options one setting at a time. Read-only/immutable/temp-store did not help. mmap
  was slightly faster than page cache but rejected because the target is NFS.
- Retained one batch-local `PRAGMA cache_size=-65536`. Three measured two-process
  public CLI pairs improved from 7.987s median to 5.445s, a 31.83% gain. Baseline
  and candidate docs/code files were byte-identical; public Recall@1/3/5/10 stayed
  Docs 0.600/0.780/0.870/0.890 and Code 0.354/0.545/0.606/0.667.
- Added one focused trace regression for the measured connection setting. Raw
  traces/outputs remain ignored under `data/output/profiling/issue45/`; no private
  labels, persistent query cache, mmap, concurrency, ranking, or generation change.
- Home Windows evidence cannot prove campus NFS performance. One unanswered-input
  campus confirmation remains before the mandatory timing gate can be called green.
- Fresh candidate gates: 22 focused search tests; `make check` with 124 tests in
  87.94s; Flake8, normal/strict mypy over 36 files, context validation and
  `git diff --check` passed. Candidate outputs revalidated 199 questions, 1,990
  sources, `k=10`, and a maximum 2,000-character span.
- Fresh CLI edge smokes returned empty query 2, nonsense query 0, and missing
  dataset 2 with clear diagnostics where applicable and no tracebacks.
- Ponytail-full review found no blocker and retained the one-line SQLite-native
  change plus one regression. Its only caveat matches the documented open risk:
  campus NFS performance remains unverified. Project #12's stale M4 README was
  updated and read back exactly as M5 with #45 active and the bonus gate pending.

## 2026-09-16 — #45 campus confirmation and #25 runner hardening
- Reviewed the metadata and complete log for all eight ignored artifacts from
  campus run `2026-09-15_18-09-20`
  without opening private answered labels. The RAG implementation was merged PR
  #47 commit `6ff741a`; the host was `c3r4s5.42madrid.com` on `/sgoinfre` NFS4.
- Indexing passed in 10.172s. Private unanswered retrieval took 4.079s for 100
  docs questions and 4.114s for 100 code questions: 8.193s combined, passing the
  <=90s gate with 81.807s headroom. No Moulinette/private Recall rerun occurred.
- `uv sync --locked`, 124-test `make check`, single search, `answer --k 0`, public
  Qwen single/batch smokes, batch identity, and edge exam 4/4 all passed; every
  runner step exited 0 and the final result was PASS.
- The result is 91.09% below the prior 92s campus observation, but the host changed
  and the integrity log reports an uncaptured local `scripts/campus_test.sh` edit.
  Recorded the result as compliance evidence, not controlled causal attribution.
- Added the smallest tracked #25 mitigation for the known NFS cwd failure: every
  runner step now executes only after `cd "$ROOT"` and successful `pwd -P`.
  Generated campus outputs remain ignored; the unrelated roadmap prompt remains
  untracked and untouched.
- Fresh follow-up checks: the focused runner contract test passed; `bash -n` and
  `--help` passed; `make check` passed context, Flake8, normal mypy over 37 files,
  and 125 tests in 50.95s; strict mypy and `git diff --check` passed.

## 2026-09-16 — #15 final README and defense readiness
- Re-read the authoritative subject v2.0 and pinned the exact required first README
  line plus every required section with one focused regression; the old harness
  README produced the expected RED before the evaluator-facing English README.
- Replaced scaffold prose with actual installation, architecture, chunking, BM25,
  generation, Pydantic, CLI, benchmark, design, limitation, resource and AI-use
  documentation. Added the requested complete Spanish defense/recode guide at
  `docs/project/16_DEFENSE_GUIDE_ES.md`.
- Disposable clean worktree at `010e568`: staged only supplied public archives,
  created a fresh uv environment, passed 126-test `make check` and strict mypy,
  then exercised every mandatory CLI flow without private data.
- Fresh M5-F1 public result: index 3.551s for 1,969 files / 17,134 chunks; docs
  search 2.314s; code search 2.612s; 4.926s combined. Recall remained Docs
  0.600/0.780/0.870/0.890 and Code 0.354/0.545/0.606/0.667 at k=1/3/5/10.
- Revalidated 199 questions, 1,990 retrieved sources, `k=10`, max span 2,000,
  Pydantic outputs and batch identity. Model-free `k=0`, cache-only Volta answer,
  two-question answer batch and four edge equivalents passed without tracebacks.
- Corpus, datasets, index, outputs, model weights and the unrelated roadmap prompt
  remained ignored/untracked. No private data or label evaluation was used.
- PR #49 merged with green CI at `7c411ef`; issue #15 and milestone M5 closed.
  Project #12 marks #15/PR #49 Done and its README now records mandatory complete.
- Issue #19 was refined and unblocked but remains Todo/unstarted. Its contract keeps
  full rebuild mandatory-default and scopes explicit incremental mode, SHA-256 file
  manifests, atomic transactional updates, deterministic output, `index_revision`,
  full-rebuild equivalence and public timing/Recall evidence.
- The completed Ponytail milestone audit's delayed full result identified one more
  README correction: only Moulinette/evaluation runs are ignored, while supplied
  exam scripts remain untracked. It also clarified that source-free answer batches
  open zero SQLite connections. Both documentation fixes were applied post-M5.

## 2026-09-10 — #13 single-answer Qwen progress
- Added opt-in tqdm phases around tokenizer/config loading, model loading, and
  generation; `RagCli.answer` enables them while the reusable adapter stays quiet.
- Preserved stderr-only progress and the no-model/no-progress abstention path.
- Focused regressions verify each long phase and CLI enablement; a real cache-only
  run displayed all three labels and completed with valid Pydantic output.

## 2026-08-25 — Harness bootstrap
- Distilled subject v2.0, correction scripts, moulinette README, and dataset packaging assumptions.
- Reviewed Mario's existing Fly-In/Codexion agent workflow patterns: incremental slices, explicit invariants, fresh evidence, Ponytail review, detailed issues/PRs, manual merge, and Project synchronization caveats.
- Created initial harness scaffold; no mandatory retrieval functionality claimed.
- External research checked current Hermes progressive-disclosure skill guidance and the current Ponytail Hermes plugin command surface.
- Created GitHub Project #12, opened #1 for bootstrap, and opened #2 as the next implementation slice.
- Fixed bootstrap gates: lint excludes `.venv`, pytest imports `src`, mypy accepts CLI placeholders, and Hermes setup installs the project skill into the active Hermes config home.
- Fresh evidence: `bash scripts/setup-hermes.sh` installs `rag-against-machine`; `make check` passes.

## 2026-08-25 — #2 architecture and model contracts
- Expanded #2 to include the minimal modular-monolith / hexagonal-seam package layout before business logic exists.
- Added the first dependency-boundary rule: `domain` and `application` must not import `adapters` or `infrastructure`.
- Planned bonus seams so semantic/hybrid retrieval and HTTP can be added later without moving search/answer use cases out of CLI code.
- Implemented the Pydantic exchange models, moved Fire into `adapters/cli.py`, and added model/architecture contract tests.
- Fresh evidence: `make check` passes with 11 tests; Ponytail final review reported no blockers or required simplifications.

## 2026-08-26 — Post-#2 state and supplied-artifact policy
- Verified PR #22 merged, issue #2 closed, and Project #12 marked #2 Done.
- Confirmed `docs/extra/` contains local immutable inputs: subject PDF,
  correction archives/binaries, public/private datasets, and the vLLM corpus.
- Kept those artifacts unversioned because they include private holdout data,
  large/third-party inputs, and evaluator binaries; `docs/extra/` is now
  explicitly ignored.
- Selected #4 as the next smallest implementation slice; no retrieval behavior
  is claimed yet.
- Fresh pre-change baseline: `make check` passes with 11 tests.
- Fresh final evidence: both supplied-artifact ignore checks pass and
  `make check` passes with 11 tests.
- Official Ponytail review (`DietrichGebert/ponytail` at `1b2760d`) found the
  docs-only diff lean already (`net: -0 lines possible`).

## 2026-08-26 — #4 exact corpus loading
- Added the `SourceDocument` Pydantic exchange model and deterministic loading
  for the public-ground-truth suffixes `.py`, `.md`, and `.txt`.
- Preserved CRLF and Unicode by reading strict UTF-8 with newline translation
  disabled; unsupported files are skipped and accepted invalid files fail fast.
- Fixture tests cover canonical paths, deterministic order, exact raw text,
  missing roots, ignored suffixes, and invalid UTF-8.
- Real-corpus smoke loaded 1,969 documents with exact decoded text and canonical
  prefixes in 1.392 seconds; no retrieval or recall behavior is claimed.
- Fresh final evidence: `make check` passes with 14 tests and strict mypy passes.
- Official Ponytail review (`DietrichGebert/ponytail` at `1b2760d`) found the
  implementation lean already (`net: -0 lines possible`).

## 2026-08-27 — #5 Markdown/text chunking
- Added `SourceChunk`, a Pydantic source span carrying the exact text slice and
  locking the half-open `[first_character_index:last_character_index]` width
  convention.
- Added a direct string-scanning Markdown/text chunker that groups paragraph-like
  blocks, preserves CRLF/Unicode, returns no chunks for whitespace-only input,
  and splits oversized blocks into bounded exact slices.
- Fixture tests cover block boundaries, exact substring reconstruction,
  whitespace-only input, invalid max size, and oversized-block splitting.
- Fresh final evidence: focused text chunking tests pass with 7 tests;
  `make check` passes with 21 tests.
- Ponytail full review kept the stdlib/no-dependency implementation; no
  simplifications applied or rejected.

## 2026-08-27 — #6 Python chunking
- Added a distinct stdlib `ast`-based Python strategy that starts chunks at
  top-level decorated functions, async functions, and classes without using
  AST byte-column offsets.
- Reused #5's exact bounded range fallback for oversized structures and invalid
  Python while retaining `python` chunk metadata.
- Extended `SourceChunk` with `chunk_type` so persisted index records can retain
  strategy type alongside exact path, half-open span, and text.
- Focused tests cover module code, decorators, comments, docstrings, CRLF,
  Unicode, classes/functions, oversized definitions, invalid syntax, empty
  input, and invalid max size.
- Fresh local-source smoke: 14 Python files produced 37 chunks with exact
  reconstruction and a maximum width of 2000 characters.
- Fresh final evidence: 14 combined chunking tests pass; `make check` passes
  with 28 tests; strict mypy passes over 22 source files.
- Ponytail full review retained one AST scan plus the existing fallback; no
  Protocol, factory, parser dependency, or semantic analysis was added.

## 2026-08-27 — #7 persisted lexical index
- Validated #5/#6 against all 1,969 accepted public vLLM files without opening
  the private holdout; fixed one real trailing-blank-line loss in the text
  block iterator before persistence.
- Added the first real application `Chunker` Protocol and injected the existing
  Python/text callables through an explicit suffix map at the CLI composition
  root; no factory, registry, or persistence port was added.
- Selected stdlib SQLite FTS5 BM25 after a local capability probe, then persisted
  Pydantic metadata, exact chunk path/span/type/text, and FTS retrieval data via
  temporary-file construction plus atomic replacement.
- The evaluator-facing `index` command supports configurable corpus/output paths,
  displays tqdm progress for chunking and FTS construction, and translates
  missing input/persistence failures into Fire errors without tracebacks.
- Full-corpus evidence at implementation commit `2a34c0a`: 1,969 documents,
  17,139 chunks, 36,945,920-byte index, maximum span 2,000, SQLite integrity
  `ok`, exact reconstruction for every non-whitespace document, and a successful
  native BM25 probe.
- Cold observed indexing took 41.414 seconds; deliberate atomic refresh took
  5.049 seconds, both below the 300-second gate. Recall and warm-query timing
  remain intentionally unclaimed until #8/#10.
- Fresh final local gates: `make check` passes with 32 tests and strict mypy
  passes over 26 source files.

## 2026-08-28 — #8 ranked single-query search
- Added one direct stdlib SQLite query over the persisted FTS5 index; no corpus
  loading, new dependency, retriever interface, factory, or cache was added.
- Natural-language input is reduced to quoted Unicode word tokens joined with
  `OR`, preventing FTS syntax errors from punctuation while leaving measured
  recall optimization to #10.
- BM25 score plus persisted chunk ID provides deterministic ranking; results
  project directly to exact `MinimalSource` path and half-open offsets.
- Empty/punctuation-only queries, negative `k`, missing/corrupt indexes, zero
  results, and `k=0` have deliberate traceback-free behavior.
- Retrieval throughput and recall remain unclaimed; probes over ignored local
  data were excluded from the ledger because they are not reproducible evidence.
- Fresh final local gates: `make check` passes with 44 tests and strict mypy
  passes over 27 source files.
- Official Ponytail `full` review used `DietrichGebert/ponytail` at `1b2760d`:
  `Lean already. Ship.` (`net: -0 lines possible`).
- Independent review found that the positive fixture did not distinguish BM25
  ranking from insertion order. The fixture now inserts the weaker match first,
  asserts BM25 reverses that order, and independently asserts `LIMIT k`.
- Fail-closed review also found that index metadata accepted configured sizes
  above 2,000. The domain contract now caps that field at 2,000 and rejects any
  persisted chunk exceeding the configured maximum.
- Follow-up Ponytail `full` review kept the corrective diff unchanged: the two
  domain checks and their regression tests are the minimum complete invariant.

## 2026-08-29 — #9 dataset search and output contracts
- Audited the supplied subject and public unanswered datasets without opening
  private holdout answers; search operations require `StudentSearchResults`.
- Corrected standalone question IDs to use the subject's UUID default and made
  single-query search serialize the same subject wrapper instead of a bare list.
- Added ordered dataset retrieval through one warm SQLite connection with tqdm,
  configurable paths, predictable filenames, and traceback-free input errors.
- Reproducible public smoke processed 100 documentation and 99 code questions
  at `k=5` in 7.324 and 8.689 seconds; all IDs/order matched and 995 sources had
  existing paths, valid offsets, and spans no larger than 2,000 characters.
- Fresh local gates: `make check` passes with 51 tests and strict mypy passes
  over 27 source files after test consolidation.
- Official Ponytail `full` review used `DietrichGebert/ponytail` at `1b2760d`.
  Its duplicate-test-fixture finding was applied by consolidating dataset tests
  into `tests/test_search.py`; production design remained unchanged.

## 2026-08-29 — #10 public retrieval baseline
- Corrected single-query `search` to print ranked
  `file_path [first_character_index:last_character_index]` locations while
  retaining the exact Pydantic wrapper for evaluator-facing dataset output.
- Public `k=10` retrieval took 6.720 seconds for 100 docs questions and 5.467
  seconds for 99 code questions on Windows; the supplied moulinette under WSL
  validated both outputs at Docs Recall@5 0.870 and Code Recall@5 0.606.
- Existing index timing remains below 300 seconds; private timing and recall
  remain unclaimed, and no code-recall optimization was added.
- Fresh final evidence: `make check` passes with 51 tests. Ponytail `full`
  removed the redundant single-query output wrapper and caught Fire's extra
  trailing newline; no new abstraction or dependency was introduced.

## 2026-08-30 — #11 macro Recall@k evaluation
- Added a pure application use case for exact-path, strict IoU > 0.05 source
  matching and macro-averaged per-question Recall@1/3/5/10.
- Explicitly distinguished Recall@k from HitRate@k and micro-recall with
  multi-source regression fixtures; duplicate retrievals cannot inflate recall.
- Added deterministic question-ID validation, empty retrieval handling,
  max-context checks, and traceback-free Fire errors for invalid inputs.
- Regenerated ignored public `k=10` search outputs and reproduced the supplied
  moulinette metrics exactly: Docs 0.600/0.780/0.870/0.890 and Code
  0.354/0.545/0.606/0.667 at Recall@1/3/5/10.
- No ranking, BM25, chunking, index, dependency, or moulinette integration was
  changed. Fresh local gates: `make check` passes with 67 tests.

## 2026-08-30 — #35 post-#11 evaluate polish
- Rounded displayed Recall percentages to one decimal place while preserving the
  underlying macro Recall@k values and exact metric dictionary.
- Added three local typed evaluation errors so student, dataset, and configuration
  failures retain their provenance without inspecting exception strings.
- Updated current state and README CLI contracts; #12 remains the next candidate
  in `Todo`, not active work.
- Focused evaluator tests pass with 25 tests. Fresh final `make check` passes with
  76 tests; Flake8, strict mypy, and context validation pass.
- No IoU, threshold, recall formula, subject model, dependency, retrieval, or
  recorded metric changed. Ponytail `full` kept the three-error local taxonomy.

## 2026-09-05 — #12 retrieval/evaluator edge coverage
- Baseline: 41 focused search/evaluation tests passed after `uv sync` on
  Windows with CPython 3.14.6. Existing production error handling needed no fix.
- Added five regression cases using existing fixture/CLI helpers: no-match and
  zero-limit search success, plus batch missing/corrupt index and empty-query
  failure preserving previous output. No production files/dependencies changed.
- Final focused tests: 46 passed. `make check`: context and Flake8 passed,
  mypy passed over 29 files, 81 tests passed in 28.91s. `git diff --check` passed.
- Eight exact `uv run python -m src` fixture smokes: empty query, missing index,
  missing/malformed search dataset, malformed student and evaluator dataset
  exited 2; gibberish and `k=0` exited 0 with stdout `\n` and empty stderr.
  All were traceback-free. Complete captured argv/stdout/stderr are in the PR.
- No public benchmark rerun: retrieval semantics are unchanged. No private
  inputs, generated outputs, model downloads, or answer implementation used.
- Next candidate after manual merge: #24 CPU-capable Qwen runtime validation;
  #13/#14 integration and #25 final rehearsal remain separate.

## 2026-09-05 — #24 isolated Qwen CPU runtime
- Started from merged #12 / PR #37 at a489fea. Scope is runtime validation only;
  no `src/`, retrieval, source loader, generator interface or answer integration.
- Pinned Transformers 4.57.6 and torch 2.10.0 CPU wheels with an explicit uv index.
  Initial Python 3.14 generation succeeded, but NumPy 2.5 stubs broke the Python
  3.10 mypy target. `.python-version` now selects 3.10; uv sync and gates pass
  with CPython 3.10.20/NumPy 2.2.6 without weakening checks.
- Real Qwen revision c1899de289a04d12100db370d81485cdf75e47ca returned `Paris.`
  in CPU float32/no-thinking mode. Final cache-only process: model load 2.4639s,
  generation 1.0022s; sampled process-tree peak RSS 4,677,201,920 bytes.
  Initial download+load was 51.4322s on Python 3.14, not a like-for-like benchmark.
- Config capacity 40,960 bounds tokenizer 131,072. Complete template is 48 tokens;
  128 reserved output tokens fit the configurable 2,048 budget. Budget 176 succeeds;
  175, 40,961 and zero output reservation fail before loading weights. Sentinel
  handling and render/tokenize equivalence assertions passed with the real tokenizer.
- `docs/project/09_GENERATION_RUNTIME.md` retains exact runnable probe, versions,
  observations and limitations; disposable script is not retained as production.
  Weights/cache stay ignored. Q4 resolved by D-0009; evaluator network/cache Q5
  and full-context memory remain unverified. No private inputs were touched.
- Fresh final local gates: `uv sync --locked`, `make check` (81 tests in 18.55s,
  mypy over 29 files, Flake8/context) and `git diff --check` passed.
- Ponytail full is skill-based; slash review/audit is not exposed. Independent
  review outcome and CI readback belong to the PR. Final clean-clone rehearsal
  remains #25. Next: #13 only after manual merge, then #14 in its own iteration.

## 2026-09-06 — #13 grounded single-query answer
- Started from merged #24 / PR #38 at f31b50e. Updated #13 first to remove
  resolved runtime selection and pin exact lookup, budgeting, abstention, output,
  error and #14 non-goal criteria; Project #12 moved #13 to In Progress.
- RED: `tests/test_answer.py` failed collection because the answer use case did
  not exist. Added 29 focused regressions, then the minimum shared application
  result/use case, one `TextGenerator` Protocol, exact SQLite hydration, lazy
  Qwen adapter and Fire `answer` composition. No domain model/dependency change.
- Exact loader queries path and both offsets per source in received order and
  rejects absent/ambiguous tuples. Budgeting preserves a complete ranked prefix;
  output preserves all retrieved sources and tracks included sources internally.
- `k=0` and no-match smokes succeeded in about 0.7s with a deliberately absent
  local-only model cache, proving fixed Pydantic abstention without model assets.
  Empty query and missing index exited 2 without tracebacks; focused tests also
  cover corrupt index, invalid budget, stale source and model/generation failures.
- Fresh public smoke cloned ignored vLLM tag v0.10.1 at aab5498 and indexed 1,969
  accepted files/17,360 chunks in 24.5199s. This local checkout is not the supplied
  retrieval baseline. Real cache-only Qwen answered `Volta refers to SM 7.0 in
  vLLM hardware documentation.` from one exact 647-character source in 26.5680s.
- Newline-preserving verification matched SQLite text to the original half-open
  slice. Real template: base 66, complete prompt 265, plus 128 reserved = 393
  under budget 2,048 and supported limit 40,960. Sampled process-tree peak RSS:
  4,660,158,464 bytes, with #24 sampling caveats. No private data was used.
- Fresh final local evidence after review fixes: `uv sync --locked`; 29 focused tests;
  `make check` (110 tests in 124.01s, mypy 33 files, Flake8/context); strict mypy;
  and `git diff --check` all passed. Exact commands/output live in the PR and
  `docs/project/10_GROUNDED_ANSWER.md`.
- Initial independent correctness review found no implementation blocker. Ponytail
  mutation audit found two test-contract gaps: dropping context from the real Qwen
  message or skipping a non-fitting ranked source could stay green. Added a real
  adapter message/options regression and a three-source strict-prefix regression;
  both mutation classes are now detected without adding production code. The
  generation path now has its own grounded/no-thinking template regression. A
  follow-up assertion proves all retrieved sources reach hydration, and a real
  SQLite case rejects a stale source even outside the fitted prompt prefix. The
  re-audit then showed generation-specific context/thinking mutations survived;
  a tokenizer/model-fake test now pins the actual generate-side message and flags.
  The first re-review killed five requested mutations (count/generate context,
  generate thinking, ranked skip, partial hydration) at 24 focused/105 full tests.
  A later-delivered audit found supported-context, non-positive/equal reservation,
  and whitespace-only output guards insufficiently pinned. Five additional cases
  now protect them without production changes; final evidence is 29 focused/110
  full tests.
- #14 remains Todo/unstarted: no dataset loop, tqdm batch generation, shared batch
  connection/model lifecycle assertion, or atomic batch replacement in this slice.
