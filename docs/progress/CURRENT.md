# Current project state

## Milestone
M3 — Local evaluation and robustness.

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
  input, ranks persisted chunks with SQLite FTS5 BM25, and prints exact ranked
  source locations without rebuilding the corpus.
- The required `search_dataset` command validates `RagDataset`, reuses one warm
  SQLite connection, preserves question identity/order, and writes the exact
  `StudentSearchResults` model to a predictable configurable output path.
- The public `k=10` baseline processes 199 docs/code questions in 12.187 seconds
  and passes moulinette validation: Docs Recall@5 0.870 and Code Recall@5 0.606.
- Issues #10 and #11 are closed; the public retrieval baseline and local
  evaluator are complete.
- The project-owned `evaluate` command computes per-question source Recall@k
  and macro-averages it across questions with non-empty ground truth.
- Local evaluation reproduces the recorded moulinette values at every cutoff:
  Docs 0.600/0.780/0.870/0.890 and Code 0.354/0.545/0.606/0.667 for
  Recall@1/3/5/10.

## Active issue
[#12 Harden retrieval and evaluator edge cases](https://github.com/mario-asenjo/RAG-Against-The-Machine/issues/12)
has completed local verification and awaits PR review/manual merge.
Issue #35 and PR #36 are merged.

- Existing boundary handling already satisfies the required error cases; no
  production refactor or exception hierarchy was needed.
- Added CLI coverage for no-match/zero-limit success and batch missing/corrupt
  index or empty-query failure, including preservation of previous output.
- Fresh `make check`: context, Flake8, mypy (29 files), and 81 tests pass.
- Exact fixture CLI smokes confirm exit 0 with a newline for no matches/zero
  limit, and exit 2 without tracebacks for missing/malformed inputs.

## Next candidate
After #12 is reviewed and merged, start
[#24 Validate minimal Qwen/Qwen3-0.6B inference runtime](https://github.com/mario-asenjo/RAG-Against-The-Machine/issues/24)
in M4. Keep #13/#14 generation integration and #25 complete clean-checkout
rehearsal separate. Answer commands remain placeholders.

## Main risks
- Overfitting retrieval to provided private ground truth.
- Losing exact source offsets after text normalization/chunking.
- Correct content with wrong path prefix receiving zero recall credit.
- Premature embeddings/hybrid complexity delaying mandatory lexical baseline.
