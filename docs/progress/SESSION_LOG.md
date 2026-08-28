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
