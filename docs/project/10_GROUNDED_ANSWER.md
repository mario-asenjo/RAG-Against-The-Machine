# Grounded single-query answer — issue #13

## Contract

`answer` performs exactly one existing BM25 search, hydrates each returned source
from SQLite by exact `(file_path, first_character_index, last_character_index)`,
and passes a ranked prefix of complete chunks to the generator. It never reloads
the corpus, retrieves again, scans all chunks, substitutes a nearby span, or asks
the model to build evaluator JSON.

The application layer depends only on the existing Pydantic contracts, a source
loader callable, and the minimal `TextGenerator` Protocol. The Protocol exposes
only the supported context limit, complete-template token count, and answer-text
generation. Qwen/Transformers details remain in `infrastructure/generation.py`.

`AnswerGeneration` carries the Pydantic `MinimalAnswer` and the exact sources
included in the prompt. `MinimalAnswer.retrieved_sources` always preserves the
full ranked retrieval result, even when the operational budget admits only a
prefix. The included-source tuple is internal and is not added to evaluator JSON.

## Exact hydration and budgeting

SQLite executes a parameterized exact three-field query for every source in
received order. Zero or multiple rows are errors. All sources are validated
before prompt selection, so an excluded-but-stale source still cannot be silently
ignored.

The generator owns one no-thinking chat template for both counting and generation.
The use case validates positive budget/reservation values, verifies the configured
budget does not exceed the adapter's model/tokenizer limit, and counts the base
instructions plus question before source I/O. It appends complete labeled chunks
in ranking order and stops at the first chunk that would violate:

```text
complete_prompt_tokens + max_new_tokens <= token_budget
```

No fragment is truncated. If the base prompt overflows, or retrieved evidence
exists but the first complete chunk cannot fit, the command returns a technical
budget error before loading model weights. Defaults follow D-0009: 2,048 total
and 128 reserved output tokens.

## Empty evidence and failures

`k=0` and successful searches with no matches produce the explicit answer:

```text
I cannot answer from the retrieved sources.
```

That path neither hydrates sources nor loads Qwen tokenizer/model assets; a CLI
regression runs with a deliberately absent local-only model cache. Empty queries,
negative/invalid budgets, missing/corrupt indexes, stale exact source identities,
missing model assets, empty model output, and model generation errors remain
non-abstention technical failures. Known boundary errors become Fire errors with
non-zero status and no Python traceback. Output is written only after successful
answer construction, so failed generation does not create the requested file.

## Output

The CLI prints the answer and every retrieved source location for humans, then
writes one `StudentSearchResultsAndAnswer(search_results=[MinimalAnswer], k=k)`
using Pydantic. `save_path`, `index_directory`, `model_cache_directory`,
`token_budget`, `max_new_tokens`, and offline-cache mode are configurable.

Example:

```text
uv run python -m src answer "What does Volta refer to in vLLM hardware documentation?" --k 1 --index_directory data/processed --save_path data/output/issue13/public-answer.json --model_cache_directory models/huggingface --token_budget 2048 --max_new_tokens 128 --local_files_only=True
```

## Fresh public-corpus smoke

The smoke used a fresh public checkout of vLLM tag `v0.10.1` at commit
`aab549870df50edf0512f0a59b574f692f546465`, not private evaluator data. The
ignored corpus was indexed locally: 1,969 accepted documents, 17,360 chunks,
24.5199 seconds. This checkout-generated index is smoke evidence, not a replacement
for the recorded supplied-corpus retrieval baseline or a new recall benchmark.

Exact command argv:

```json
[
  "uv",
  "run",
  "python",
  "-m",
  "src",
  "answer",
  "What does Volta refer to in vLLM hardware documentation?",
  "--k=1",
  "--index_directory=data/processed",
  "--save_path=data/output/issue13/public-answer.json",
  "--model_cache_directory=models/huggingface",
  "--token_budget=2048",
  "--max_new_tokens=128",
  "--local_files_only=True"
]
```

Observed result:

```text
exit: 0
wall_seconds: 26.5680
sampled_process_tree_peak_rss_bytes: 4660158464
stdout:
Answer: Volta refers to SM 7.0 in vLLM hardware documentation.
Sources:
data/raw/vllm-0.10.1/docs/features/quantization/supported_hardware.md [2083:2730]
Saved student_search_results_and_answer to data/output/issue13/public-answer.json
stderr: <empty>
```

The Pydantic file contained one UUID question, the exact question, `k=1`, answer
`Volta refers to SM 7.0 in vLLM hardware documentation.`, and the unchanged source:

```text
data/raw/vllm-0.10.1/docs/features/quantization/supported_hardware.md [2083:2730]
```

Independent verification against the original file using newline-preserving
reading found the 647-character SQLite text equal to the exact half-open slice.
The real Qwen template measured 66 tokens without context and 265 with the full
source; 265 + 128 = 393, within the 2,048 budget and below the 40,960 supported
context limit. The model cache was already populated and `local_files_only=True`;
wall time includes uv/Python startup, search, tokenizer/model load, generation,
validation, output and shutdown. The 100ms-sampled process-tree RSS peak
(4,660,158,464 bytes) has the same sampling/double-count caveats as #24.

This one public factual smoke demonstrates the complete RAG path and grounding;
it is not an answer-quality benchmark, private holdout result, full-context memory
claim, or proof that evaluator model assets are pre-provisioned.

## Deferred to #14

No dataset input, sequential loop, tqdm generation progress, shared SQLite batch
connection, lazy model reuse assertion, or atomic batch replacement is implemented
here. #14 must reuse this application path only after #13 is manually merged.
