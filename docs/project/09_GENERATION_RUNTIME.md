# Qwen CPU runtime validation — issue #24

## Scope and decision

Validate the runtime only. No `src/` code, retrieval behavior, source loading,
`answer`, `answer_dataset`, or generation interface is implemented here.

Use `Qwen/Qwen3-0.6B` with Transformers 4.57.6 and PyTorch 2.10.0 CPU wheels.
These exact versions are pinned in `pyproject.toml` and resolved in `uv.lock`.
The explicit PyTorch index supplies only torch; other dependencies use PyPI.
No CUDA wheels, Accelerate, server, alternate backend or RAG framework is needed.
The user selected this stack; no alternative-runtime benchmark is claimed.

`.python-version` selects Python 3.10, matching CI and the mypy target while
`requires-python >=3.10` stays unchanged. On the initial Python 3.14.6 environment,
generation worked, but NumPy 2.5.2's type syntax broke mypy's Python 3.10 target.
The reproducible Python 3.10.20 environment resolves NumPy 2.2.6 and passes all
gates without weakening type checks or adding a direct NumPy dependency.
Explicit newer-Python overrides are not claimed to pass the full quality gate.

## Verified environment and storage

- Windows 11 (build 26200), Intel Core i5-12600KF, 10 cores / 16 logical CPUs.
- Physical RAM: 34,193,698,816 bytes; available at initial check:
  22,188,859,392 bytes. Free disk at initial check: 103,122,329,600 bytes.
- CPython 3.10.20; torch 2.10.0+cpu; transformers 4.57.6;
  tokenizers 0.22.2; huggingface-hub 0.36.2; numpy 2.2.6;
  safetensors 0.8.0. CPU float32, four torch threads, evaluation/inference mode.
- Model revision: `c1899de289a04d12100db370d81485cdf75e47ca`.
- `model.safetensors`: 1,503,300,328 bytes. Observed model cache:
  1,519,182,365 bytes. Python 3.10 site-packages: 619,434,273 bytes
  (logical file sizes including the dev environment, not incremental disk use).
- float32 model parameters: 2,384,199,680 bytes; this is NOT process memory.

`uv sync`/`uv sync --locked` install dependencies, not weights. Initial model
acquisition used public HTTPS without login, `trust_remote_code=False`, and an
explicit `models/huggingface` cache (already ignored). Model loading uses the pinned
revision and safetensors. Windows reported unavailable cache symlinks and used
ordinary files; the missing optional hf_xet accelerator fell back to HTTP. Neither
warning blocked execution or justified another dependency/system privilege.

A separate process with `local_files_only=True` successfully loaded and generated
from the populated cache. This verifies the library's cache-only path, not the
availability of internet or preloaded weights in the evaluator. Supply/cache the
pinned snapshot before an offline exam; an absent cache must remain a technical
error, not an abstention. No private evaluator data was used.

## Context and operational budget

- Model `config.max_position_embeddings`: 40,960.
- Real tokenizer `model_max_length`: 131,072. It is finite, but cannot override
  the smaller model capacity; supported limit here is 40,960.
- In this Transformers version, `LARGE_INTEGER` is 10^20. Ignore absent,
  non-positive, non-integer or sentinel tokenizer limits at/above this threshold.
  Use the minimum of model capacity and a valid tokenizer capacity. The probe
  asserts the larger/smaller finite, absent, threshold and 10^30 sentinel cases.
- Start with configurable `budget=2048` and `max_new_tokens=128`.
  Require `0 < max_new_tokens < budget <= supported_limit`, then require
  `complete_prompt_tokens + max_new_tokens <= budget` BEFORE loading weights.
- This is a conservative starting budget, not a claim that a full 2,048-token
  request, let alone 40,960 tokens, fits comfortably on every CPU machine.
  This slice measured a 48-token prompt and a three-token completion only.
- Count the REAL template with `add_generation_prompt=True`,
  `enable_thinking=False`, `tokenize=True`; the probe verifies equality with
  rendering then tokenizing using `add_special_tokens=False` (no double BOS/EOS).
  The empty `<think>...</think>` template prefix is still part of the prompt.
- Probe count: 48 prompt tokens + 128 reserved answer tokens = 176.
  Generation returns only new token IDs, decoded to answer text; Python owns JSON.

No-thinking is the starting decision, not a grounding/quality result. The smoke
uses explicit greedy `do_sample=False` in `generate` kwargs for reproducibility,
with `temperature/top_p/top_k=None` to clear incompatible model sampling defaults.
An intermediate experiment supplying only a new `GenerationConfig` warned that
model defaults (including sampling) were restored; that approach was discarded.
The final kwargs-based run has empty stderr. Do not infer good RAG answer quality
from this one factual fixture; #13 must run its own public-question smoke.

## Fresh execution evidence (2026-09-05)

Initial uncached run on Python 3.14.6 (not the final canonical environment):
config/tokenizer 3.3304s; model download + load 51.4322s; generation 1.1658s;
answer `Paris.`. This is a combined download/load measurement, not isolated
network throughput or a comparable cold/warm performance benchmark.

Final cache-only run on Python 3.10.20, after all sentinel assertions were added:

```json
{
  "exit": 0,
  "process_tree_peak_rss_bytes": 4677201920,
  "sampling_seconds": 0.1,
  "wall_seconds": 58.87569650000023,
  "records": [
    {
      "phase": "environment",
      "python": "3.10.20",
      "torch": "2.10.0+cpu",
      "transformers": "4.57.6",
      "model": "Qwen/Qwen3-0.6B",
      "revision": "c1899de289a04d12100db370d81485cdf75e47ca",
      "device": "cpu",
      "dtype": "float32",
      "threads": 4
    },
    {
      "phase": "prompt",
      "config_limit": 40960,
      "tokenizer_limit": 131072,
      "tokenizer_limit_is_valid": true,
      "supported_limit": 40960,
      "sentinel_threshold": 100000000000000000000,
      "budget": 2048,
      "prompt_tokens": 48,
      "max_new_tokens": 128,
      "reserved_total": 176,
      "rendered_prompt": "<|im_start|>system\nAnswer using only the supplied context.<|im_end|>\n<|im_start|>user\nContext: The capital of France is Paris.\nQuestion: What is the capital of France? Answer in one short sentence.<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n",
      "tokenizer_load_seconds": 0.9020167999997284
    },
    {
      "phase": "loading_model"
    },
    {
      "phase": "loaded",
      "load_seconds": 2.4639271000005465,
      "parameter_bytes": 2384199680
    },
    {
      "phase": "generated",
      "seconds": 1.0021713999994972,
      "generated_tokens": 3,
      "answer": "Paris."
    }
  ],
  "stderr": ""
}
```

The memory figure is a 100ms-sampled peak SUM of RSS for the Windows venv
redirector and descendant Python process, measured externally with psutil. It
includes interpreter/runtime overhead and may double-count shared pages or miss
short peaks. psutil is an agent-side observer, NOT a project dependency. An early
redirector-only measurement was discarded. Wall time includes interpreter imports,
startup and shutdown, unlike the model-load/generation phase timers. Timing varies
with the shared workstation; no performance gate is claimed for generation.

Budget edge runs (same real tokenizer/template and cache):

| Arguments | Exit | Observed result |
|---|---:|---|
| `--budget 176` | 0 | exact reservation boundary accepted, `Paris.` |
| `--budget 175` | 2 | complete prompt plus answer reservation exceeds budget |
| `--budget 40961` | 2 | budget exceeds supported context |
| `--max-new-tokens 0` | 2 | invalid answer reservation |

All rejected runs failed before the `loading_model` phase and without traceback.
`make check`: context, Flake8, mypy (29 files) passed; 81 tests passed in 18.05s
on Python 3.10 after dependency installation. Final PR/CI evidence is recorded
in the PR. These checks do not constitute the #25 clean-checkout rehearsal.

## Reproduce without adding a production entry point

Run `uv sync --locked` from repository root. Save the following disposable probe
as `models/probe_qwen24.py` (ignored), then run:

```text
uv run python models/probe_qwen24.py
uv run python models/probe_qwen24.py --local-files-only
uv run python models/probe_qwen24.py --local-files-only --budget 176
uv run python models/probe_qwen24.py --local-files-only --budget 175
uv run python models/probe_qwen24.py --local-files-only --budget 40961
uv run python models/probe_qwen24.py --local-files-only --max-new-tokens 0
```

The observed session executed the identical probe from `.git/probe_qwen24.py`
using the uv-synchronized `.venv/Scripts/python.exe`. The probe is preserved below
as reproducible evidence, not a second runtime adapter; delete the disposable copy
after the smoke. Cache location, budget and answer reservation are configurable.

```python
"""Run the isolated #24 CPU/token-budget smoke; no RAG integration."""
import argparse
import json
import platform
import time

import torch
import transformers
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
from transformers.tokenization_utils_base import LARGE_INTEGER

parser = argparse.ArgumentParser()
parser.add_argument("--cache-dir", default="models/huggingface")
parser.add_argument("--budget", type=int, default=2048)
parser.add_argument("--max-new-tokens", type=int, default=128)
parser.add_argument("--local-files-only", action="store_true")
args = parser.parse_args()
model_id = "Qwen/Qwen3-0.6B"
revision = "c1899de289a04d12100db370d81485cdf75e47ca"
kwargs = dict(revision=revision, cache_dir=args.cache_dir,
              local_files_only=args.local_files_only, trust_remote_code=False)
torch.set_num_threads(4)

def report(phase, **values):
    """Flush phase evidence for the external process-memory monitor."""
    print(json.dumps(dict(phase=phase, **values)), flush=True)

report("environment", python=platform.python_version(), torch=torch.__version__,
       transformers=transformers.__version__, model=model_id, revision=revision,
       device="cpu", dtype="float32", threads=torch.get_num_threads())
started = time.perf_counter()
config = AutoConfig.from_pretrained(model_id, **kwargs)
tokenizer = AutoTokenizer.from_pretrained(model_id, **kwargs)
model_limit = config.max_position_embeddings
tokenizer_limit = tokenizer.model_max_length
def supported_context(model_capacity: int, tokenizer_capacity: object) -> int:
    """Ignore unknown/sentinel tokenizer capacities; never raise model capacity."""
    if isinstance(tokenizer_capacity, int) and 0 < tokenizer_capacity < LARGE_INTEGER:
        return min(model_capacity, tokenizer_capacity)
    return model_capacity

assert supported_context(40960, 131072) == 40960
assert supported_context(40960, 8192) == 8192
assert supported_context(40960, LARGE_INTEGER) == 40960
assert supported_context(40960, 10**30) == 40960
assert supported_context(40960, None) == 40960
valid_tokenizer_limit = (
    isinstance(tokenizer_limit, int) and 0 < tokenizer_limit < LARGE_INTEGER
)
supported = supported_context(model_limit, tokenizer_limit)
if not 0 < args.max_new_tokens < args.budget <= supported:
    parser.error("require 0 < max_new_tokens < budget <= supported context")
messages = [
    {"role": "system", "content": "Answer using only the supplied context."},
    {"role": "user", "content": "Context: The capital of France is Paris.\n"
     "Question: What is the capital of France? Answer in one short sentence."},
]
rendered = tokenizer.apply_chat_template(
    messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
)
inputs = tokenizer.apply_chat_template(
    messages, tokenize=True, add_generation_prompt=True, enable_thinking=False,
    return_dict=True, return_tensors="pt"
)
ids = inputs["input_ids"][0].tolist()
assert ids == tokenizer(rendered, add_special_tokens=False)["input_ids"]
assert "<think>\n\n</think>" in rendered
prompt_tokens = len(ids)
if prompt_tokens + args.max_new_tokens > args.budget:
    parser.error("complete prompt plus answer reservation exceeds budget")
report("prompt", config_limit=model_limit, tokenizer_limit=tokenizer_limit,
       tokenizer_limit_is_valid=valid_tokenizer_limit, supported_limit=supported,
       sentinel_threshold=LARGE_INTEGER, budget=args.budget,
       prompt_tokens=prompt_tokens, max_new_tokens=args.max_new_tokens,
       reserved_total=prompt_tokens + args.max_new_tokens,
       rendered_prompt=rendered, tokenizer_load_seconds=time.perf_counter()-started)
started = time.perf_counter()
report("loading_model")
model = AutoModelForCausalLM.from_pretrained(
    model_id, dtype=torch.float32, **kwargs
).to("cpu").eval()
report("loaded", load_seconds=time.perf_counter()-started,
       parameter_bytes=sum(p.numel()*p.element_size() for p in model.parameters()))
started = time.perf_counter()
with torch.inference_mode():
    output = model.generate(
        **inputs, max_new_tokens=args.max_new_tokens, do_sample=False,
        temperature=None, top_p=None, top_k=None,
        pad_token_id=tokenizer.eos_token_id,
    )
answer_ids = output[0, prompt_tokens:]
answer = tokenizer.decode(answer_ids, skip_special_tokens=True)
assert answer.strip() and "<think>" not in answer
assert len(ids) + len(answer_ids) <= args.budget
report("generated", seconds=time.perf_counter()-started,
       generated_tokens=len(answer_ids), answer=answer)

```

## Handoff boundaries — not implemented in #24

After manual merge, #13 owns the replaceable generation adapter and minimal fakeable
interface, plus the shared `MinimalSearchResults -> MinimalAnswer` use case.
Read SQLite text by exact path AND both offsets in input order; never load all
chunks, re-run retrieval, or substitute missing sources. Keep ranked fragments
complete, re-count the full template for each candidate, preserve retrieved sources
and track included sources separately. Empty evidence abstains without model load;
technical failures remain errors. The CLI searches once, delegates, displays
answer/sources and writes the Pydantic `StudentSearchResultsAndAnswer` wrapper.

Only after its own manual merge, #14 reads `StudentSearchResults`, reuses that
path sequentially with tqdm, preserves IDs/questions/order/sources/k, loads the
model lazily at most once and reuses/closes one SQLite connection. Atomic output
replacement must preserve prior results on any failure. No new retrieval or
model-authored JSON. Both future issues keep configurable paths/index_directory
and need their own tests, real Qwen smoke, documentation and PR.

## Sources

- https://huggingface.co/Qwen/Qwen3-0.6B
- https://huggingface.co/Qwen/Qwen3-0.6B/blob/c1899de289a04d12100db370d81485cdf75e47ca/config.json
- https://huggingface.co/Qwen/Qwen3-0.6B/blob/c1899de289a04d12100db370d81485cdf75e47ca/tokenizer_config.json
- https://docs.astral.sh/uv/guides/integration/pytorch/
- https://pypi.org/project/transformers/4.57.6/
- https://pypi.org/project/torch/2.10.0/
