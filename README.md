*This project has been created as part of the 42 curriculum by masenjo.*

# RAG Against the Machine

## Description

This project implements a complete Retrieval-Augmented Generation (RAG) pipeline
for answering questions about the supplied vLLM 0.10.1 codebase. It discovers and
loads source files without changing their contents, applies separate chunking
strategies to Python and Markdown/text, persists a lexical SQLite FTS5 BM25 index,
retrieves ranked source locations, and grounds answers from Qwen/Qwen3-0.6B in the
retrieved evidence.

The mandatory pipeline is CPU-compatible and exposes all required operations through
Python Fire:

```text
uv run python -m src <command> [options]
```

Required commands implemented by the project are `index`, `search`,
`search_dataset`, `answer`, `answer_dataset`, and `evaluate`.

## System Architecture

The implementation is a small modular monolith with explicit dependency boundaries:

```text
Python Fire ───────────────┐
                           v
FastAPI Routers ──> RagApplication ──> PipelineOperations port
                                              ^
                                              |
                                   LocalPipelineOperations
                                     - corpus and chunking
                                     - SQLite FTS5 / cache
                                     - MiniLM semantic / RRF
                                     - Qwen generation
```

`RagApplication` owns adapter-neutral index/search/answer orchestration and returns
structured Pydantic results. Fire owns arguments, files, human formatting, progress, and
CLI error translation. FastAPI routers act as thin controllers for request validation,
application delegation, response models, and HTTP error translation.
`LocalPipelineOperations` owns concrete local filesystem, SQLite, MiniLM, cache, and Qwen
effects. `domain` and `application` import neither adapters nor infrastructure, and peer
adapter families may not import each other.

One coarse application-facing operations port is used instead of interfaces for every
SQLite/model function. There is no dependency-injection framework, background worker,
controller base class, or speculative backend registry. The local FastAPI adapter calls
the same use cases as Fire; it does not copy pipeline orchestration.

Pipeline flow:

1. Discover `.py`, `.md`, and `.txt` files in deterministic path order.
2. Read exact UTF-8 text while preserving newline characters.
3. Chunk each document with the strategy selected by its suffix.
4. Persist exact chunks and metadata in `data/processed/lexical_index.sqlite3`.
5. Optionally project those same canonical chunks into `semantic_index.pt`.
6. Rank with default BM25 or explicit normalized MiniLM cosine search.
7. Return exact file paths and half-open character ranges.
8. Hydrate selected source text by exact path and offsets.
9. Fit a ranked prefix of complete chunks into the Qwen prompt budget.
10. Generate answer text and serialize only the required Pydantic wrapper.

## Chunking Strategy

All source locations use half-open ranges:

```text
original_text[first_character_index:last_character_index]
```

The indexed text must equal that exact slice. Text is never normalized before final
offsets are assigned, and no emitted chunk may exceed the configured
`max_chunk_size`, whose default and hard maximum are 2,000 characters.

### Python

Python files are parsed with the standard-library `ast` module. Chunks begin at
module-level functions, asynchronous functions, and classes; decorators stay with
their definition, and module preamble text is preserved. Oversized structures are
split into exact bounded slices. Invalid Python syntax falls back safely to the same
bounded exact slicing rather than failing the complete corpus build.

### Markdown and text

Markdown/text files are scanned as paragraph-like blocks separated by blank lines.
Adjacent blocks are grouped while the complete range fits the configured maximum.
An oversized block is split into exact bounded slices. This keeps useful textual
context without inventing overlap or rewriting whitespace.

## Retrieval Method

The mandatory retriever uses SQLite FTS5 with the `unicode61` tokenizer and native
BM25 ranking. Query words are extracted as Unicode word tokens and converted into
quoted FTS terms joined with `OR`, which prevents punctuation from becoming FTS
syntax. Results are ordered by BM25 score and then canonical `rank_order` for
deterministic ties across full and incremental builds.

Single-query search opens one SQLite connection. Dataset search reuses one warm
connection for all questions and requests a demand-driven 64 MiB SQLite page cache:

```text
PRAGMA cache_size=-65536
```

This is an in-memory per-connection SQLite page cache for distinct FTS queries. It is
not a persistent query-result cache and creates no invalidation problem. Ranking,
paths, offsets, and JSON output are unchanged by the setting.

### Incremental indexing bonus

Full rebuild remains the default. `index --incremental=True` enables an explicit
file-level update path over schema-v2 indexes. The persisted file manifest records
canonical path, SHA-256 content hash, byte/character counts, and a monotonic
`index_revision`.

An unchanged corpus is a true no-op: the SQLite bytes and revision remain unchanged.
Added and content-changed files alone are re-chunked; deleted/changed stale chunks and
FTS rows are removed. Rename is naturally delete plus add. Updates run transactionally
on a sibling copy, validate counts, widths, FTS rows and SQLite integrity, then replace
the live index atomically. Incompatible lifecycle metadata triggers a visible safe full
rebuild. Canonical `rank_order` preserves the mandatory BM25 tie order independently
of mutable SQLite row IDs.

### Semantic embeddings bonus

Semantic mode is explicit; lexical BM25 remains the unchanged default. The pinned
`sentence-transformers/all-MiniLM-L6-v2` model runs through the installed Transformers
and torch CPU stack, using attention-mask mean pooling and L2 normalization. No
`sentence-transformers` package or vector database is required.

`data/processed/semantic_index.pt` is one atomically replaced torch artifact. It
contains a normalized float32 tensor, exact path/offset identities in canonical SQLite
chunk order, and Pydantic-validated schema/model/dimension/count/source-revision
metadata. It does not duplicate chunk text. Search rejects an artifact whose
`source_index_revision` or identities differ from the canonical SQLite store and ranks
with cosine dot products plus `torch.topk`, using canonical order for exact ties.

`index --semantic=True` builds both projections. With `--incremental=True`, the one
existing lexical update plan remains the only change detector: unchanged-file vectors
are reused, while every vector for changed/deleted files is invalidated and all new
chunks from changed/added files are embedded. Missing, stale, or incompatible semantic
state rebuilds only the semantic projection after a lexical no-op. Semantic writes use
a sibling temporary file, so a failure leaves the prior artifact intact and detectably
stale if SQLite has already advanced.

### Hybrid retrieval bonus

`search --hybrid=True` and `search_dataset --hybrid=True` run the existing BM25 and
MiniLM retrievers, then combine their top-`k` lists with equal-weight reciprocal rank
fusion using the fixed conventional rank constant 60. Exact path/offset identity
deduplicates a chunk returned by both modes; distinct adjacent or overlapping chunks
remain distinct. Fused-score ties resolve by exact canonical identity.

Hybrid mode adds no index, model, persisted artifact, score-calibration framework, or
tunable weight. `semantic=True` and `hybrid=True` are mutually exclusive, and omitting
both flags preserves lexical behavior exactly. Missing or stale semantic state fails
through the existing semantic validation before any fused output is written.

The evaluator counts a source when the path matches exactly and the retrieved and
expected ranges overlap above its IoU threshold. Consequently, the project preserves
the complete corpus prefix, for example:

```text
data/raw/vllm-0.10.1/docs/features/lora.md
```

## Answer Generation

`answer` performs one lexical search and hydrates every retrieved source through an
exact `(file_path, first_character_index, last_character_index)` SQLite lookup.
Missing or ambiguous tuples are technical errors; the pipeline never substitutes a
nearby chunk.

The generator uses the pinned Qwen/Qwen3-0.6B revision through Transformers on CPU
in float32. It uses greedy generation with thinking disabled. The default operational
budget is 2,048 tokens with 128 reserved output tokens. The exact chat template is
counted before model generation, and the context contains the longest ranked prefix
of complete source fragments that fits. A lower-ranked fragment is never selected
after a higher-ranked fragment fails to fit.

If retrieval returns no sources, including `k=0`, the command produces the fixed
abstention below without loading model assets:

```text
I cannot answer from the retrieved sources.
```

`answer_dataset` consumes an existing `StudentSearchResults` file; it does not run
retrieval again. It processes questions sequentially, preserves IDs, questions,
source order and `k`, reuses one lazy Qwen instance and at most one lazily opened
SQLite connection, and atomically replaces the final Pydantic output only after the
complete batch succeeds. Progress bars are written to stderr.

## Data Models and Output

Pydantic models validate every evaluator-facing stage:

- `MinimalSource`
- `UnansweredQuestion` and `AnsweredQuestion`
- `RagDataset`
- `MinimalSearchResults` and `MinimalAnswer`
- `StudentSearchResults`
- `StudentSearchResultsAndAnswer`

Search output is serialized from `StudentSearchResults`; answer output is serialized
from `StudentSearchResultsAndAnswer`. The model, not Qwen, owns JSON structure.

## Instructions

### Requirements

- Python 3.10 or later; `.python-version` selects 3.10.
- `uv` available on `PATH`.
- A Python build with SQLite FTS5 support.
- Enough disk space for dependencies, the vLLM corpus, indexes, and the Qwen and
  optional MiniLM model snapshots.
- Network access for first model downloads, or a pre-populated model cache.
- The optional HTTP adapter binds only to local loopback (`127.0.0.1`).

### Install dependencies

From the repository root:

```bash
uv sync --locked
```

`uv sync` installs Python dependencies but does not download model weights.

### Stage the supplied data

The supplied archives remain outside version control. On Bash/Linux/WSL:

```bash
bash scripts/bootstrap-data.sh \
  --vllm "/path/to/vllm-0.10.1.zip" \
  --public "/path/to/datasets_public.zip"
```

The optional private archive is a holdout and must not be used for tuning:

```bash
bash scripts/bootstrap-data.sh \
  --vllm "/path/to/vllm-0.10.1.zip" \
  --public "/path/to/datasets_public.zip" \
  --private "/path/to/datasets_private.zip"
```

Canonical local development paths are:

```text
data/raw/vllm-0.10.1/
data/datasets/datasets_public/public/UnansweredQuestions/
data/datasets/datasets_public/public/AnsweredQuestions/
data/processed/
data/output/
models/huggingface/
```

Runtime datasets, indexes, outputs, model files, evaluation runs, and local
Moulinette binaries are ignored by Git. Supplied exam scripts must remain untracked
unless they are explicitly intended for submission.

### Quality gates

```bash
make check
make lint-strict
```

`make check` runs repository-context validation, Flake8, mypy with the subject flags,
and pytest.

### Run the optional local HTTP API

The module launcher reserves `api` only when it is the first argument. Every other first
argument continues through the existing Python Fire CLI.

```bash
uv run python -m src api --help
uv run python -m src api --port 8000 --log-level info
```

The launcher starts Uvicorn in application-factory mode with
`src.adapters.http:create_app`, one worker, and fixed host `127.0.0.1`. Interactive
OpenAPI documentation is then available at `http://127.0.0.1:8000/docs`.

The three controller routes reuse the same application commands/results as the CLI:

```text
POST /index   -> IndexOperationResult
POST /search  -> MinimalSearchResults
POST /answer  -> MinimalAnswer
```

For example, after starting the server:

```bash
curl -X POST http://127.0.0.1:8000/index \
  -H 'Content-Type: application/json' \
  -d '{"corpus_path":"data/raw/vllm-0.10.1","save_directory":"data/processed"}'

curl -X POST http://127.0.0.1:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"What is paged attention?","index_directory":"data/processed","k":5}'

curl -X POST http://127.0.0.1:8000/answer \
  -H 'Content-Type: application/json' \
  -d '{"query":"What is paged attention?","index_directory":"data/processed","k":5}'
```

BM25 remains the default. Semantic, hybrid, and retrieval-cache modes remain explicit.
Dataset search, dataset answer, and evaluation stay on their existing CLI/file contracts;
the HTTP adapter intentionally exposes no duplicate endpoints for them.

This server is local development/bonus functionality, not a production deployment. It
does not promise thread-safe overlapping index/search/answer operations, idempotency,
authentication, TLS, CORS policy, job persistence, cancellation/timeouts, request queues,
rate limiting, multi-worker model lifecycle, or remote binding. Those concerns require a
future design covering operation identity, read/write exclusion, SQLite connection
ownership, atomic index transitions, model ownership, and worker/process lifecycle.

## Example Usage

### Build the lexical index

```bash
uv run python -m src index \
  --corpus_path data/raw/vllm-0.10.1 \
  --save_directory data/processed \
  --max_chunk_size 2000
```

### Update an existing compatible index incrementally

```bash
uv run python -m src index \
  --corpus_path data/raw/vllm-0.10.1 \
  --save_directory data/processed \
  --max_chunk_size 2000 \
  --incremental=True
```

### Build or update the optional semantic projection

```bash
uv run python -m src index \
  --corpus_path data/raw/vllm-0.10.1 \
  --save_directory data/processed \
  --semantic=True \
  --semantic_model_cache_directory models/huggingface \
  --local_files_only=True

uv run python -m src index \
  --corpus_path data/raw/vllm-0.10.1 \
  --save_directory data/processed \
  --incremental=True \
  --semantic=True \
  --local_files_only=True
```

### Search one question

```bash
uv run python -m src search \
  "What is paged attention?" \
  --index_directory data/processed \
  --k 5
```

### Search a public dataset

```bash
uv run python -m src search_dataset \
  --dataset_path data/datasets/datasets_public/public/UnansweredQuestions/dataset_docs_public.json \
  --index_directory data/processed \
  --save_directory data/output/search_results/UnansweredQuestions \
  --k 10
```

Add `--semantic=True --local_files_only=True` to select the semantic projection, or
`--hybrid=True --local_files_only=True` to fuse BM25 and semantic rankings. Omitting
both flags preserves BM25 exactly.

Add `--cache=True` to `search` or `search_dataset` to persist and reuse exact repeated
queries. The SQLite key includes cache schema, canonical `index_revision`, retrieval
mode/configuration signature, exact-query SHA-256, and `k`. It stores only ordered
`MinimalSource` locations; default `--cache=False` keeps the existing path unchanged.

### Evaluate public retrieval locally

```bash
uv run python -m src evaluate \
  --student_search_results_path data/output/search_results/UnansweredQuestions/dataset_docs_public.json \
  --dataset_path data/datasets/datasets_public/public/AnsweredQuestions/dataset_docs_public.json \
  --max_context_length 2000
```

This command is for local iteration. The official evaluator uses its own Moulinette;
the student implementation never imports or invokes it.

### Answer one question

The first network-enabled run downloads the pinned model snapshot to the configured
cache:

```bash
uv run python -m src answer \
  "What does Volta refer to in vLLM hardware documentation?" \
  --k 1 \
  --index_directory data/processed \
  --save_path data/output/search_results_and_answer/answer.json \
  --model_cache_directory models/huggingface \
  --token_budget 2048 \
  --max_new_tokens 128 \
  --cache=True
```

For `answer`, this flag caches only the lexical retrieval result. Exact source hydration,
prompt fitting, and Qwen generation still run on every call; generated answers are never
cached.

After the model snapshot cache exists, enforce offline loading with:

```text
--local_files_only=True
```

### Answer prior dataset search results

```bash
uv run python -m src answer_dataset \
  --student_search_results_path data/output/search_results/UnansweredQuestions/dataset_docs_public.json \
  --save_directory data/output/search_results_and_answer/UnansweredQuestions \
  --index_directory data/processed \
  --model_cache_directory models/huggingface \
  --token_budget 2048 \
  --max_new_tokens 128 \
  --local_files_only=True
```

`answer_dataset` accepts prior `StudentSearchResults` and performs no retrieval, so it
has no retrieval-cache flag.

## Performance Analysis

The mandatory lexical configuration uses `max_chunk_size=2000` and `k=10`.
Recorded public retrieval quality is:

| Dataset | Questions | Recall@1 | Recall@3 | Recall@5 | Recall@10 |
|---|---:|---:|---:|---:|---:|
| Documentation | 100 | 0.600 | 0.780 | 0.870 | 0.890 |
| Code | 99 | 0.354 | 0.545 | 0.606 | 0.667 |

Both mandatory Recall@5 thresholds pass: documentation requires at least 0.80 and
code at least 0.50. The public 199-question baseline completed in 12.187 seconds
before the later page-cache optimization. A final disposable clean-checkout run at
commit `010e568` rebuilt the supplied corpus in 3.551 seconds and completed the
public docs/code searches in 2.314 and 2.612 seconds respectively (4.926 seconds
combined), while reproducing every Recall value in the table. These local timings
are host-specific and are not substituted for the native-campus gate evidence.

Native campus evidence on the supplied corpus and NFS4 filesystem:

| Gate | Observed result | Requirement |
|---|---:|---:|
| Indexing | 10.172 s | <= 300 s |
| Warm retrieval, 200 unanswered questions | 8.193 s | <= 90 s |
| Maximum source span | 2,000 characters | <= 2,000 |

The only retained private-label evidence is aggregate: an explicitly authorized
blind validation and its unchanged-configuration campus reproduction both recorded
Docs Recall@5 0.800 and Code Recall@5 0.510. Those observations were confirmation,
not tuning inputs. The later 8.193-second campus timing confirmation used unanswered
inputs only and did not reopen the labels. It also used another campus host and a
locally modified runner, so it proves compliance on campus NFS but is not used to
attribute the complete cross-run improvement solely to the SQLite page cache.

Generation is CPU-bound and varies by host. A public ten-question profile showed
that generation accounted for roughly 91-97% of answer-batch wall time. Retrieval,
source hydration, and prompt fitting were not meaningful generation bottlenecks.
No answer length was reduced to improve timing.

Incremental-index evidence on a disposable full public corpus copy used three
rotated one-file changes:

| Operation | Median time | Comparison |
|---|---:|---:|
| Full rebuild after change | 3.004 s | baseline |
| One-file incremental update | 2.527 s | 15.90% faster |
| Unchanged incremental no-op | 1.513 s | no rewrite/revision change |

Every incremental index matched a clean full rebuild in canonical chunks and
byte-identical docs/code search JSON. A fresh canonical-path public run preserved
Docs Recall@1/3/5/10 at 0.600/0.780/0.870/0.890 and Code at
0.354/0.545/0.606/0.667. Timings are host/filesystem-specific; generated benchmark
artifacts remain ignored.

Public issue #17 evidence used the same 1,969 files, 17,134 chunks, 100 documentation
questions, and 99 code questions without private data:

| Method | Dataset | Recall@1 | Recall@3 | Recall@5 | Recall@10 | Search |
|---|---|---:|---:|---:|---:|---:|
| BM25 | Documentation | 0.600 | 0.780 | 0.870 | 0.890 | 1.819 s |
| BM25 | Code | 0.354 | 0.545 | 0.606 | 0.667 | 2.069 s |
| MiniLM cosine | Documentation | 0.270 | 0.410 | 0.440 | 0.530 | 7.077 s |
| MiniLM cosine | Code | 0.263 | 0.333 | 0.404 | 0.465 | 7.005 s |

The full lexical plus semantic build took 379.690 s on this Windows CPU host. A
one-file semantic incremental update took 19.797 s, a validated semantic no-op took
5.603 s, and the artifact was 27,862,262 bytes with shape `(17134, 384)`. These
host-specific bonus timings do not alter the mandatory default's <=300 s lexical gate.

Public issue #18 evidence reran all three modes over the same corpus/questions:

| Method | Dataset | Recall@1 | Recall@3 | Recall@5 | Recall@10 | Search |
|---|---|---:|---:|---:|---:|---:|
| BM25 | Documentation | 0.600 | 0.780 | 0.870 | 0.890 | 2.374 s |
| BM25 | Code | 0.354 | 0.545 | 0.606 | 0.667 | 2.613 s |
| MiniLM cosine | Documentation | 0.270 | 0.410 | 0.440 | 0.530 | 11.437 s |
| MiniLM cosine | Code | 0.263 | 0.333 | 0.404 | 0.465 | 11.357 s |
| Equal RRF hybrid | Documentation | 0.450 | 0.700 | 0.790 | 0.870 | 14.418 s |
| Equal RRF hybrid | Code | 0.323 | 0.495 | 0.596 | 0.707 | 14.403 s |

Hybrid improved Code Recall@10 over BM25 from 0.667 to 0.707, but reduced the other
recorded BM25 cutoffs and documentation Recall. It therefore remains an explicit
experimental bonus and does not justify changing the lexical default or adding weights.
Exact cross-mode duplicates were 244 of 1,000 lexical candidates for Docs (24.40%) and
137 of 990 for Code (13.84%); the denominator is the total lexical top-10 candidates
summed across all questions, equal in size to the semantic candidate denominator.

Public issue #20 evidence measured opt-in persistent caching over the same 199 distinct
questions in two CLI processes. Values are three-run medians; a miss starts with an empty
cache and a hit repeats the same questions:

| Mode | No cache | Empty-cache miss | Persistent hit | Rows | Logical bytes |
|---|---:|---:|---:|---:|---:|
| BM25 | 4.058 s | 4.320 s | 0.974 s | 199 | 284,934 |
| MiniLM cosine | 18.862 s | 18.917 s | 1.029 s | 199 | 308,166 |
| Equal RRF hybrid | 34.667 s | 36.291 s | 1.454 s | 199 | 333,404 |

No-cache, miss, and hit outputs were byte-identical per mode; all Recall@1/3/5/10 values
above reproduced exactly and maximum span stayed 2,000. SQLite reused existing free pages,
so the 37,699,584-byte file did not grow in this run while allocating 438,272-507,904
bytes internally. Misses do not accelerate distinct first-seen evaluator queries; this
bonus is for real repetition and does not replace mandatory uncached performance.

## Design Decisions

- Use exact original text and half-open spans as the central correctness invariant.
- Use two small, distinct chunkers instead of one generic segmentation framework.
- Start with the mandatory lexical method and keep BM25 as the stable default.
- Use standard-library SQLite FTS5 rather than adding a search service.
- Build a complete temporary index and replace the destination atomically.
- Keep full rebuild as the mandatory default and incremental updates explicit.
- Use content hashes rather than mtime as the correctness identity.
- Preserve deterministic ranking with canonical order separate from SQLite row ID.
- Keep embeddings as a second atomic projection over canonical SQLite chunks rather
  than introducing another chunk store, change detector, or vector database.
- Fuse lexical and semantic ranks with one fixed equal-weight RRF function rather than
  calibrating incomparable BM25 and cosine scores or adding tuning knobs.
- Cache only ordered exact retrieval results under revision/configuration-aware SQLite
  keys; never cache generated answers.
- Expose the optional local API as thin FastAPI routers over `RagApplication`, and reserve
  only first argument `api` in the module launcher so Fire remains unchanged.
- Reuse one warm SQLite connection for dataset search.
- Expand only the batch connection's page cache after profiling showed FTS execution
  dominated retrieval time.
- Keep complete ranked chunks in prompts; never truncate a source fragment.
- Keep Qwen lazy so abstention and invalid-budget paths do not load model weights.
- Keep answer batches sequential and atomic; concurrency was not needed for the
  mandatory contract.
- Preserve Python/Pydantic ownership of output JSON.
- Keep private answered datasets blind and use public data for development.

## Challenges and Limitations

- Exact path prefixes and character ranges are evaluator-visible, so newline handling
  and text normalization had to be controlled carefully.
- Python AST byte columns are unsafe for direct character offsets with Unicode; the
  chunker uses exact line-start character offsets instead.
- Natural-language questions and code identifiers do not always share vocabulary;
  lexical BM25 therefore has a lower code Recall@5 than documentation Recall@5.
- Standalone MiniLM cosine retrieval underperformed BM25 on both public datasets and
  its measured full optional build exceeded 300 seconds on this host.
- Equal-weight hybrid RRF improved only Code Recall@10 and reduced other BM25 cutoffs;
  semantic and hybrid therefore remain explicit experimental modes.
- Campus NFS performance differed greatly from local filesystems. Profiling identified
  SQLite FTS execution as the useful optimization target, while mmap was rejected as
  a riskier filesystem-dependent choice.
- `uv sync` does not provision Qwen weights. Offline evaluation requires the pinned
  snapshot to be cached in advance.
- Qwen/Qwen3-0.6B is intentionally small and CPU-compatible; answers may be incomplete
  when retrieval evidence is weak, even though the prompt requires grounding.
- The operational prompt budget is conservative and does not claim that every host can
  use the model's maximum architectural context.
- Persistent retrieval caching retains old-revision rows until a full rebuild; add cleanup
  only if measured database growth justifies it.
- The FastAPI bonus is intentionally localhost-only and single-worker. FastAPI may execute
  synchronous handlers in worker threads, but the project provides no concurrency,
  idempotency, multi-worker, remote-deployment, or production-security guarantee.

## Resources

- 42 subject: `RAG against the machine`, version 2.0.
- Python `ast`: https://docs.python.org/3/library/ast.html
- SQLite FTS5: https://www.sqlite.org/fts5.html
- SQLite `cache_size`: https://www.sqlite.org/pragma.html#pragma_cache_size
- Pydantic: https://docs.pydantic.dev/
- Python Fire: https://github.com/google/python-fire
- FastAPI: https://fastapi.tiangolo.com/
- Uvicorn: https://www.uvicorn.org/
- tqdm: https://tqdm.github.io/
- uv: https://docs.astral.sh/uv/
- Qwen/Qwen3-0.6B: https://huggingface.co/Qwen/Qwen3-0.6B
- all-MiniLM-L6-v2: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
- Transformers: https://huggingface.co/docs/transformers/

### AI Usage

AI tooling was used as an engineering assistant to distill the supplied subject and
correction scripts, plan issue-sized slices, inspect code, propose minimal patches,
generate and review tests/documentation, and organize benchmark evidence. Every
accepted change was reviewed against the repository contracts and exercised with
real tests, linting, type checking, CLI smokes, public benchmarks, or campus evidence
as applicable. AI was not used to inspect private ground-truth spans for tuning or to
hard-code question-to-source mappings. The author remains responsible for the design,
code, measurements, and defense.

## Defense Notes

The detailed Spanish defense and recode preparation guide is available at
[`docs/project/16_DEFENSE_GUIDE_ES.md`](docs/project/16_DEFENSE_GUIDE_ES.md).
