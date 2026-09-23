# Optional hybrid retrieval

## Scope

Issue #18 adds one explicit retrieval mode that combines the existing lexical and
semantic rankings. It does not change indexing, chunking, persisted artifacts, model
selection, source hydration, answer generation, or the mandatory BM25 default.

## Inputs and boundaries

Hybrid search consumes only the two existing ranked lists:

```text
query
  +--> SQLite FTS5 BM25 top-k -----+
  |                                +--> equal RRF --> exact top-k MinimalSource
  +--> MiniLM cosine top-k --------+
```

The lexical retriever retains its SQLite validation/query behavior. The semantic
retriever retains model/configuration, canonical identity, and `source_index_revision`
validation. Hybrid adds no index and persists no state.

## Fusion rule

The pure `fuse_ranked_sources()` use case applies equal-weight reciprocal rank fusion:

```text
score(source) = sum(1 / (60 + rank_in_retriever))
```

Ranks are one-based. The rank constant is the fixed conventional value 60; it is not a
CLI knob. BM25 and cosine scores are intentionally not normalized or compared directly.

The evaluator-visible identity is exact:

```text
(file_path, first_character_index, last_character_index)
```

A chunk returned by both retrievers appears once and receives both rank contributions.
Repeated identity inside one ranking contributes only at its first rank. Distinct
adjacent or overlapping spans remain separate; no fuzzy deduplication can discard valid
sources. Final ties resolve lexicographically by exact identity, matching canonical path
and offset order.

## CLI contract

`search` and `search_dataset` add `hybrid: bool = False`.

- no mode flag: unchanged lexical BM25;
- `--semantic=True`: unchanged semantic cosine retrieval;
- `--hybrid=True`: run both existing retrievers and fuse their top-`k` lists;
- `--semantic=True --hybrid=True`: clear mutually-exclusive mode error.

The semantic model/cache/max-length/local-only options are reused for hybrid mode. The
single command prints the same exact source-location lines. Dataset mode constructs the
same `StudentSearchResults` Pydantic wrapper and preserves question ID, text, order and
`k`. A semantic validation/model failure occurs before output writing, preserving an
existing result file.

`answer` and `answer_dataset` remain lexical/previous-result flows; issue #18 does not
change generation.

## Determinism and edge behavior

- `k < 0` fails at the reusable fusion/retrieval boundary.
- `k = 0` returns no fused sources.
- Empty queries retain existing retriever validation.
- Exact duplicates are fused once.
- Near duplicates remain distinct and deterministic.
- Missing, corrupt, stale, or incompatible semantic state retains existing clear errors.
- Every returned source still comes from canonical chunks and remains at most 2,000
  characters.

## Tests

Focused regressions cover:

- exact duplicate score combination;
- candidates present in only one retriever;
- canonical equal-score ordering;
- overlapping source spans remaining distinct;
- duplicate suppression inside one ranking;
- zero and negative limits;
- single-query hybrid CLI orchestration/output;
- dataset identity/order/`k` and Pydantic output;
- stale semantic failure preserving prior dataset output;
- mutually exclusive mode flags without traceback;
- all existing lexical and semantic tests unchanged.

## Public benchmark

Fixed public input: canonical relative `data/raw/vllm-0.10.1`, 1,969 files, 17,134
chunks, `max_chunk_size=2000`, 100 documentation questions, 99 code questions, and
`k=10`. The same persisted SQLite and MiniLM artifacts were used for all modes. No
private data or campus run was used.

| Method | Dataset | Recall@1 | Recall@3 | Recall@5 | Recall@10 | Search s |
|---|---|---:|---:|---:|---:|---:|
| SQLite FTS5 BM25 | Docs | 0.600 | 0.780 | 0.870 | 0.890 | 2.374 |
| SQLite FTS5 BM25 | Code | 0.354 | 0.545 | 0.606 | 0.667 | 2.613 |
| MiniLM cosine | Docs | 0.270 | 0.410 | 0.440 | 0.530 | 11.437 |
| MiniLM cosine | Code | 0.263 | 0.333 | 0.404 | 0.465 | 11.357 |
| Equal RRF hybrid | Docs | 0.450 | 0.700 | 0.790 | 0.870 | 14.418 |
| Equal RRF hybrid | Code | 0.323 | 0.495 | 0.596 | 0.707 | 14.403 |

Combined timings for 199 public questions were 4.987s lexical, 22.794s semantic, and
28.821s hybrid. Every output validated as `StudentSearchResults` with `k=10`, 199
questions, at most ten sources per question, and maximum span 2,000.

Exact cross-mode duplicate rate is the sum of lexical/semantic identity intersections
per question divided by the total lexical candidate count. Both modes returned ten
candidates per question, so either candidate-list denominator has the same size:

| Dataset | Shared exact identities | Candidate denominator | Duplicate rate |
|---|---:|---:|---:|
| Docs | 244 | 1,000 | 24.40% |
| Code | 137 | 990 | 13.84% |

Lexical result hashes remained exactly frozen:

```text
Docs 52996f9cf6b692210e0f70478b184921a415d90127e82182d19c6bdee92ce199
Code 97ab7c56779e8379e7220a50b8fb109bb7df8b021a3f08bf67f7383a63175301
```

Equal RRF improved Code Recall@10 from 0.667 to 0.707, but reduced BM25 at the other
recorded code cutoffs and all documentation cutoffs. The result justifies retaining the
transparent optional experiment, not changing the default or adding learned/manual
weights. Public probes of alternative rank constants and deeper candidate pools did not
produce a broad improvement and were not promoted to configuration.

## Non-goals retained

No reranker, learned fusion, exposed weights/rank constant, new embedding model, query
cache, vector database, HTTP API, fuzzy overlap suppression, private-label tuning, or
answer-pipeline integration.

Final local verification passed 11 focused hybrid tests, `make check` with 170 tests,
context validation, Flake8 and subject-flag mypy; `make lint-strict` and
`git diff --check` also passed.
