# Risk register

| ID | Risk | Impact | Mitigation / trigger | Status |
|---|---|---|---|---|
| R1 | Source offsets computed after normalization | Recall sources fail overlap | Store exact original start/end for every chunk; test Unicode/newlines | Open |
| R2 | Emitted path differs from `data/raw/vllm-0.10.1/...` | Correct result gets zero match | Path contract tests from public ground truth | Open |
| R3 | One source span > 2000 chars | Whole output may be rejected | Enforce max span at chunk creation and output validation | Open |
| R4 | Public benchmark overfitting | Private recall collapses | Keep private ground truth blind; prefer general chunk/ranking improvements | Open |
| R5 | Index rebuild/query too slow | Fail 300s/90s gates | #45 profiles uncached SQLite/NFS phases and keeps only an output-identical change reaching <=80s across three campus runs | Campus index passes at 10s; warm retrieval fails at 92s vs 90s |
| R6 | LLM stack too heavy/fragile | Answer commands unusable | #24 runtime + #13/#14 exact-context, lazy reuse, abstention, atomic output and public Qwen smokes; provision cache | Two-question cache-only batch passed; broader quality, full-context memory and evaluator cache remain unverified |
| R7 | GitHub Project token lacks scope | Board drifts from issues | Record limitation; sync later; never pretend success | Open |
| R8 | Agent implements bonus/speculative architecture early | Scope/defense risk | Mandatory-first roadmap + Ponytail full | Open |
| R9 | Slow `answer_dataset` prompts answer-shortening or `max_new_tokens` reduction | Lower answer quality and weaker defense | Profile public subset and CPU threads first; keep 128-token default unless measured quality-preserving evidence says otherwise | Open |
| R10 | Persistent retrieval cache returns stale sources after incremental updates | Wrong exact paths/spans or hidden recall regressions | Implement `index_revision` in #19 before #20; include retriever signature and revision in cache key | Open |
| R11 | `bootstrap-data.sh` selects its own `<tmp>/public` staging directory | Clean evaluator setup fails before commands run | Fix #43 with exact archive-root discovery and a regression check | Open |
| R12 | Campus NFS invalidates the runner's inherited working directory after a long step | Automated evidence steps fail with `cannot stat ... Permission denied` | Re-enter and validate `$ROOT` inside each runner step; keep command failures visible | Open |
