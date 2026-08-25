# Initial GitHub backlog

These are issue **seeds**, not a license to create duplicates. Hermes must first inspect existing issues/Project and create only missing work. Each issue should use the repository implementation/benchmark template and be expanded with current file paths and evidence.

## M0 — Foundation

### 1. Implement exact Pydantic exchange models and JSON contract tests
**Goal:** implement the subject's minimal data models exactly, including UUID default behavior, and test serialization/validation.

**DoD:** all required models exist; malformed source ranges/required fields fail predictably where appropriate; JSON shape matches subject examples; mypy/flake8/tests green.

**Non-goals:** chunking, retrieval, model loading.

### 2. Implement safe corpus discovery and exact source text loading
**Goal:** traverse `data/raw/vllm-0.10.1` deterministically, preserve canonical project-relative paths and raw text used for offset calculation.

**DoD:** excludes clearly irrelevant/binary/generated files by documented policy; exact path contract tests; unreadable files handled deliberately; no hard-coded evaluator question mapping.

## M1 — Chunking

### 3. Implement bounded Markdown/text chunking with exact character spans
**Goal:** distinct text chunker under configurable max size.

**DoD:** every chunk <= max; original substring equality test; headings/paragraph logic documented; empty/huge input covered.

### 4. Implement bounded Python code chunking with exact character spans
**Goal:** distinct Python strategy, preferably structure-aware with safe fallback.

**DoD:** every chunk <= max; original substring equality; functions/classes/oversized constructs covered; invalid Python does not crash whole indexing run.

## M2 — Lexical retrieval baseline

### 5. Persist first lexical index and implement `index`
**Goal:** choose BM25 or TF-IDF based on the smallest credible baseline design and persist under `data/processed/`.

**DoD:** `index --max_chunk_size 2000`; persisted metadata includes source locations; fresh indexing <=300s on full corpus; progress shown with tqdm; no query-time corpus rebuild.

### 6. Implement ranked `search` and source projection
**Goal:** top-k ranked exact source locations.

**DoD:** correct JSON/CLI behavior; empty/gibberish/k=0 graceful; spans <=2000; exact path/offset tests; persisted index reload works.

### 7. Implement `search_dataset` and output persistence
**Goal:** batch unanswered datasets to StudentSearchResults JSON in caller-provided directory.

**DoD:** preserves question IDs/text/order; configurable paths; 200-question warm workflow runnable; malformed JSON/path errors graceful.

### 8. Establish public retrieval baseline and close threshold gaps
**Goal:** run public docs/code evaluation and record reproducible baseline.

**DoD:** benchmark ledger contains Recall@1/3/5/10 + timing + config. If thresholds are missed, create separate controlled benchmark issues instead of stuffing multiple experiments into one PR.

## M3 — Local evaluation and robustness

### 9. Implement student-owned Recall@k `evaluate`
**Goal:** provide the subject's local evaluation command without importing/calling moulinette.

**DoD:** same-file overlap metric documented; public dataset sanity checks; malformed files graceful.

### 10. Harden evaluator edge cases and clean-clone workflow
**Goal:** mirror provided edge-case script and verify install/run from clean clone.

**DoD:** no tracebacks for empty query, gibberish, k=0 answer, bad dataset path; `uv sync`, Makefile gates, README setup work cleanly.

## M4 — Answer generation

### 11. Integrate Qwen/Qwen3-0.6B and grounded single-query `answer`
**Goal:** minimal local inference stack using retrieved context within token budget.

**DoD:** works with mandatory model; prompt rejects unsupported claims; k=0 graceful; selected public questions produce coherent grounded answers; no hidden re-search bypassing retrieved sources.

### 12. Implement `answer_dataset`
**Goal:** consume StudentSearchResults and write StudentSearchResultsAndAnswer to caller-provided directory.

**DoD:** preserves source metadata/question identity; progress bar; malformed inputs graceful.

## M5 — Defense readiness

### 13. Final README, architecture/performance documentation, AI usage, and defense rehearsal
**Goal:** satisfy every README requirement in English and explain the actual implementation.

**DoD:** exact required first line, architecture, chunking, retrieval, performance, design decisions, challenges, examples, resources + AI usage; clean-clone and public evaluator rehearsal evidence.

### 14. Blind private evaluator rehearsal (explicit authorization required)
**Goal:** one final confidence run against private questions without tuning on their answered labels.

**DoD:** run supplied evaluator workflow once; record only aggregate results/timing and bugs; do not mine private ground truth for ranking changes unless Mario explicitly changes the holdout policy.

## Bonuses — only after mandatory full pass
Create separate issues only after all mandatory gates are green: semantic embeddings, hybrid retrieval, incremental indexing, caching, local HTTP API.
