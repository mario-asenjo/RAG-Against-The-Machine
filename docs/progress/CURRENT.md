# Current project state

## Milestone
M1 — Chunking / Markdown-text source spans.

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
- Markdown/text chunking preserves half-open `[first_character_index:last_character_index]`
  spans against exact original text and enforces configurable max chunk size.
- No retrieval implementation is claimed.

## Active issue
[#5](https://github.com/mario-asenjo/RAG-Against-The-Machine/issues/5)
implements bounded Markdown/text chunking with exact character spans.

## Next smallest step
After #5 merges, start [#6 Implement bounded Python code chunking with exact
character spans](https://github.com/mario-asenjo/RAG-Against-The-Machine/issues/6).

## Main risks
- Overfitting retrieval to provided private ground truth.
- Losing exact source offsets after text normalization/chunking.
- Correct content with wrong path prefix receiving zero recall credit.
- Premature embeddings/hybrid complexity delaying mandatory lexical baseline.
