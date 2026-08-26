# Current project state

## Milestone
M0 — Foundation / exact corpus loading.

## Verified
- Subject/exam/moulinette constraints have been distilled into `docs/project/`.
- Minimal Python Fire scaffold exists.
- Hermes project skill setup is installed through the active Hermes config home.
- `make check` passes after `uv sync` on the bootstrap scaffold.
- Bootstrap PR #3 was merged.
- Model/architecture PR #22 was merged and issue #2 is closed.
- Exact Pydantic exchange contracts and the minimal modular-monolith package
  seams are covered by tests.
- No retrieval implementation is claimed.

## Active issue
No implementation issue is active. Documentation hygiene
[#23](https://github.com/mario-asenjo/RAG-Against-The-Machine/issues/23)
records the local supplied-artifact policy after #2.

## Next smallest step
Start [#4 Implement safe corpus discovery and exact source text
loading](https://github.com/mario-asenjo/RAG-Against-The-Machine/issues/4).

## Main risks
- Overfitting retrieval to provided private ground truth.
- Losing exact source offsets after text normalization/chunking.
- Correct content with wrong path prefix receiving zero recall credit.
- Premature embeddings/hybrid complexity delaying mandatory lexical baseline.
