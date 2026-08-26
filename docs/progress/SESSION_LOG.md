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
