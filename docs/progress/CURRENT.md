# Current project state

## Milestone
M0 — Foundation / data contracts and architecture seams.

## Verified
- Subject/exam/moulinette constraints have been distilled into `docs/project/`.
- Minimal Python Fire scaffold exists.
- Hermes project skill setup is installed through the active Hermes config home.
- `make check` passes after `uv sync` on the bootstrap scaffold.
- Bootstrap PR #3 was merged.
- No retrieval implementation is claimed.

## Active issue
[#2 Implement exact Pydantic exchange models and JSON contract tests](https://github.com/mario-asenjo/RAG-Against-The-Machine/issues/2).

## Next smallest step
Finish #2 with minimal domain/application/infrastructure/adapters seams, Pydantic contracts, boundary tests, local gates, Ponytail review, and PR.

## Main risks
- Overfitting retrieval to provided private ground truth.
- Losing exact source offsets after text normalization/chunking.
- Correct content with wrong path prefix receiving zero recall credit.
- Premature embeddings/hybrid complexity delaying mandatory lexical baseline.
