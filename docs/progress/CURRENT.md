# Current project state

## Milestone
M2 — Persisted lexical retrieval baseline.

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
- Python chunking uses top-level function/class boundaries, includes decorators,
  preserves exact original spans, and falls back safely for invalid syntax or
  oversized structures.
- A real-corpus check covers all 1,969 accepted vLLM files and 17,139 chunks
  with exact reconstruction and a maximum span of 2,000 characters.
- The required `index` command atomically persists exact chunk metadata and a
  reusable SQLite FTS5 BM25 index under configurable `data/processed/` output.
- The required single-query `search` command safely tokenizes natural-language
  input, ranks persisted chunks with SQLite FTS5 BM25, and emits the subject's
  `StudentSearchResults` contract without rebuilding the corpus.
- The required `search_dataset` command validates `RagDataset`, reuses one warm
  SQLite connection, preserves question identity/order, and writes the exact
  `StudentSearchResults` model to a predictable configurable output path.
- A public unanswered-dataset smoke processed 199 questions at `k=5` in 9.445
  seconds total; Recall@k remains intentionally unmeasured until #10.

## Active issue
[#9](https://github.com/mario-asenjo/RAG-Against-The-Machine/issues/9)
implements dataset retrieval and persisted subject-compatible output.

## Next smallest step
After #9 merges, start [#11 Implement Recall@k evaluation](https://github.com/mario-asenjo/RAG-Against-The-Machine/issues/11).

## Main risks
- Overfitting retrieval to provided private ground truth.
- Losing exact source offsets after text normalization/chunking.
- Correct content with wrong path prefix receiving zero recall credit.
- Premature embeddings/hybrid complexity delaying mandatory lexical baseline.
