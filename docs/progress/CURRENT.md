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
- Deterministic corpus discovery loads `.py`, `.md`, and `.txt` files in sorted
  order while preserving canonical paths and exact UTF-8 text.
- No retrieval implementation is claimed.

## Active issue
[#4](https://github.com/mario-asenjo/RAG-Against-The-Machine/issues/4)
implements safe corpus discovery and exact source text loading.

## Next smallest step
After #4 merges, start [#5 Implement bounded Markdown/text chunking with exact
character spans](https://github.com/mario-asenjo/RAG-Against-The-Machine/issues/5).

## Main risks
- Overfitting retrieval to provided private ground truth.
- Losing exact source offsets after text normalization/chunking.
- Correct content with wrong path prefix receiving zero recall credit.
- Premature embeddings/hybrid complexity delaying mandatory lexical baseline.
