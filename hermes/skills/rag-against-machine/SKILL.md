---
name: rag-against-machine
description: Project-specific workflow and evaluator constraints for the 42 RAG Against the Machine v2.0 implementation.
version: 1.0.0
metadata:
  hermes:
    tags: [rag, python, 42, retrieval, evaluation, github]
    category: development
---

# RAG Against the Machine project skill

## When to use
Load for planning, implementing, benchmarking, reviewing, or defending this repository.

## Required first read
The root `AGENTS.md` is authoritative. Then read only the relevant `docs/project/` and `docs/progress/` files.

## Procedure

1. Inspect Git status, GitHub issues/PRs, and associated Project.
2. Select exactly one issue-scoped vertical slice.
3. Confirm source/evaluator requirements relevant to that issue.
4. Activate Ponytail full for code changes.
5. Implement with tests and exact source-location preservation.
6. Run focused/full gates; benchmark public data for retrieval changes.
7. Run Ponytail review.
8. Update progress evidence.
9. Open/update a complete issue-linked PR and read CI back.
10. Keep private ground truth blind unless an explicit holdout rehearsal is authorized.

## Project-specific red flags

- Normalizing text and then emitting offsets from the normalized string.
- Returning absolute/shortened vLLM paths.
- Any source > 2000 chars.
- Re-indexing the whole corpus on every search.
- Hard-coded public/private question-to-file mappings.
- Importing/calling moulinette.
- Adding embeddings/hybrid/HTTP before mandatory lexical thresholds pass.
- Claiming tests/CI/Project updates that were not actually observed.

## References
Load `references/evaluator-cheatsheet.md` for the compact numeric/CLI contract.
