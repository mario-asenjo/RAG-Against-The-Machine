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
Python Fire CLI (src/adapters/cli.py)
        |
        +--> application use cases
        |      - build lexical index input
        |      - evaluate Recall@k
        |      - fit retrieved evidence and generate an answer
        |
        +--> infrastructure adapters
        |      - exact corpus loading
        |      - SQLite FTS5 persistence and BM25 search
        |      - Qwen/Transformers generation
        |
        +--> Pydantic domain contracts
               - documents and exact source chunks
               - datasets, search results, and answers
               - index metadata
```

`domain` and `application` do not depend on CLI or infrastructure modules. Ports are
used only where the current implementation needs an interchangeable collaborator,
such as chunking and text generation. There is no dependency-injection framework,
server, background worker, or speculative retrieval abstraction.

Pipeline flow:

1. Discover `.py`, `.md`, and `.txt` files in deterministic path order.
2. Read exact UTF-8 text while preserving newline characters.
3. Chunk each document with the strategy selected by its suffix.
4. Persist exact chunks and metadata in `data/processed/lexical_index.sqlite3`.
5. Tokenize a query safely and rank matching chunks with SQLite FTS5 BM25.
6. Return exact file paths and half-open character ranges.
7. Hydrate selected source text by exact path and offsets.
8. Fit a ranked prefix of complete chunks into the Qwen prompt budget.
9. Generate answer text and serialize only the required Pydantic wrapper.

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
syntax. Results are ordered by BM25 score and then stable chunk ID for deterministic
ties.

Single-query search opens one SQLite connection. Dataset search reuses one warm
connection for all questions and requests a demand-driven 64 MiB SQLite page cache:

```text
PRAGMA cache_size=-65536
```

This is an in-memory per-connection SQLite page cache for distinct FTS queries. It is
not a persistent query-result cache and creates no invalidation problem. Ranking,
paths, offsets, and JSON output are unchanged by the setting.

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
source order and `k`, reuses one lazy Qwen instance and one SQLite connection, and
atomically replaces the final Pydantic output only after the complete batch succeeds.
Progress bars are written to stderr.

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
- Enough disk space for dependencies, the vLLM corpus, the SQLite index, and the
  approximately 1.5 GB Qwen model snapshot.
- Network access for the first Qwen download, or a pre-populated model cache.

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

All runtime datasets, indexes, outputs, evaluator tools, and model files are ignored
by Git.

### Quality gates

```bash
make check
make lint-strict
```

`make check` runs repository-context validation, Flake8, mypy with the subject flags,
and pytest.

## Example Usage

### Build the lexical index

```bash
uv run python -m src index \
  --corpus_path data/raw/vllm-0.10.1 \
  --save_directory data/processed \
  --max_chunk_size 2000
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
  --max_new_tokens 128
```

After the cache exists, enforce offline loading with:

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

## Design Decisions

- Use exact original text and half-open spans as the central correctness invariant.
- Use two small, distinct chunkers instead of one generic segmentation framework.
- Start with the mandatory lexical method and keep BM25 as the stable default.
- Use standard-library SQLite FTS5 rather than adding a search service.
- Build a complete temporary index and replace the destination atomically.
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
- Campus NFS performance differed greatly from local filesystems. Profiling identified
  SQLite FTS execution as the useful optimization target, while mmap was rejected as
  a riskier filesystem-dependent choice.
- `uv sync` does not provision Qwen weights. Offline evaluation requires the pinned
  snapshot to be cached in advance.
- Qwen/Qwen3-0.6B is intentionally small and CPU-compatible; answers may be incomplete
  when retrieval evidence is weak, even though the prompt requires grounding.
- The operational prompt budget is conservative and does not claim that every host can
  use the model's maximum architectural context.
- Semantic retrieval, hybrid ranking, incremental indexing, persistent query caching,
  and HTTP access are bonus work and are not described as implemented features.

## Resources

- 42 subject: `RAG against the machine`, version 2.0.
- Python `ast`: https://docs.python.org/3/library/ast.html
- SQLite FTS5: https://www.sqlite.org/fts5.html
- SQLite `cache_size`: https://www.sqlite.org/pragma.html#pragma_cache_size
- Pydantic: https://docs.pydantic.dev/
- Python Fire: https://github.com/google/python-fire
- tqdm: https://tqdm.github.io/
- uv: https://docs.astral.sh/uv/
- Qwen/Qwen3-0.6B: https://huggingface.co/Qwen/Qwen3-0.6B
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
