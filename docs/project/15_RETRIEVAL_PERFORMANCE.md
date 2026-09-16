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

## Native campus confirmation — 2026-09-15

Mario ran the merged candidate once on native campus Linux using private
unanswered questions only. The run did not open answered labels or invoke
Moulinette, so the previously recorded private Recall values were not
re-evaluated.

### Environment and provenance

- Run: `2026-09-15_18-09-20`.
- RAG commit: `6ff741a85bbfd848a3020980f22eec6990b59fa4`, the merge commit
  for PR #47.
- Host: `c3r4s5.42madrid.com`, Linux 5.15.
- CPU: Intel Core i5-8500, 6 cores / 6 threads; PyTorch default: 6 threads.
- Memory: 7.6 GiB RAM and 4.0 GiB swap.
- Filesystem: campus `/sgoinfre` NFS4.
- Runtime: Python 3.10.12 and uv 0.12.15.
- Complete ignored log: `evaluations/campus/2026-09-15_18-09-20/campus_test.log`
  (33,034 bytes; SHA-256
  `791ad01068805dc85007df969ecd9b1e892a5739597b8d831f25560da80a4995`).

The final integrity section reports `M scripts/campus_test.sh`. The exact local
runner diff was not captured, so this is not evidence that the tracked runner
itself was clean. It does not invalidate the retrieval measurement: `GIT_HEAD`
pins the RAG implementation to the merged PR #47 commit, and generated indexes,
model assets, and evaluation outputs remained ignored. Issue #25 separately
adds the known per-step repository-root guard to the tracked runner.

### Mandatory retrieval result

| Step | Result |
|---|---:|
| `uv sync --locked` | PASS, 0.111s |
| `make check` | PASS, 124 tests; 124.927s step time |
| Index 1,969 documents / 17,134 chunks | PASS, 10.172s |
| Private unanswered docs, 100 questions, `k=10` | PASS, 4.079s |
| Private unanswered code, 100 questions, `k=10` | PASS, 4.114s |
| Combined warm retrieval | **PASS, 8.193s <= 90s** |
| Headroom below limit | 81.807s |

The confirmation is 83.807 seconds lower than the earlier 92-second campus
observation (91.09%, or 11.23x). This is not a controlled paired benchmark:
the host changed from `c2r13s5` to `c3r4s5`, machine load was not controlled,
and the runner had an uncommitted modification. Therefore the evidence proves
that the merged candidate passed the required workload on campus NFS with wide
margin, but it does not assign the entire observed difference to the page-cache
statement.

### Remaining mandatory smokes

- Single search passed in 0.655s.
- `answer --k 0` abstained without loading the model in 0.240s.
- Public two-question search passed in 0.903s.
- Qwen loaded and answered the public Volta question correctly from one exact
  source in 33.763s: `Volta refers to SM 7.0.`
- Public two-question `answer_dataset` passed in 71.517s and exact input/output
  identity validation reported `BATCH_IDENTITY=PASS`.
- The supplied edge exam passed 4/4 in 2.115s without tracebacks.
- Every runner step exited 0 and `CAMPUS_TEST_RESULT=PASS`.

Eight generated artifacts were retained locally under the ignored run directory:
the complete log, two private unanswered retrieval outputs, the two-question
public input/search/answer files, and the single-answer plus `k=0` outputs. None
is committed.

The tracked #25 follow-up passed one focused runner contract test, `bash -n`,
the runner's `--help` path, `make check` with 125 tests in 50.95s, strict mypy
over 37 files, Flake8, context validation, and `git diff --check`.

## Limits and confirmation rule

At candidate-selection time, the 31.83% local CLI margin exceeded issue #45's
15% retention threshold but could not prove campus NFS performance. No
projection from 5.445 local seconds to a campus time was used.

The one allowed native-campus confirmation has now been consumed and passed on
unanswered inputs. Do not rerun private labels or repeat campus tuning. Issue
#45's mandatory timing gate is green; the remaining limitation is attribution,
not compliance. Query cache, concurrency, semantic retrieval, and ranking
changes remain out of scope until mandatory readiness documentation is closed.
