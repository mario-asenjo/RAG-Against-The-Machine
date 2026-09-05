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
[#24 Validate minimal Qwen/Qwen3-0.6B inference runtime](https://github.com/mario-asenjo/RAG-Against-The-Machine/issues/24)
is locally demonstrated; PR review/manual merge remains required.
Issue #12 and PR #37 are merged; retrieval/evaluator robustness is complete.

- CPU runtime: Transformers 4.57.6, torch 2.10.0+cpu, CPython 3.10.20.
- Real no-thinking generation returned `Paris.` with cache-only loading verified.
- The full template uses 48 tokens; 128 reserved output tokens fit a configurable
  2,048-token budget. Exact-boundary and invalid-budget smokes pass.
- Supported context is capped by model config at 40,960, not the tokenizer's
  131,072; sentinel tokenizer limits are ignored.
- Fresh `make check` passes with 81 tests; no production/retrieval code changed.
- See `docs/project/09_GENERATION_RUNTIME.md` for timings, observed memory,
  dependency/cache limitations and the exact reproducible probe.

## Next candidate
After #24 is reviewed and merged, implement #13 (`answer` and the shared
source-to-answer path), then #14 (`answer_dataset`) in separate iterations/PRs.
The approved boundaries are recorded in the runtime document. Neither has started;
answer commands remain placeholders. Keep #25 final clean-checkout rehearsal separate.

## Main risks
- Overfitting retrieval to provided private ground truth.
- Losing exact source offsets after text normalization/chunking.
- Correct content with wrong path prefix receiving zero recall credit.
- Premature embeddings/hybrid complexity delaying mandatory lexical baseline.
