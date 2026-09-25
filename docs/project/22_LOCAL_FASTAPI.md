# Local FastAPI adapter

## Scope

Issue #21 adds an optional local HTTP transport over the adapter-neutral pipeline seam
from issue #56. The mandatory Python Fire CLI, BM25 default, model/index artifacts,
retrieval ranking, generation, and evaluator JSON contracts remain unchanged.

## Launch contract

`python -m src` reserves only the first argument `api`:

```text
uv run python -m src api --port 8000 --log-level info
```

The launcher otherwise delegates to the existing Fire entry point without rewriting its
arguments. API mode calls Uvicorn with
`src.adapters.http:create_app`, `factory=True`, `host=127.0.0.1`, and one worker.
`uv run python -m src api --help` owns the API-specific help. The bind address and worker
count are deliberately fixed; this is a local adapter, not a deployment recipe.

## Transport boundary

```text
Python Fire ---------------+
                           v
FastAPI Routers ---> RagApplication ---> PipelineOperations
                                              ^
                                              |
                                   LocalPipelineOperations
```

`create_app()` constructs one `FastAPI` object, installs one `RagApplication`, registers
expected-error handlers, and includes three small routers. Routers act as controllers:
they validate a Pydantic request, call one existing `RagApplication` method, and return its
existing Pydantic result. They contain no index lifecycle, retriever selection, caching,
source hydration, prompt fitting, or model-generation logic.

The adapter exposes:

| Method | Path | Request | Response |
|---|---|---|---|
| `POST` | `/index` | `IndexRequest` over `IndexCommand` | `IndexOperationResult` |
| `POST` | `/search` | query plus `RetrievalCommand` fields | `MinimalSearchResults` |
| `POST` | `/answer` | query plus `AnswerCommand` fields | `MinimalAnswer` |

Request defaults match the existing CLI defaults. BM25 remains the search default;
semantic, hybrid, and retrieval cache behavior are still explicit. `/answer` keeps its
existing lexical retrieval contract and never caches generated text. Dataset search,
dataset answer, and evaluation remain CLI/file-oriented operations and are intentionally
not duplicated as HTTP endpoints.

FastAPI publishes `/openapi.json`, `/docs`, and `/redoc` from those Pydantic contracts.

## Error boundary

Expected local application failures are translated once in the HTTP adapter:

- missing local artifacts: `404` with an `error` field;
- semantically invalid operation/configuration: `400` with an `error` field;
- expected runtime, filesystem, or SQLite failure: `500` with an `error` field;
- malformed request shape/type: FastAPI Pydantic `422` validation response.

The CLI keeps its established `FireError` translation and output. HTTP types do not enter
the application or domain layers.

## Deliberate local-only ceiling

The adapter adds no authentication, authorization, TLS, CORS policy, idempotency keys,
request/job persistence, cancellation, queue, rate limiting, concurrency coordination,
or multi-worker model lifecycle. Synchronous route functions may run in the FastAPI
thread pool, while SQLite/index replacement and heavyweight model ownership were designed
for the existing local sequential workflow. Therefore overlapping mutating/read requests
are not promised safe, and the README does not present this server as production-ready.

Add a deliberate concurrency/idempotency design only when a real remote or multi-client
use case exists. That design must specify operation identity, read/write exclusion,
SQLite connections, atomic index transitions, model lifecycle, cancellation/timeouts,
and worker/process ownership before enabling external binding or multiple workers.

## Dependencies

- Runtime: FastAPI and Uvicorn.
- Development HTTP client: `httpx2`, selected because the installed FastAPI/Starlette
  TestClient explicitly targets it.

No ASGI middleware stack, DI container, controller base class, service locator, generic
router factory, or external service was added.

## Evidence

- Focused HTTP/launcher suite: 12 tests passed.
- `make check`: context validation, Flake8, subject mypy flags, and 202 tests passed.
- `make lint-strict`: Flake8 and strict mypy over 63 source files passed.
- `uv sync --locked` and `git diff --check` passed.
- A detached clean-worktree rehearsal at `c37fa56` created a Python 3.10 environment
  from `uv.lock`, passed `make check` with 202 tests, returned clean API help and final
  Fire `status`, and left the worktree clean.
- Independent delivery audit returned `ACEPTAR`. Ponytail-full found one invalid-port
  traceback path; range validation and subprocess regressions for `-1`/`65536` were added,
  and the focused follow-up returned `ACEPTAR`.
- Real Uvicorn factory smoke on `127.0.0.1`: OpenAPI plus full index, search, and
  model-free `k=0` answer returned HTTP 200; exact source path and offsets were preserved.
- The real tiny HTTP index contained one document and one chunk; search returned its exact
  `[0:22]` span; answer returned the established abstention with no model download.
- All six public lexical/semantic/hybrid Docs/Code outputs retained their frozen SHA-256
  values after the launcher/adapter change. Maximum span remained 2,000.
- Public Recall@1/3/5/10 remained lexical Docs `0.600/0.780/0.870/0.890`, lexical Code
  `0.354/0.545/0.606/0.667`, semantic Docs `0.270/0.410/0.440/0.530`, semantic Code
  `0.263/0.333/0.404/0.465`, hybrid Docs `0.450/0.700/0.790/0.870`, and hybrid Code
  `0.323/0.495/0.596/0.707`.
- No private dataset or ground-truth span was inspected.
