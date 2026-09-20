# Optional semantic embeddings

## Scope

Issue #17 adds a local semantic projection and retrieval mode without changing the
mandatory lexical default. Hybrid fusion, a query cache, an HTTP API, external vector
stores, and private-data tuning remain out of scope.

## Canonical data model

SQLite remains authoritative:

```text
files + chunks                 canonical manifest/chunk store
        |\
        | +--> chunks_fts      lexical projection (FTS5/BM25)
        |
        +----> semantic_index.pt  semantic projection (MiniLM/cosine)
```

The corpus is loaded once per `index` command. Full builds use the existing chunkers.
Incremental builds call `plan_lexical_index_update()` once and reuse its
`changed_paths`, `removed_paths`, and `changed_chunks`; semantic code performs no file
hashing, change detection, or chunking.

## Model and pooling

The default model is
`sentence-transformers/all-MiniLM-L6-v2` at revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. The implementation uses the existing
`torch==2.10.0` and `transformers==4.57.6` dependencies directly on CPU:

1. tokenize padded/truncated batches with maximum length 256;
2. run `AutoModel` in inference mode;
3. mean-pool token hidden states using `attention_mask`;
4. L2-normalize every float32 vector.

Model name/revision, cache directory, maximum length, and `local_files_only` are
configurable. The project does not add `sentence-transformers`.

## Artifact contract

The default generated path is `data/processed/semantic_index.pt`. A sibling temporary
file is written with `torch.save` and atomically replaces the live artifact only after
serialization succeeds. The payload contains:

- Pydantic-validated metadata: schema version, model name/revision, pooling,
  max length, embedding dimension, chunk count, and `source_index_revision`;
- one normalized float32 embedding matrix;
- exact `(file_path, first_character_index, last_character_index)` identities in
  canonical SQLite `rank_order`.

Chunk text is not duplicated. Loading validates payload types, dimensions, finite
values, L2 norms, counts, requested model configuration, source revision, and exact
identity/order against SQLite.

## Full and incremental flows

### Default full lexical build

`index` retains the existing lexical build and output. A prior semantic projection is
removed after a successful lexical-only full rebuild, preventing an obsolete artifact
from becoming accidentally valid if corrupt lexical metadata resets a revision number.

### Full semantic build

`index --semantic=True` first completes the normal atomic SQLite build, reloads chunks
from the canonical store, embeds those chunks, and atomically writes the semantic
projection. If semantic work fails, valid SQLite remains and the prior semantic file is
unchanged. Its old revision makes staleness visible.

### Incremental semantic update

`index --incremental=True --semantic=True` uses one lexical delta. After SQLite updates:

- embeddings from unchanged files are reused exactly;
- all old rows from changed/deleted files are discarded;
- every new chunk from added/changed files is embedded;
- rows are assembled in final canonical SQLite order;
- semantic metadata advances to the same `index_revision`.

Changed file is the complete semantic invalidation unit; matching offsets do not permit
partial reuse.

### No-op and recovery

An unchanged corpus preserves the lexical byte-stable no-op. If semantic mode is also
requested:

- a valid same-revision/model/identity artifact is unchanged without loading the model;
- a missing, stale, corrupt, or incompatible artifact is rebuilt from canonical SQLite
  chunks without rebuilding lexical state.

## Retrieval

`search` and `search_dataset` remain lexical unless `--semantic=True` is explicit.
Semantic search validates the projection against current SQLite before embedding the
query. Normalized cosine similarity is computed by tensor dot product and selected with
`torch.topk`; exact score ties resolve by canonical chunk position. Returned values are
the same `MinimalSource` path and half-open offsets used by BM25, with the existing
2,000-character chunk bound.

## Tests

Focused coverage includes:

- full semantic build and CLI flag;
- canonical count, identity, order, dimensions, float32 dtype, and normalization;
- attention-mask mean pooling and L2 normalization;
- semantic no-op;
- added/changed/deleted/renamed file update behavior;
- whole-file invalidation and unchanged-file tensor reuse;
- missing/stale/incompatible rebuild without lexical replacement;
- atomic persistence failure and semantic failure after successful SQLite update;
- stale revision rejection before query embedding;
- exact path/offset projection and deterministic tied top-k;
- semantic single and dataset CLI output contracts;
- lexical indexing/search/incremental regression suites.

## Public benchmark

Fixed input: canonical relative `data/raw/vllm-0.10.1`, 1,969 accepted files,
17,134 chunks, `max_chunk_size=2000`, 100 public documentation questions, 99 public
code questions, and `k=10`. No private inputs or labels were used.

| Method | Dataset | Recall@1 | Recall@3 | Recall@5 | Recall@10 | Search s |
|---|---|---:|---:|---:|---:|---:|
| SQLite FTS5 BM25 | Docs | 0.600 | 0.780 | 0.870 | 0.890 | 1.819 |
| SQLite FTS5 BM25 | Code | 0.354 | 0.545 | 0.606 | 0.667 | 2.069 |
| MiniLM cosine | Docs | 0.270 | 0.410 | 0.440 | 0.530 | 7.077 |
| MiniLM cosine | Code | 0.263 | 0.333 | 0.404 | 0.465 | 7.005 |

| Semantic lifecycle measurement | Seconds |
|---|---:|
| Full lexical + semantic build | 379.690 |
| One changed file incremental update | 19.797 |
| Unchanged validated no-op | 5.603 |

The artifact is 27,862,262 bytes for a `(17134, 384)` tensor plus metadata and source
identities. Lexical output SHA-256 values remained exactly:

```text
Docs 52996f9cf6b692210e0f70478b184921a415d90127e82182d19c6bdee92ce199
Code 97ab7c56779e8379e7220a50b8fb109bb7df8b021a3f08bf67f7383a63175301
```

Standalone MiniLM underperforms BM25 on this public corpus. It therefore remains an
explicit bonus mode and supplies the semantic component needed by future issue #18;
this issue does not implement or tune hybrid fusion. The 379.690-second optional full
build is host-specific and above the mandatory 300-second indexing gate, but the
mandatory default remains lexical-only and unchanged.

Final local verification passed `make check` with 159 tests, context validation,
Flake8 and subject-flag mypy; `make lint-strict` and `git diff --check` also passed.
