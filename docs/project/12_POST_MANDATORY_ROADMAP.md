# Post-mandatory roadmap

This document records the findings from `docs/prompts/RAG_MASTER_ROADMAP_MANDATORY_AND_ALL_BONUSES.md` without implementing any bonus behavior in PR #40.

## Current PR #40 findings

PR #40 remains mandatory-only. The review plan identifies three follow-ups before merge/readiness:

- fix nested tqdm UX so the dataset bar is stable and generation progress is a reusable second line;
- record the known long-run `answer_dataset` baseline and a profiling plan;
- document the post-#40 mandatory and bonus order.

Do not add cache, incremental indexing, semantic retrieval, hybrid retrieval, HTTP, concurrency, or answer-shortening in #40.

## Non-negotiable decisions

- Do not reduce `max_new_tokens` merely to improve runtime.
- Do not shorten answers just to make `answer_dataset` faster.
- Do not introduce `StaticCache` unless a future dedicated benchmark proves it useful.
- Keep mandatory lexical retrieval permanently available.
- Preserve exact `file_path`, `first_character_index`, and `last_character_index` contracts.
- Keep private datasets as blind holdout until Mario explicitly authorizes issue #16.

## Mandatory readiness order

After PR #40 review/manual merge, finish mandatory readiness before bonuses:

1. Profile `answer_dataset` on a fixed public 10-15 question subset.
2. Benchmark CPU thread counts: 4, 8, 10, PyTorch default, and 16.
3. Run the clean-checkout mandatory CLI rehearsal in #25.
4. Finish evaluator-facing README and defense readiness in #15.
5. Freeze a known-good mandatory baseline SHA/configuration.

Only optimize source lookup or tokenization if profiling shows material cost. The 99-question public code baseline cited by the roadmap is 40:48 total, about 24.73 seconds/question, with generation dominating observed per-question time.

## Bonus unlock order

Bonuses stay blocked until mandatory readiness is green. The accepted order is:

```text
#19 incremental indexing
  -> #17 semantic retrieval
  -> #18 hybrid retrieval
  -> #20 persistent query cache
  -> #21 local HTTP API
  -> final public regression/docs
  -> #16 one blind private rehearsal, only with explicit authorization
```

## Why incremental indexing comes first

Incremental indexing establishes the index lifecycle primitives that later bonuses need:

- file manifest;
- content hash/fingerprint;
- changed/added/deleted detection;
- transactional partial chunk and FTS replacement;
- stale chunk cleanup;
- persistent `index_revision`.

Semantic retrieval can reuse the same change detector for embedding updates. Persistent query caching also needs `index_revision`; with incremental updates the SQLite file is no longer naturally replaced on every content change, so cache validity must be explicit.

## Bonus-specific constraints

### #19 Incremental indexing

Implement only corpus/index lifecycle work. Track per-file path, content hash, size, optional mtime precheck, and index revision/generation. Treat rename as delete plus add. Keep full rebuild as a safe fallback.

Required evidence: unchanged, changed, added, deleted, mixed-change, rollback/failure, metadata-mismatch fallback, full-rebuild equivalence, and no-op/small-change timing.

### #17 Semantic retrieval

Pick the smallest local/offline-compatible embedding stack that survives `uv sync`. Persist embeddings tied to chunk identity, index revision, embedding model ID, and model revision. Reuse #19 change detection. Lexical remains available and default-safe.

Required evidence: lexical vs semantic Recall@1/3/5/10, latency, build/update time, and storage size.

### #18 Hybrid retrieval

Depend on #17. Start with transparent score-agnostic fusion such as Reciprocal Rank Fusion because BM25 and cosine scores are not directly comparable. Deduplicate by exact source identity.

Required evidence: lexical-only vs semantic-only vs hybrid Recall@1/3/5/10, docs/code split, latency, and duplicate rate. No reranker without a separate measured issue.

### #20 Persistent query cache

Implement only after retrieval modes stabilize. Use a persistent SQLite table, not generated-answer caching.

Logical key:

```text
(cache_schema_version, index_revision, retriever_signature, query_key, k)
```

`retriever_signature` must distinguish lexical, semantic model/revision/algorithm, and hybrid fusion parameters. Errors are not cached. Cached and uncached outputs and Recall must remain identical.

### #21 Local HTTP API

Add this last as a local adapter over stable use cases and Pydantic models. Keep the CLI as the evaluator contract. No auth, deployment, Docker, UI, async worker, or duplicated business logic unless a later issue justifies it.

## Global regression after bonuses

After all shipped bonuses, rerun mandatory commands, `make check`, strict mypy, clean-checkout smoke, public recall benchmarks, performance gates, and bonus-specific benchmarks. Update README with only actually shipped bonus behavior.
