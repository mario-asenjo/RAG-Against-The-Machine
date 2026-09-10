# Current project state

## Milestone
M4 — Answer generation.

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
[#13 Integrate Qwen/Qwen3-0.6B and grounded answer command](https://github.com/mario-asenjo/RAG-Against-The-Machine/issues/13)
is implemented and locally verified; PR review/manual merge remains required.
Issues #12/#24 and PRs #37/#38 are merged.

- `answer` performs one existing BM25 search and hydrates only exact SQLite
  `(file_path, first_character_index, last_character_index)` source tuples.
- A minimal `TextGenerator` Protocol keeps the shared application path fakeable;
  the lazy Qwen adapter owns the no-thinking template, token count and generation.
- Complete ranked chunks fit under configurable 2,048/128 token defaults; all
  retrieved sources stay in Pydantic output while included prompt sources remain
  tracked internally.
- `k=0`/no-match produce an explicit abstention without model assets. Missing or
  corrupt indexes, stale exact sources, invalid budgets and model failures remain
  clear technical errors rather than abstentions.
- Fresh public vLLM v0.10.1/Qwen smoke answered the Volta question from the exact
  647-character source: 265 prompt + 128 reserved = 393 tokens; wall time 26.5680s.
- Fresh gates: 29 focused tests; `make check` passes with 110 tests; strict mypy,
  Flake8, context validation, `uv sync --locked`, and `git diff --check` pass.
- The `answer` CLI enables stderr-only tqdm phases for tokenizer/config loading,
  model loading, and generation; the reusable Qwen adapter remains quiet by default.
- See `docs/project/10_GROUNDED_ANSWER.md` for contracts and full fresh evidence.

## Next candidate
After #13 is reviewed and manually merged, implement #14 (`answer_dataset`) as a
separate iteration/PR. It remains Todo and unstarted. Keep #25 clean-checkout
rehearsal and #16 private holdout separate.

## Main risks
- Overfitting retrieval to provided private ground truth.
- Losing exact source offsets after text normalization/chunking.
- Correct content with wrong path prefix receiving zero recall credit.
- Premature embeddings/hybrid complexity delaying mandatory lexical baseline.
