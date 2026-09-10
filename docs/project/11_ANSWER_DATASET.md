# Sequential dataset answers — issue #14

## Contract

`answer_dataset` validates one configurable `StudentSearchResults` JSON file and
processes its existing `search_results` in received order. It does not call
retrieval. Every output item preserves the input `question_id`, `question`, and
`retrieved_sources`, and the wrapper preserves `k`.

Each item delegates to the shared `answer_search_result` use case from issue #13.
One lazy `QwenGenerator` instance is reused for the complete batch. The SQLite
connection is opened only when the first sourced question is encountered, reused
for every exact source hydration, and closed after the loop. Questions without
sources take the fixed abstention path without source I/O or tokenizer/model work.
Processing is deliberately sequential; no concurrency, cache, backend registry,
or retrieval path was added.

## Progress and output safety

The CLI enables the existing Qwen tokenizer/model/generation tqdm phases and adds
one `Answering dataset` bar around the ordered loop. tqdm writes to stderr. The
command's stdout contains only Fire's final saved-path message, and progress never
enters the JSON. The reusable Qwen adapter remains silent by default.

The output path is `<save_directory>/<input filename>`. Python constructs only a
`StudentSearchResultsAndAnswer` Pydantic model, serializes it to a closed sibling
temporary file, and atomically replaces the destination. Input, source, index,
budget, or model failures remove the temporary file and leave a prior destination
unchanged.

Example:

```text
uv run python -m src answer_dataset \
  --student_search_results_path data/output/search_results/questions.json \
  --save_directory data/output/search_results_and_answer \
  --index_directory data/processed \
  --model_cache_directory models/huggingface \
  --token_budget 2048 \
  --max_new_tokens 128 \
  --local_files_only=True
```

## TDD and fresh validation

Initial focused RED:

```text
uv run pytest tests/test_answer_dataset.py -q
10 failed: the placeholder rejected the new options or returned
'answer_dataset' is not implemented yet.
```

Final local checks:

```text
uv sync --locked
Resolved 51 packages; checked 44 packages.

uv run pytest tests/test_answer_dataset.py tests/test_answer.py -q
40 passed.

make check
Context validation passed.
Flake8 passed.
Mypy passed over 34 source files.
121 tests passed in 31.68s.

make lint-strict
Flake8 passed.
Strict mypy passed over 34 source files.

git diff --check
passed.
```

Acceptance coverage pins exact identity/order/source/`k` preservation, no
retrieval, sequential calls, one generator construction, one closed SQLite
connection, source-free abstention without SQLite/model work, stderr-only batch
progress, Pydantic output, predictable naming, atomic replacement, preservation
of prior bytes after an intermediate model failure, stale sources, and
traceback-free missing/malformed input, missing index, invalid budget, and missing
model cache failures.

The single final Ponytail-full review retained the stdlib-only design and found no
new port, factory, concurrency, cache, or retrieval work to remove. It identified
one test-contract gap: direct destination writing could survive the original
failure tests. One focused replacement-failure regression now requires the sibling
temporary-file/`Path.replace` path and preservation of prior bytes; no production
code was added for the finding.

## Public cache-only Qwen smoke

No private data was used. A local public vLLM v0.10.1 corpus was indexed and two
handwritten public-source questions were retrieved at `k=1`, then the resulting
`StudentSearchResults` file was passed unchanged to `answer_dataset`.

```text
index: 1,969 documents / 17,134 chunks / 5.9469s
search_dataset: 2 questions / 0.6742s
answer_dataset: 2 questions / 18.4644s
```

All commands exited 0. Index/search/batch and Qwen phase progress appeared on
stderr. The answer file revalidated as `StudentSearchResultsAndAnswer`; `k`, IDs,
questions, order, and source lists exactly matched the prior search file. The
cache was pre-populated and `local_files_only=True`.

Observed answers and top sources:

```text
public-volta -> "Volta refers to SM 7.0."
data/raw/vllm-0.10.1/docs/features/quantization/supported_hardware.md [2059:2698]

public-serving -> "You cannot answer from it."
data/raw/vllm-0.10.1/examples/offline_inference/audio_language.py [0:925]
```

The second BM25 top-1 source was insufficient, and Qwen abstained in its own
wording. This tiny run verifies batch integration and resource reuse contracts in
tests; it is not an answer-quality benchmark, a cold model-download measurement,
a private holdout result, or proof that evaluator model weights are provisioned.
Generation timing varies with the shared CPU host.
