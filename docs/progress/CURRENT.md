# Current project state

## Milestone
M0 — Harness/bootstrap only.

## Verified
- Subject/exam/moulinette constraints have been distilled into `docs/project/`.
- Minimal Python Fire scaffold exists.
- No retrieval implementation is claimed.

## Active issue
None yet. GitHub repository/Project must be inspected before selecting the first issue.

## Next smallest step
Create/confirm the GitHub Project and open the first implementation issue: exact Pydantic models + JSON contract tests, unless the existing Project already defines a different Ready issue.

## Main risks
- Overfitting retrieval to provided private ground truth.
- Losing exact source offsets after text normalization/chunking.
- Correct content with wrong path prefix receiving zero recall credit.
- Premature embeddings/hybrid complexity delaying mandatory lexical baseline.
