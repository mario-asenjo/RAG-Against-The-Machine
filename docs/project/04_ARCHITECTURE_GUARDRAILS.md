# Architecture guardrails

## Minimum viable architecture
Keep the mandatory implementation small and source-preserving.

```text
CLI (Fire)
  -> pipeline/orchestration
      -> corpus reader + chunkers
      -> persisted lexical index
      -> retriever
      -> context builder + Qwen generator
      -> Pydantic JSON outputs
```

## Exact-offset invariant
Never compute final source spans from transformed text. Normalization/tokenization may be used for ranking, but each indexed chunk must retain its original file path and exact original character start/end. This is the central retrieval correctness invariant.

## Chunking hypothesis, not premature commitment
A good first public-baseline experiment is:

- Python: structure-aware chunks around top-level classes/functions/method regions with safe splitting/fallback for oversized regions.
- Markdown/text: heading/paragraph-aware chunks with bounded overlap.

But issue implementation should measure rather than treat this as dogma. The only hard constraint is that Python and text use distinct strategies and emitted spans stay <= the configured maximum.

## Retrieval minimalism
Start with exactly one required lexical method. Add a second lexical method only when a measured public-data experiment justifies it. Semantic/hybrid retrieval is bonus scope and must not delay mandatory pass thresholds.

## Persistence
Persist enough index metadata to avoid reparsing the corpus on every query. Retrieval must load/query the persisted index quickly. Do not introduce a database unless file-based persistence measurably fails requirements.

## Generation
Keep answer generation downstream from retrieval. It must consume retrieved sources rather than re-searching the corpus invisibly. Prompt instructions should tell the model to answer from context and admit insufficient evidence rather than hallucinate.

## Error boundary
Translate expected failures at the CLI boundary into concise messages and stable non-zero return behavior. Internal functions may raise typed/domain-specific exceptions. Never broadly swallow programming errors just to hide tracebacks during development tests.
