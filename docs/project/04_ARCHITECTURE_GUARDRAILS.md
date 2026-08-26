# Architecture guardrails

## Minimum viable architecture
Keep the mandatory implementation small and source-preserving. The project uses
a modular monolith with hexagonal seams: dependency boundaries are real, but
ports/adapters are introduced only when a concrete use case needs them.

```text
adapters/cli (Fire)              future bonus: adapters/http
  -> application/use_cases
      -> application/ports       added only when implementations vary
          -> infrastructure      indexing/retrieval/generation/persistence
      -> domain/models           Pydantic JSON contracts + source spans
```

Layer rule: `domain` and `application` must not import `adapters` or
`infrastructure`. CLI and future HTTP adapters call the same use cases; if the
HTTP bonus requires moving retrieval, generation, or dataset orchestration out
of the CLI later, the initial architecture failed.

Planned seams by delivery order:

- Foundation: `domain/models`, package layout, and import-boundary tests.
- Corpus loading: deterministic source discovery with exact path/text fidelity.
- Chunking: distinct Python and Markdown/text strategies preserving original
  spans.
- Indexing/search: indexing/retrieval ports plus mandatory lexical
  infrastructure when search needs a replaceable retriever.
- Dataset/evaluation/answer commands: use cases as pure orchestration.
- Generation: generator port plus Qwen infrastructure when answer commands
  need a replaceable model adapter.
- Bonus semantic/hybrid retrieval: add `SemanticRetriever`/`HybridRetriever`
  behind the retriever port without changing search use cases, CLI, or HTTP.
- Bonus HTTP API: add `adapters/http` and reuse existing use cases.

Do not add dependency-injection containers, repository layers, factories,
databases, async workers, HTTP APIs, semantic embeddings, hybrid retrieval,
incremental indexing, or caching before the issue that actually needs them.

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
