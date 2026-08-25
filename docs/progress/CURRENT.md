# Current project state

## Milestone
M0 — Harness/bootstrap only.

## Verified
- Subject/exam/moulinette constraints have been distilled into `docs/project/`.
- Minimal Python Fire scaffold exists.
- Hermes project skill setup is installed through the active Hermes config home.
- `make check` passes after `uv sync` on the bootstrap scaffold.
- No retrieval implementation is claimed.

## Active issue
[#1 Bootstrap harness and Hermes setup](https://github.com/mario-asenjo/RAG-Against-The-Machine/issues/1) is in review via PR.

## Next smallest step
Start [#2 Implement exact Pydantic exchange models and JSON contract tests](https://github.com/mario-asenjo/RAG-Against-The-Machine/issues/2).

## Main risks
- Overfitting retrieval to provided private ground truth.
- Losing exact source offsets after text normalization/chunking.
- Correct content with wrong path prefix receiving zero recall credit.
- Premature embeddings/hybrid complexity delaying mandatory lexical baseline.
