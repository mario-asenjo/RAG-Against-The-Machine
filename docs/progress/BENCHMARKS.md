# Retrieval benchmark ledger

No implementation baseline exists yet.

| Run | Commit | Method | Chunking | Index s | Warm search s | Docs R@5 | Code R@5 | Max span | Conclusion |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| M0 | scaffold | n/a | n/a | n/a | n/a | n/a | n/a | n/a | Harness only |
| M2-I1 | 2a34c0a | SQLite FTS5 BM25 | Python structural + text blocks, max 2000 | 41.414 cold; 5.049 refresh | n/a | n/a | n/a | 2000 | 1,969 files / 17,139 exact chunks; indexing gate passes, ranking unmeasured |
| M2-I2 | issue #8 worktree | SQLite FTS5 BM25, OR-token query | Same, max 2000 | 3.732 refresh | 5.343 / 200-query local smoke | n/a | n/a | 2000 | Ranked exact-source search works; public dataset recall remains #10 |
