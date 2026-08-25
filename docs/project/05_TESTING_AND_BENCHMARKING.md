# Testing and benchmarking strategy

## Layers

1. **Unit tests**: exact offset math, chunk limits, path preservation, model validation, ranking helpers, recall calculation.
2. **Contract tests**: JSON shapes and mandatory CLI signatures.
3. **Integration tests**: small temporary corpus -> index -> search -> persisted reload.
4. **Public benchmark**: full vLLM corpus + public docs/code questions.
5. **Answer smoke**: a few public questions with retrieved context and Qwen.
6. **Edge cases**: mirror the provided exam script.
7. **Clean-clone rehearsal**: install/run from README only.
8. **Private blind rehearsal**: only when explicitly authorized and not used for tuning.

## Public benchmark record
For each meaningful retrieval experiment append to `docs/progress/BENCHMARKS.md`:

- date/time;
- git SHA/branch;
- retrieval method;
- chunker parameters;
- indexed file/chunk counts;
- maximum observed source span;
- index wall time;
- docs dataset count and Recall@1/3/5/10;
- code dataset count and Recall@1/3/5/10;
- combined warm retrieval wall time;
- change from prior baseline;
- conclusion/next action.

## Performance discipline
Do not optimize model answer speed before retrieval passes its 90-second gate. Do not cache query results just to pass public benchmark unless caching is also valid for unseen evaluator queries; prefer index loading/vectorized ranking improvements first.
