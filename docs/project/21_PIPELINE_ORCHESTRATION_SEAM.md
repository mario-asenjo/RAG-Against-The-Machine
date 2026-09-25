# Adapter-neutral pipeline orchestration

## Scope

Issue #56 is the architecture prerequisite for parent bonus #21. It extracts the existing
index, retrieval, and single-answer flows from Python Fire without adding HTTP code or a
framework dependency.

## Boundary

```text
Fire adapter ──> RagApplication ──> PipelineOperations
                                         ^
                                         |
                              LocalPipelineOperations
```

`RagApplication` is the shared use-case facade. It accepts Pydantic commands and returns
existing Pydantic pipeline contracts. `PipelineOperations` is one cohesive port for the
concrete effects that cannot point inward. `LocalPipelineOperations` implements those
effects with the already-shipped corpus, SQLite, semantic, cache, and Qwen adapters.

This is deliberately one port, not interfaces for every persistence/model helper. There
is no factory, registry, DI container, repository layer, or alternate backend.

## Shared commands and results

- `IndexCommand`: existing full/incremental/semantic configuration.
- `RetrievalCommand`: existing lexical/semantic/hybrid/cache configuration.
- `AnswerCommand`: existing lexical retrieval, Qwen, and token-budget configuration.
- `IndexOperationResult`: structured full/fallback/incremental/unchanged metadata and
  semantic action.

Search returns `MinimalSearchResults`, dataset search returns `StudentSearchResults`, and
single answer returns `MinimalAnswer`. The Fire adapter formats or persists these models;
the application never emits CLI text or imports Fire.

## Responsibility split

### `RagApplication`

- delegate structured index operations;
- build single and dataset search Pydantic models from one retrieval boundary;
- preserve dataset ID/question/order/`k`;
- compose lexical retrieval, exact source hydration, and `answer_search_result`;
- keep generated answers outside retrieval caching.

### `LocalPipelineOperations`

- run the existing full/incremental/semantic index lifecycle;
- select lexical, semantic, or hybrid retrieval once for both single and batch calls;
- apply the existing persistent query cache and signatures;
- hydrate exact canonical sources;
- construct the existing lazy Qwen adapter.

### Fire CLI

- parse the unchanged scalar options;
- construct shared commands;
- enable progress;
- read/write dataset and answer files;
- preserve established human status/source text;
- translate expected failures into `FireError`.

`answer_dataset` remains its existing sequential prior-result adapter and performs no
retrieval. `evaluate` remains CLI-only. Neither belongs to the planned three-endpoint API.

## Preserved behavior

- All Fire method signatures and positional argument order remain unchanged.
- Full/incremental/no-op/fallback and semantic lifecycle behavior remains unchanged.
- Lexical default, semantic, hybrid, cache, stale-index, exact path/offset, and progress
  behavior remains unchanged.
- Application/domain still import no outer layer.
- Peer adapters are prohibited from importing each other.
- No index, semantic artifact, cache schema, model, ranking, JSON wrapper, or dependency
  changed.

## HTTP decision deliberately deferred

Parent #21 will compare FastAPI routers/controllers with stdlib `HTTPServer` after this PR
merges. Both must consume `RagApplication`; framework choice may affect only transport,
validation/error mapping, server startup, tests, and documentation. It may not move or
copy index/retrieval/answer logic.

Decision inputs for #21:

- total runtime/dev dependency cost;
- route/error code size and clarity;
- Pydantic request/response integration;
- local-only binding and synchronous long-operation behavior;
- lightweight real HTTP tests;
- OpenAPI value versus framework ownership.

No HTTP server, route, Router, ASGI handler, `HTTPServer`, FastAPI, Uvicorn, or HTTPX is
part of issue #56.

## Evidence

- Focused pre-extraction baseline: 125 indexing/retrieval/answer tests passed.
- Shared seam + architecture tests: 5 passed.
- Full `make check`: 190 passed; context, Flake8, and subject mypy passed.
- `make lint-strict` and `git diff --check`: passed.
- Public lexical, semantic, and hybrid Docs/Code output SHA-256 values exactly matched the
  frozen pre-refactor hashes; no Recall rerun or private data was needed because bytes are
  identical.
