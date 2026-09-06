# Risk register

| ID | Risk | Impact | Mitigation / trigger | Status |
|---|---|---|---|---|
| R1 | Source offsets computed after normalization | Recall sources fail overlap | Store exact original start/end for every chunk; test Unicode/newlines | Open |
| R2 | Emitted path differs from `data/raw/vllm-0.10.1/...` | Correct result gets zero match | Path contract tests from public ground truth | Open |
| R3 | One source span > 2000 chars | Whole output may be rejected | Enforce max span at chunk creation and output validation | Open |
| R4 | Public benchmark overfitting | Private recall collapses | Keep private ground truth blind; prefer general chunk/ranking improvements | Open |
| R5 | Index rebuild/query too slow | Fail 300s/90s gates | Persist index; benchmark early; optimize only measured bottlenecks | Public index and warm-query gates passed; private unclaimed |
| R6 | LLM stack too heavy/fragile | Answer command unusable | #24 runtime + #13 exact-context budget, abstention and public Qwen smoke; provision cache | Single public RAG smoke passed; broader quality, full-context memory and evaluator cache remain unverified |
| R7 | GitHub Project token lacks scope | Board drifts from issues | Record limitation; sync later; never pretend success | Open |
| R8 | Agent implements bonus/speculative architecture early | Scope/defense risk | Mandatory-first roadmap + Ponytail full | Open |
