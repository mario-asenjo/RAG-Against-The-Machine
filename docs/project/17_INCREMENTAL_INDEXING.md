# Incremental lexical indexing — issue #19

## Contract

Incremental indexing is an opt-in bonus:

```text
uv run python -m src index --incremental=True
```

The mandatory default remains a complete atomic rebuild. Incremental mode requires a
compatible schema-v2 index with the same corpus path and `max_chunk_size`. A missing,
legacy, incompatible, or corrupt lifecycle schema triggers a visible full-rebuild
fallback rather than an in-place guess.

## Persisted lifecycle data

Schema v2 adds:

- `files`: canonical path, SHA-256 content hash, byte count, character count;
- `metadata.index_revision`: positive monotonic revision;
- `chunks.rank_order`: canonical BM25 tie order independent of SQLite row ID.

Full rebuilds populate the manifest and increase the revision when replacing a
compatible index. Hashes are calculated from the exact UTF-8 source text; mtime is not
a correctness input. Whitespace-only accepted files remain in the manifest with zero
chunks.

## Update flow

1. Discover and exactly load the current accepted corpus.
2. Hash every accepted file and compare it with the persisted manifest.
3. Classify added, content-changed, deleted, and unchanged paths. Rename is delete plus
   add.
4. If no path changed, return without replacing the database or changing its revision.
5. Chunk only added/changed documents and verify every produced chunk equals its exact
   original source slice.
6. Copy the live index to its sibling temporary path.
7. In one transaction on the copy:
   - delete stale FTS/chunk rows for changed/deleted paths;
   - insert chunks/FTS rows for added/changed paths;
   - replace the file manifest;
   - recompute canonical rank order;
   - increment metadata revision once;
   - validate file/chunk/FTS counts, widths, SQLite integrity and metadata.
8. Close all handles and atomically replace the live database.

Any loading, chunking, SQLite, validation, or replacement failure preserves the prior
live artifact. No filesystem watcher, daemon, concurrency, semantic retrieval, query
cache, or external dependency is added.

## Deterministic equivalence

SQLite row IDs cannot be the long-term tie-break once changed files may receive new
rows. `rank_order` is therefore recomputed from exact path and source offsets after an
update. BM25 orders by score then `rank_order`.

Fixture tests prove that mixed add/change/delete (including rename and changed chunk
counts) produces the same canonical chunks and query results as a clean full rebuild.
Public docs/code search JSON from a one-file incremental update was byte-identical to
a clean full rebuild over the same modified corpus.

## Failure and compatibility evidence

Focused acceptance coverage includes:

- schema-v2 manifest/revision/full rebuild;
- zero-chunk files;
- exact-byte no-op and stable revision;
- chunking only added/changed files;
- same-size content changes via SHA-256;
- inexact chunk rejection;
- mixed add/change/delete and rename;
- stale-term removal;
- contiguous deterministic rank order;
- invalid UTF-8 preserving prior bytes;
- SQLite-copy corruption preserving prior bytes;
- final replacement failure preserving prior bytes;
- incompatible schema full-rebuild fallback;
- inconsistent metadata, impossible bounds, changed persisted source text and missing
  FTS postings triggering safe full rebuild;
- monotonic full-rebuild/update revision.

## Public benchmark

Host/filesystem timings are local observations, not evaluator-wide constants. Raw
traces and generated corpora/indexes remain ignored under
`data/output/profiling/issue19/`.

### Public mandatory regression

Canonical relative corpus path, 1,969 files / 17,134 chunks, `k=10`:

| Metric | Result |
|---|---:|
| Full schema-v2 build | 8.430s |
| Unchanged no-op | 2.961s |
| Docs search | 3.676s |
| Code search | 3.961s |
| Combined search | 7.638s |
| Docs Recall@1/3/5/10 | 0.600 / 0.780 / 0.870 / 0.890 |
| Code Recall@1/3/5/10 | 0.354 / 0.545 / 0.606 / 0.667 |
| Max source span | 2,000 |

The docs/code output SHA-256 values remained the frozen mandatory values:

```text
docs: 52996f9cf6b692210e0f70478b184921a415d90127e82182d19c6bdee92ce199
code: 97ab7c56779e8379e7220a50b8fb109bb7df8b021a3f08bf67f7383a63175301
```

Schema-v2 artifact validation:

```text
bytes: 37,670,912
documents/files: 1,969
chunks/FTS rows: 17,134 / 17,134
zero-chunk accepted files: 122
revision: 1
PRAGMA integrity_check: ok
```

### Rotated one-file changes

A disposable full corpus copy was changed once per round. Incremental/full order was
rotated, each no-op followed its successful update, and every incremental artifact
matched its clean full rebuild.

| Round | Incremental | Full rebuild | No-op |
|---:|---:|---:|---:|
| 1 | 25.125s | 3.023s | 1.557s |
| 2 | 2.527s | 2.996s | 1.511s |
| 3 | 2.520s | 3.004s | 1.513s |
| Median | 2.527s | 3.004s | 1.513s |

Median one-file improvement: **15.90%** versus the comparable full rebuild. The first
incremental observation was a 25.125s host outlier; it is retained rather than hidden,
and the median remains below the three comparable full rebuilds.
Revisions advanced once per change (8, 9, 10) and stayed unchanged on each no-op.

### Discarded measurement

An initial public run passed an absolute corpus path. Retrieval completed, but local
Recall was 0 because emitted paths no longer matched the canonical
`data/raw/vllm-0.10.1/...` prefix. That run is retained only as a path-fidelity
negative control and is excluded from quality evidence. The canonical relative-path
rerun above is authoritative.

## Boundaries for later bonuses

- #17 may reuse file hashes and `index_revision` for embedding updates.
- #20 must include `index_revision` in every persistent query-cache key.
- Full lexical rebuild/search remains available and default-safe.
- No private labels or campus iteration were used for #19.
