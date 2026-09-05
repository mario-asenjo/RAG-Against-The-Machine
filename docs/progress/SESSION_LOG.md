# Session log

Append compact, factual entries. Do not duplicate full PR descriptions.

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
