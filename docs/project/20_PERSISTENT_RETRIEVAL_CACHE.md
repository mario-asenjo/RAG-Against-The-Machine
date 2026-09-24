# Persistent retrieval-result cache

## Scope

Issue #20 adds an explicit persistent cache for repeated retrieval queries after lexical,
semantic, and hybrid modes stabilized. It does not alter chunking, ranking, indexes,
default retrieval behavior, evaluator JSON, or generated answers.

The cache is opt-in with `cache: bool = False` on:

- `search`;
- `search_dataset`;
- the lexical retrieval step inside `answer`.

`answer` still invokes Qwen for every call. `answer_dataset` is unchanged because it
consumes validated prior `StudentSearchResults` and deliberately performs no retrieval.

## Storage and key

The cache is one lazily created `query_cache` table inside the existing lexical SQLite
artifact. No dependency, service, second database, migration framework, or cache class is
introduced.

```sql
CREATE TABLE query_cache (
    cache_schema_version INTEGER NOT NULL,
    index_revision INTEGER NOT NULL,
    retriever_signature TEXT NOT NULL,
    query_key TEXT NOT NULL,
    k INTEGER NOT NULL CHECK (k >= 0),
    results_json TEXT NOT NULL,
    PRIMARY KEY (
        cache_schema_version,
        index_revision,
        retriever_signature,
        query_key,
        k
    )
);
```

The logical key is therefore:

```text
(cache_schema_version, index_revision, retriever_signature, query_key, k)
```

`query_key` is SHA-256 over the exact UTF-8 query. There is intentionally no whitespace,
case, punctuation, or semantic normalization: queries that can produce different model
embeddings must not alias.

Only ordered `list[MinimalSource]` JSON is stored. Chunk text, scores, embeddings,
prompts, generated text, errors, and model output are not duplicated.

## Retriever signatures

Signatures are deterministic namespaces for behavior that can change ranking:

- lexical: SQLite FTS5 BM25 algorithm version;
- semantic: MiniLM cosine algorithm version, model name, pinned model revision, pooling /
  normalization behavior, and maximum token length;
- hybrid: fixed equal RRF version and rank constant plus both child signatures.

Changing mode, semantic model configuration, hybrid parameters, `k`, exact query,
cache schema, or canonical `index_revision` produces a miss.

## Lifecycle and correctness

The flow is deliberately small:

```text
exact queries
  -> load validated lexical metadata/index_revision
  -> create table if needed
  -> validate matching rows against Pydantic + canonical chunk identities
  -> retrieve each exact miss once through the existing mode
  -> validate fresh exact identities
  -> commit ordered MinimalSource JSON
  -> restore original query order, including duplicates
```

The `files + chunks` SQLite tables remain canonical. On every cache-enabled operation the
17,134 exact chunk identities are loaded once into a set, avoiding one SQLite lookup per
returned source while still rejecting corrupt/non-canonical rows.

Incremental indexing copies the SQLite artifact as before. A content change advances
`index_revision`, so historical rows remain unreachable without deletion or a second
invalidation mechanism. A true lexical no-op retains the revision and valid hits. A full
rebuild atomically replaces SQLite and naturally starts without the old table.

Malformed JSON, duplicates, lists larger than `k`, and identities absent from canonical
`chunks` are misses and are replaced only after successful retrieval. Retrieval failures
and SQLite write failures do not create successful rows. Cache reads/writes are ordinary
SQLite transactions; cache diagnostics never enter evaluator stdout.

A valid semantic/hybrid hit can be served without loading MiniLM or reading the semantic
tensor. If the canonical index advances, the revision changes and the normal semantic
staleness checks run on the resulting miss.

## Answer boundary

Retrieval caching and generated-answer caching are different contracts:

```text
answer --cache=True
  -> cached or fresh lexical MinimalSource list
  -> exact SQLite source hydration
  -> prompt fitting
  -> Qwen generation every time
```

Generated answers depend on the model revision, complete prompt/template, context
selection, token budget, generation settings, and runtime behavior. Caching them would
need a separate key, invalidation policy, quality contract, and storage boundary. It is
not needed for repeated retrieval and remains explicitly out of scope.

`answer_dataset` already receives prior source lists and never retrieves again, so adding
`--cache` there would be a misleading no-op.

## Tests

Focused acceptance coverage proves:

- persistence across independent calls and CLI processes;
- one retrieval for duplicate queries inside a batch;
- misses for exact query, `k`, mode/signature, semantic revision, and index revision;
- lexical, semantic, and hybrid CLI signature selection;
- Pydantic/canonical validation and corrupt-row replacement;
- retrieval and cache-write errors leave no row;
- byte-identical cached/uncached CLI output;
- `search_dataset` preserves duplicate question order and output identity;
- `answer` hits retrieval once but generates twice;
- `answer_dataset` exposes no retrieval-cache flag;
- all existing lexical, semantic, hybrid, answer, and batch-answer behavior remains green.

## Public benchmark

Fixed input: canonical public vLLM index with 1,969 files / 17,134 chunks, 100 Docs +
99 Code questions, `k=10`, two fresh CLI processes per observation, and no private data.
Each mode was measured for three rounds. “Miss” is an empty persistent cache; “hit” is a
second run over the same 199 exact questions. All raw observations, including the first
hybrid host outlier, are retained under ignored `data/output/issue20/`.

| Mode | No-cache s (3 rounds) | Miss s (3 rounds) | Hit s (3 rounds) | Median no-cache | Median miss | Median hit |
|---|---|---|---|---:|---:|---:|
| Lexical | 3.967 / 4.061 / 4.058 | 4.197 / 4.450 / 4.320 | 0.946 / 0.994 / 0.974 | 4.058 | 4.320 | 0.974 |
| Semantic | 18.831 / 18.928 / 18.862 | 18.917 / 19.798 / 18.910 | 0.996 / 1.029 / 1.067 | 18.862 | 18.917 | 1.029 |
| Hybrid | 35.330 / 34.667 / 31.555 | 82.488 / 31.266 / 36.291 | 4.376 / 1.454 / 1.189 | 34.667 | 36.291 | 1.454 |

The hybrid first-miss 82.488s and first-hit 4.376s observations are retained as host
outliers; medians, not deleted samples, summarize the result. Cache misses do not improve
distinct first-seen work and add small validation/write overhead. Persistent hits avoid
FTS/model/fusion work and are materially faster. This cache does not replace the mandatory
uncached performance path.

Every no-cache/miss/hit output was byte-identical within its mode. Fresh evaluation
reproduced the existing Recall@1/3/5/10 values exactly:

| Mode | Docs Recall@1/3/5/10 | Code Recall@1/3/5/10 |
|---|---|---|
| Lexical | 0.600 / 0.780 / 0.870 / 0.890 | 0.354 / 0.545 / 0.606 / 0.667 |
| Semantic | 0.270 / 0.410 / 0.440 / 0.530 | 0.263 / 0.333 / 0.404 / 0.465 |
| Hybrid | 0.450 / 0.700 / 0.790 / 0.870 | 0.323 / 0.495 / 0.596 / 0.707 |

All modes returned 199 validated questions / 1,990 sources with maximum span 2,000.
Each mode stored 199 rows. Logical key/payload size was 284,934 bytes lexical, 308,166
bytes semantic, and 333,404 bytes hybrid. SQLite allocated 438,272 / 471,040 / 507,904
bytes from existing free pages respectively, so the 37,699,584-byte database file did not
grow in this run.

## Deliberate non-goals

No generated-answer cache, TTL, LRU, automatic old-revision cleanup, size limit,
concurrency service, distributed cache, query-equivalence normalization, HTTP API, vector
database, new retrieval mode, model change, or private tuning. Historical revisions may
consume additional SQLite pages across many real content updates; add measured cleanup
only if actual database growth becomes a problem.
