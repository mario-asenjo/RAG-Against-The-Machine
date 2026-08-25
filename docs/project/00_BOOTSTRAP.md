# Bootstrap protocol

## Goal
Turn this scaffold into the working student repository without losing evaluator constraints or GitHub traceability.

## First local setup

1. Copy this scaffold into the new repository root.
2. Run `git init` only if the directory is not already a repository.
3. Run `uv sync` and `make check`.
4. Stage the supplied vLLM/data assets locally with `scripts/bootstrap-data.sh`; verify they remain ignored.
5. Do **not** copy model weights, generated search results, private datasets, or evaluator binaries into Git history.
6. Run `scripts/setup-hermes.sh` or the PowerShell equivalent.
7. Restart Hermes and start it from the repository root.

## GitHub bootstrap

Before implementation:

1. Identify the repository and default branch.
2. Inspect whether a GitHub Project already exists for this repository.
3. Reuse the existing Project. Do not create duplicates.
4. If none exists and Mario has authorized project creation, create one with a simple status flow: `Backlog`, `Ready`, `In progress`, `Review`, `Done`.
5. Create the initial issues from `docs/github/INITIAL_BACKLOG.md` as detailed issues, preserving dependencies.
6. Add each issue to the Project and set realistic status.
7. Do not start implementation before issue #1 (or the actual first Ready issue) is approved.

## First implementation principle
The harness already supplies governance and a harmless CLI shell. It does not choose BM25 vs TF-IDF, AST exact chunk semantics, model-loading stack, or optimization strategy as irreversible decisions. Those are issue-level decisions backed by public-dataset evidence.
