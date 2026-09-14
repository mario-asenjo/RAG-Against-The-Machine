# Mandatory retrieval performance — issue #45

## Purpose

The native campus run at merged commit `e367ecb` took 92 seconds for 200
private unanswered questions on `/sgoinfre` NFS4. That exceeds the mandatory
90-second limit, so this slice optimizes the uncached lexical batch path before
any bonus work.

Private labels were not opened or evaluated during this work. All tuning used
the public docs/code datasets and the existing public SQLite index. The later
campus confirmation is limited to unanswered inputs.

## Fixed local workload

- Host: Windows 11 build 26200, 16 logical CPUs.
- Runtime: CPython 3.10.20 through `uv`; SQLite 3.53.1.
- Filesystem: local home-machine filesystem, not campus Linux/NFS.
- Index: `data/processed/lexical_index.sqlite3`, 35.230 MiB, 9,019 pages of
  4,096 bytes.
- SQLite defaults: `cache_size=-2000` (approximately 2 MiB), `mmap_size=0`,
  `temp_store=0`.
- Inputs: 100 public docs questions plus 99 public code questions.
- Shape: two fresh `search_dataset` processes in docs-then-code order, `k=10`,
  matching the evaluator's process boundary.
- Raw traces and generated outputs: `data/output/profiling/issue45/`
  (gitignored).

The CLI comparison used one warm-up pair followed by three measured pairs.
The phase probe rotated candidate order between rounds and rebuilt the exact
`StudentSearchResults` models. Process startup was measured separately with
five `uv run python -c pass` executions: 0.625, 0.447, 0.452, 0.489, and
0.562 seconds (0.515-second mean).

## Baseline phase result

The phase probe showed that SQLite FTS execution owns effectively all local
work. Median baseline phase times across the two public datasets were:

| Phase | Seconds |
|---|---:|
| Dataset reads | 0.003480 |
| Pydantic validation | 0.000905 |
| Two SQLite connections | 0.001331 |
| First query in each dataset | 0.148354 |
| Remaining 197 queries | 15.141295 |
| Pydantic result construction | 0.001248 |
| JSON serialization | 0.003254 |
| Total | 15.302 |

FTS query execution represented 99.92% of the measured total. Startup,
validation, connection opening, model construction, and serialization are not
useful optimization targets.

## SQLite experiments

Each option retained the same query tokenization, BM25 SQL, ordering, `k`, and
Pydantic output. The first exploratory series tested one setting after the
current connection baseline:

| Variant | Median seconds | Change vs baseline | Decision |
|---|---:|---:|---|
| Current connection | 14.283 | baseline | Reference |
| Read-only URI | 14.482 | 1.4% slower | Reject |
| Read-only immutable URI | 14.378 | 0.7% slower | Reject |
| `temp_store=MEMORY` | 14.216 | 0.5% faster | Reject |
| 64 MiB page cache | 4.450 | 68.8% faster | Retest |
| 256 MiB mmap | 4.235 | 70.3% faster | Reject for NFS risk |

A second rotated four-round series isolated normal-path cache sizes and mmap:

| Variant | Median seconds | Gain vs 15.302-second baseline |
|---|---:|---:|
| Current connection | 15.302 | baseline |
| Normal connection + 32 MiB page cache | 5.188 | 66.1% |
| Normal connection + 64 MiB page cache | 5.144 | 66.4% |
| Normal connection + 256 MiB mmap | 4.805 | 68.6% |
| Read-only URI + 64 MiB page cache | 5.185 | 66.1% |

The 64 MiB page cache was selected. It keeps the ordinary SQLite path, is
large enough for the current 35.230 MiB index with growth/working headroom,
and avoids making the mandatory path depend on URI or immutable semantics.
Although mmap was slightly faster locally, SQLite disables it by default and
its behavior depends more directly on operating-system/filesystem support. A
small local advantage does not justify adding that uncertainty for campus NFS.

This is SQLite's per-connection page cache for distinct FTS queries. It is not
the bonus persistent query-result cache from #20 and creates no reusable query
entries.

References:

- SQLite `cache_size`: <https://www.sqlite.org/pragma.html#pragma_cache_size>
- SQLite memory-mapped I/O: <https://www.sqlite.org/mmap.html>
- SQLite network-filesystem caveats: <https://www.sqlite.org/useovernet.html>

## Production CLI comparison

The retained change is one connection-local statement in
`search_lexical_index_batch`:

```text
PRAGMA cache_size=-65536
```

Negative `cache_size` values request a kibibyte budget, so this requests a
64 MiB maximum page cache. Allocation remains demand-driven and lasts only for
the batch connection.

The measured docs+code pairs, excluding each configuration's first warm-up
pair, were:

| Configuration | Run 1 | Run 2 | Run 3 | Median | Median gain |
|---|---:|---:|---:|---:|---:|
| Existing 2 MiB default | 8.015s | 7.987s | 7.967s | 7.987s | baseline |
| 64 MiB page cache | 5.445s | 5.631s | 5.187s | 5.445s | 31.83% |

Every subprocess exited 0. Baseline and candidate files were byte-identical:

```text
docs SHA-256: 52996f9cf6b692210e0f70478b184921a415d90127e82182d19c6bdee92ce199
code SHA-256: 97ab7c56779e8379e7220a50b8fb109bb7df8b021a3f08bf67f7383a63175301
```

Fresh local evaluation remained unchanged:

| Dataset | Recall@1 | Recall@3 | Recall@5 | Recall@10 |
|---|---:|---:|---:|---:|
| Docs | 0.600 | 0.780 | 0.870 | 0.890 |
| Code | 0.354 | 0.545 | 0.606 | 0.667 |

The focused search suite also pins the measured page-cache statement and all
existing output/error behavior.

Fresh validation on the candidate:

```text
uv run pytest tests/test_search.py -q
22 passed

make check
Context validation passed
Flake8 passed
Mypy passed over 36 source files
124 tests passed in 87.94s

make lint-strict
Flake8 passed
Strict mypy passed over 36 source files

git diff --check
passed
```

The two candidate files revalidated as `StudentSearchResults`: 100 docs plus
99 code questions, 1,990 retrieved sources, `k=10`, and maximum source span
2,000 characters.

Fresh CLI edge smokes retained deliberate behavior without tracebacks: empty
query exited 2 with `query must contain searchable terms`; a nonsense query
exited 0 with no sources or diagnostics; and a missing dataset exited 2 with a
clear file error. No output file was created or replaced by the failing batch.

## Limits and confirmation rule

The 31.83% local CLI margin exceeds issue #45's 15% retention threshold, but
this home Windows result cannot prove campus NFS performance. No projection
from 5.445 local seconds to a campus time is claimed.

After merge, run at most one native-campus confirmation on unanswered inputs
using the unchanged candidate. Do not rerun private labels. The mandatory
retrieval gate remains pending until that run reports a combined time below
90 seconds with useful safety margin. If the candidate does not transfer to
NFS, record it and open one narrower NFS diagnostic issue; do not add query
cache, concurrency, semantic retrieval, or ranking changes speculatively.
