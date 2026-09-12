# Public answer_dataset profiling — issue #41

## Purpose

This slice profiles public `answer_dataset` generation before optimizing. It does not inspect private data and does not change answer length, retrieval, caching, concurrency, or model backend.

## Fixed input

- Branch: `perf/issue-41-answer-dataset-profile` from merged PR #40.
- Public input: `data/output/search_results/UnansweredQuestions/dataset_code_public.json`.
- Subset: first 10 entries with non-empty `retrieved_sources` from that public search-results file.
- Index: `data/processed/lexical_index.sqlite3`.
- Model cache: `models/huggingface`, local files only.
- Runtime budget: `token_budget=2048`, `max_new_tokens=128`.
- Raw generated profiling JSON: `data/output/profiling/issue41/` (gitignored).

## Command pattern

```text
uv run python scripts/profile_answer_dataset.py \
  data/output/search_results/UnansweredQuestions/dataset_code_public.json \
  --limit 10 \
  --thread-setting <4|8|10|default|16> \
  --output-json data/output/profiling/issue41/profile-thread-<setting>.json
```

The profiler wraps the existing `answer_search_result`, `QwenGenerator`, and exact SQLite source loader. It measures source hydration, supported-context lookup, prompt-fitting tokenization, generation, total question time, prompt tokens, generated tokens, retrieved source count, and included source count.

For thread experiments only, the script bypasses the adapter's hard-coded `torch.set_num_threads(4)` after setting the requested process thread count. Production behavior is unchanged by the script.

## Results

| threads | effective | questions | total s | avg s/q | generation s | gen share | fit/tokenize s | hydrate s | generated tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 4 | 10 | 370.853 | 37.085 | 357.619 | 0.964 | 0.223 | 5.182 | 398 |
| 8 | 8 | 10 | 379.500 | 37.950 | 345.370 | 0.910 | 0.220 | 4.679 | 398 |
| 10 | 10 | 10 | 316.973 | 31.697 | 305.794 | 0.965 | 0.204 | 4.410 | 398 |
| default | 10 | 10 | 331.957 | 33.196 | 320.679 | 0.966 | 0.199 | 4.710 | 398 |
| 16 | 16 | 10 | 320.808 | 32.081 | 293.393 | 0.914 | 0.198 | 4.558 | 398 |

Common subset shape:

- average retrieved sources/question: 10.0;
- average included sources/question: 3.9;
- average maximum prompt tokens/question: 2022.0;
- generated tokens across the 10-question subset: 398.

## Findings

- Generation dominates wall time in every run: about 91-97% of total time.
- Source hydration is small: roughly 4.4-5.2 seconds total for 10 questions.
- Prompt fitting/tokenization is negligible: roughly 0.2 seconds total for 10 questions.
- The current production hard-coded 4-thread setting is not best on this host.
- 10 threads produced the best total runtime in this run: 316.973s, about 14.5% faster than 4 threads.
- 16 threads had the fastest summed generation time, but total runtime was slightly slower than 10 threads because non-generation overhead/noise increased.
- PyTorch default on this host was 10 effective threads and was close to explicit 10, but explicit 10 was faster in this run.

## Strategy

Do not optimize source hydration, prompt fitting, retrieval, cache, or answer length from this evidence. They are not the bottleneck.

Smallest useful next runtime change, if we choose to implement one, is to remove or parameterize the hard-coded `torch.set_num_threads(4)` in `QwenGenerator` and make the CLI expose a thread setting with a safe default. The measured candidate for this host is 10 threads. A safer evaluator-facing default may be PyTorch default/no override, because the evaluator CPU topology is unknown.

Do not implement StaticCache yet. This run does not isolate KV-cache reuse benefits, and generation length/quality must stay unchanged.
