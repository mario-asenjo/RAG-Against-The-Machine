# RAG Against the Machine — Agent Operating Contract

This file is the always-on operating contract for Hermes Agent and any other coding agent working in this repository.

## Mission
Implement the 42 project **RAG against the machine, subject v2.0** incrementally, measurably, and defensibly. The mandatory retrieval pipeline comes first. Every non-trivial change must be linked to a GitHub issue, validated locally, reviewed with Ponytail, synchronized with the GitHub Project when access permits, and delivered through a complete PR.

Communicate with Mario in Spanish unless he asks otherwise. Keep source identifiers, code comments, docstrings, commit messages, evaluator-facing README content, issues, and PR technical sections in English unless a repository convention already requires Spanish.

## Mandatory session start
Before editing anything:

1. Read `AGENTS.md`.
2. Read `docs/project/01_SOURCE_OF_TRUTH.md`.
3. Read `docs/project/02_REQUIREMENTS_DISTILLED.md`.
4. Read `docs/project/03_EVALUATION_CONTRACT.md`.
5. Read `docs/progress/CURRENT.md`, `OPEN_QUESTIONS.md`, `RISKS.md`, and `DECISION_LOG.md`.
6. Inspect `git status`, current branch, latest relevant commits, and the current diff. Preserve unrelated user changes.
7. Inspect the repository's open GitHub issues and the associated GitHub Project before planning work. Never assume the local roadmap is newer than GitHub.
8. Find the smallest open issue/slice that satisfies the user's request. Do not silently expand scope.
9. Activate Ponytail in `full` mode for implementation/refactor/review work.
10. State: current milestone, linked issue, verified baseline, main risk, and proposed smallest next step.

If GitHub Project access is unavailable because the token lacks `read:project`/`project` scope, document that limitation in the issue/PR or session log. Never claim Project synchronization when it was not actually performed.

## Source-of-truth order
Resolve conflicts in this order:

1. User's explicit current instruction.
2. Subject `RAG against the machine`, version 2.0.
3. Provided exam scripts and corrector guide where they clarify how the subject is executed.
4. Provided moulinette behavior/output contract.
5. Public datasets for development evidence.
6. Accepted ADRs/decision log.
7. GitHub issue acceptance criteria for the active slice.
8. Ponytail simplification advice.

Private datasets are a **holdout**. Do not inspect their ground-truth answers/source spans to tune retrieval. They may be used only for an explicitly authorized final/blind validation run. This prevents accidental evaluator overfitting.

## Non-negotiable subject constraints

- Python 3.10 or later.
- `uv` is the package/project manager; evaluator runs `uv sync` from repository root.
- Flake8 must pass.
- Mypy must pass with the subject flags; strict mode is a desired stronger gate.
- Type hints and PEP 257-style docstrings are required.
- Data exchanged between pipeline stages uses Pydantic models. Evaluator-facing
  JSON must be built with the exact subject wrapper model and serialized from
  that model, never assembled from ad hoc dictionaries.
- CLI uses Python Fire.
- Long-running operations use tqdm progress bars.
- Default answer model is `Qwen/Qwen3-0.6B`; alternatives are allowed only if the project still works with it.
- Implement two distinct chunking strategies: Python code and Markdown/text.
- Implement at least one classic lexical retriever: BM25 or TF-IDF.
- `--max_chunk_size` defaults to 2000 characters and no emitted source may exceed 2000 characters.
- Preserve source character offsets against the exact original file content.
- Returned `file_path` must match the ingested corpus path exactly, including prefix.
- Persist the index under `data/processed/`.
- Required CLI shape: `uv run python -m src <command> [options]`.
- Required commands: `index`, `search`, `search_dataset`, `answer`, `answer_dataset`, `evaluate`.
- All I/O paths are configurable; do not hard-code evaluator paths.
- The solution must not import or call the moulinette.
- Degenerate inputs must fail gracefully without unhandled tracebacks.
- Indexing whole corpus: <= 300 seconds.
- Warm retrieval: 200 questions <= 90 seconds.
- Docs Recall@5 >= 80%.
- Code Recall@5 >= 50%.
- Do not commit large datasets, vLLM corpus, model weights, generated outputs, or private evaluator data.

## Architecture rule
Start with the smallest modular monolith that preserves exact offsets and lets each mandatory stage be tested independently. Do not create speculative abstractions.

Recommended responsibility seams:

- `models`: exact Pydantic exchange models.
- `chunking`: source-preserving Python and text chunkers.
- `indexing`: corpus traversal and persisted lexical index.
- `retrieval`: ranked chunk search and source-location projection.
- `generation`: prompt/context assembly and local model invocation.
- `pipeline`: dataset orchestration and file output.
- `cli` / `__main__`: Python Fire boundary and graceful error translation.

Do not add interfaces, repositories, factories, dependency-injection containers, databases, async workers, HTTP APIs, semantic embeddings, hybrid retrieval, incremental indexing, or caching before a measured need or the corresponding bonus issue.

## Vertical-slice workflow
For every non-trivial issue:

1. Re-read the issue and acceptance criteria.
2. Confirm the branch contains only the intended scope.
3. Define observable behavior and a reproducible failing check/test when practical.
4. Implement the minimum code required.
5. Run the narrowest relevant test/check.
6. Run all gates affected by the change.
7. Run `/ponytail-review` on the diff.
8. Apply simplifications that preserve requirements; reject unsafe deletions with a concrete requirement/test reference.
9. Update `docs/progress/` and benchmark/evidence files only with fresh results.
10. Push and open/update a complete PR tied to the issue.
11. Read back CI. Do not call a PR ready while required checks are red or unknown.
12. Keep merge manual unless Mario explicitly asks otherwise.

At milestone boundaries, additionally run `/ponytail-audit` and a clean-clone rehearsal where practical.

## GitHub operating contract
GitHub is part of the project state, not an afterthought.

### Issues
Every implementation slice must have an issue before coding unless the user explicitly asks for an emergency one-line fix. Issues must include:

- goal/problem;
- source context and requirement references;
- scope;
- explicit non-goals;
- acceptance criteria / Definition of Done;
- expected tests/evidence;
- performance/compatibility risks;
- dependencies/blockers;
- Project/milestone information when available.

Prefer one issue per vertical slice. Split issues when acceptance can be independently demonstrated or when a diff would mix unrelated concerns.

### Project
At session start, inspect the associated GitHub Project. The Project should mirror issue reality, not replace issues. Keep status aligned with actual work (`Backlog` -> `Ready` -> `In progress` -> `Review` -> `Done`, or the project's existing equivalent). Do not create a second Project when one already exists.

### Branches and commits
Use small issue-scoped branches, e.g. `feat/issue-12-python-chunker`, `fix/issue-23-exact-paths`, `perf/issue-31-retrieval-throughput`. Keep `main` runnable. Use imperative scoped commits. Never mix generated data or unrelated formatting churn with behavior.

### Pull requests
A PR must be reviewable and defendable. It should include:

- linked issue (`Closes #N` when appropriate);
- summary and motivation;
- exact scope and non-goals;
- files/components changed;
- design/data flow;
- subject/evaluator invariants checked;
- tests and fresh command output;
- recall/performance evidence when relevant;
- edge cases;
- risks/compatibility/reversal;
- documentation updates;
- Ponytail review outcome;
- CI/check status;
- next follow-up issue if one exists.

Never fabricate test or CI evidence. If a check was not run, say so and leave it unchecked.

## Ponytail supervision
Ponytail is the minimalism supervisor, not the product owner.

Use:

- default coding mode: `full`;
- after every non-trivial slice: `/ponytail-review`;
- milestone/release boundary: `/ponytail-audit`;
- `ultra` only when explicitly requested;
- `off` only temporarily to diagnose a conflict, with reason recorded.

Never accept a simplification that breaks exact source offsets, path fidelity, required data models/CLI, exception safety, evaluator timing, retrieval quality, grounding, or meaningful tests.

## Benchmark discipline
Optimization is evidence-driven:

1. Establish a public-dataset baseline.
2. Change one retrieval/chunking variable at a time when practical.
3. Record configuration, commit, chunk statistics, index time, retrieval time, Recall@1/3/5/10, and notes.
4. Prefer gains that improve both docs and code or have an explicit dataset-specific rationale.
5. Do not tune against private ground truth.
6. Keep all retrieved sources <= 2000 characters.
7. Re-run edge-case tests after CLI/error-path changes.

## Completion response
When handing a slice back, report:

1. Outcome.
2. Issue/branch/PR.
3. Files changed.
4. Fresh validation evidence.
5. Recall/performance evidence if relevant.
6. Ponytail findings applied/rejected.
7. Project/issue synchronization status.
8. Remaining risk/limitation.
9. Smallest sensible next issue, without starting it automatically.
