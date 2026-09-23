# Current project state

## Milestone
Bonus — Optional enhancements. Mandatory readiness remains frozen at merged baseline
`7c411ef`.

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
[#19 Bonus: support incremental index updates](https://github.com/mario-asenjo/RAG-Against-The-Machine/issues/19)
is implemented on `feat/issue-19-incremental-indexing` and awaiting review. Full
rebuild remains the default; incremental indexing is explicit.

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
- `answer_dataset` validates prior `StudentSearchResults`, preserves exact `k`, IDs,
  questions, order, and retrieved sources, and never executes retrieval again.
- The sequential batch reuses one lazy Qwen instance and one lazily opened SQLite
  connection; empty-source questions abstain without SQLite or model work.
- Batch and Qwen progress stays on stderr. The Pydantic output uses the input
  filename and atomically replaces the destination only after complete success.
- Fresh #14 checks: 40 focused tests; `make check` passes with 121 tests in 31.68s;
  strict mypy over 34 files, Flake8, context validation, `uv sync --locked`, and
  `git diff --check` pass.
- Fresh public cache-only smoke: two sequential answers in 18.4644s after a
  5.9469s public-corpus index and 0.6742s retrieval preparation. Exact input/output
  identity and source lists revalidated; no private data was used.
- See `docs/project/11_ANSWER_DATASET.md` for contracts, output safety, and evidence.
- The post-review tqdm follow-up keeps #14 mandatory-only: the dataset bar now owns
  `position=0, leave=True`, Qwen phases reuse `position=1, leave=False`, and
  generation progress is streamer-backed generated-token progress on stderr.
- Public #41 profiling on 10 sourced code questions shows generation dominates
  wall time at 91-97%; source hydration and prompt fitting are not current
  bottlenecks. Explicit 10 CPU threads was fastest on this host at 316.973s
  total / 31.697s per question, about 14.5% faster than the current hard-coded
  4-thread production setting. See `docs/project/13_ANSWER_DATASET_PROFILING.md`.
- A disposable clean checkout at `7cd34f8` passed fresh `uv sync --locked`,
  `make check` with 122 tests, all four supplied edge cases, and public smokes for
  every mandatory command. Exact Pydantic answer outputs and batch identity were
  revalidated. See `docs/project/14_CLEAN_CHECKOUT_REHEARSAL.md`.
- Mario explicitly authorized one blind private retrieval rehearsal. Indexing
  passed in 55s; private Docs Recall@5 passed at 0.800 and Code Recall@5 passed at
  0.510. The warm timing gate is unclaimed because a WSL clock discontinuity made
  the script's docs duration invalid and mounted-v9fs code retrieval took 115s.
- #43 was fixed by merged PR #46: `bootstrap-data.sh` uses exact supplied
  archive roots and preserves public data under
  `data/datasets/datasets_public/public/` and private data under
  `data/datasets/private/`, without flattened or double-nested copies.
- `scripts/campus_test.sh` now provides the pending native-campus measurement in
  one command and captures complete stdout/stderr to one ignored log without
  opening private labels or rerunning Moulinette.
- Campus evidence at merged `e367ecb`: indexing passed in 10s and both private
  Recall@5 gates passed (Docs 0.800, Code 0.510), but warm retrieval took
  46s docs + 46s code = 92s and failed the mandatory <=90s gate. The 2s miss is
  small but has no safety margin. Issue #45 tracks measured uncached optimization.
- The campus runner passed `make check` but later uv steps hit a transient NFS
  working-directory permission error. Manual evaluator commands then ran; edge
  cases passed 4/4 and answer generation produced three grounded outputs.
- #45 local public phase profiling found FTS execution at 99.92% of measured
  runtime. The existing SQLite page cache was approximately 2 MiB for a 35.230 MiB
  index; startup, validation, connection, model construction and serialization
  were negligible.
- One batch-local `PRAGMA cache_size=-65536` requests a 64 MiB SQLite page cache.
  Three home-Windows CLI pairs improved from a 7.987s median to 5.445s, a 31.83%
  gain, with byte-identical outputs and unchanged public Recall@1/3/5/10.
- Read-only and immutable URIs and `temp_store=MEMORY` did not help. mmap was
  slightly faster locally but was rejected because its filesystem-dependent
  behavior adds unjustified campus-NFS risk. See
  `docs/project/15_RETRIEVAL_PERFORMANCE.md`.
- One post-merge campus confirmation at `6ff741a` processed 100 private unanswered
  docs questions in 4.079s and 100 code questions in 4.114s on `/sgoinfre` NFS4.
  The 8.193s combined result passes the <=90s gate with 81.807s headroom. Private
  labels and Moulinette were not reopened, so prior Recall evidence was not rerun.
- The same run passed `uv sync --locked`, `make check` with 124 tests, indexing in
  10.172s, public Qwen single/batch smokes, exact batch identity, and edge cases
  4/4. Every step exited 0 and the runner reported `CAMPUS_TEST_RESULT=PASS`.
- The host changed and the log reports an uncaptured local runner modification;
  therefore the run proves compliance but not that page cache caused the full
  91.09% cross-run reduction. The tracked runner now re-enters and validates the
  repository root before every step to mitigate the known NFS cwd failure.
- The final #15 README begins with the subject's exact italicized curriculum line
  and documents the actual architecture, chunkers, BM25 retrieval, Qwen grounding,
  setup, commands, performance, decisions, limitations, resources and AI usage.
- `docs/project/16_DEFENSE_GUIDE_ES.md` contains the complete Spanish defense,
  recode, demo, evidence and question/answer guide requested for later review.
- A disposable clean checkout at `010e568` passed fresh `uv sync --locked`,
  `make check` with 126 tests, strict mypy, all mandatory CLI flows, public Qwen
  single/batch smokes, exact Pydantic output checks and all four edge equivalents.
- Fresh public M5-F1 evidence: 1,969 files / 17,134 chunks indexed in 3.551s;
  100 docs + 99 code questions searched in 4.926s combined; Recall@1/3/5/10
  remained Docs 0.600/0.780/0.870/0.890 and Code
  0.354/0.545/0.606/0.667; maximum source span remained 2,000.
- #19 adds a schema-v2 SHA-256 file manifest, monotonic `index_revision`, canonical
  `rank_order`, true no-op detection, changed-file-only chunking, transactional copy
  updates, integrity validation, atomic replacement and visible full-rebuild fallback.
- Fifteen focused incremental regressions cover manifest/revision, zero-chunk files,
  exact-byte no-op, changed-file-only work, exact source slices, mixed add/change /
  delete/rename equivalence, invalid UTF-8, SQLite/replacement failures and schema
  fallback, including logical metadata, impossible source bounds, complete file
  identity and coherent chunk-text/FTS corruption. Full `make check`, strict mypy and
  Flake8 pass with 141 tests.
- Fresh public #19 regression: 1,969 files / 17,134 chunks; full build 8.430s,
  no-op 2.961s, docs/code search 7.638s combined, unchanged output hashes and Recall.
  Three final one-file rounds measured 2.527s incremental versus 3.004s comparable
  full rebuild median (15.90% faster), with 1.513s no-op median and exact full-build
  equivalence. See `docs/project/17_INCREMENTAL_INDEXING.md`.
- #17 adds explicit `--semantic=True` indexing/search over the same canonical SQLite
  chunks while preserving BM25 as the default. The pinned MiniLM adapter uses raw
  torch/Transformers CPU mean pooling and L2 normalization; no dependency was added.
- One atomic `semantic_index.pt` stores 17,134 normalized 384-d float32 rows plus exact
  path/offset identities and validated model/count/source-revision metadata without
  duplicating text. Stale revisions or non-canonical identities block search.
- Incremental semantic updates consume #19's one delta, reuse unchanged-file vectors,
  invalidate whole changed/deleted files, and embed only new changed/added chunks.
  Missing/stale/incompatible semantic state rebuilds only that projection on lexical
  no-op; failed semantic persistence preserves the prior detectably stale artifact.
- Fresh public comparison: BM25 remains Docs 0.600/0.780/0.870/0.890 and Code
  0.354/0.545/0.606/0.667 at Recall@1/3/5/10. MiniLM cosine measured Docs
  0.270/0.410/0.440/0.530 and Code 0.263/0.333/0.404/0.465, so no default change.
- Full lexical+semantic build took 379.690s; one-file update 19.797s; no-op 5.603s;
  artifact 27,862,262 bytes. Optional full build exceeds 300s on this host, while the
  unchanged mandatory lexical default retains its prior passing evidence.
- Fresh final gates: `make check` passes with 159 tests; strict mypy, Flake8, context
  validation, focused lexical/semantic suites, and `git diff --check` pass.

## Next candidate
After #17 is reviewed and merged, #18 may combine the measured lexical and semantic
signals. Keep hybrid explicit and evidence-driven; do not replace the stronger BM25
default without public results. Do not rerun private labels or campus tuning.

Planned bonus order after mandatory readiness is #19 -> #17 -> #18 -> #20 -> #21.

## Main risks
- Overfitting retrieval to provided private ground truth.
- Losing exact source offsets after text normalization/chunking.
- Correct content with wrong path prefix receiving zero recall credit.
- Premature embeddings/hybrid complexity delaying mandatory lexical baseline.
- Using #40 answer speed concerns to shorten answers or reduce `max_new_tokens`
  instead of profiling first.
