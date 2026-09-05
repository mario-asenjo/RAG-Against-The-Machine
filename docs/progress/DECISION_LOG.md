# Decision log

## D-0001 — Mandatory-first, lexical-first
**Status:** accepted for bootstrap.

The harness will not begin with embeddings/hybrid retrieval. The subject requires a lexical method and only grades bonuses after mandatory validation. Establish a lexical public baseline first.

## D-0002 — Private datasets are holdout
**Status:** accepted for harness workflow.

Although private datasets were supplied with the project materials, their answered ground truth will not be inspected to tune retrieval. This keeps evaluator evidence meaningful and reduces overfitting risk.

## D-0003 — AGENTS is always-on; Hermes skills are optional/on-demand
**Status:** accepted.

Project-specific hard constraints live in root `AGENTS.md`. The optional project skill is installed into Hermes's skill catalog by setup scripts so it is loaded on demand rather than permanently bloating context.

## D-0004 — One GitHub Project, issue-first delivery
**Status:** accepted.

Every non-trivial implementation slice is issue-backed and synchronized to the existing associated Project when scopes permit. No duplicate board is created to work around missing token scope.

## D-0005 — Modular monolith with hexagonal seams
**Status:** accepted for #2.

The implementation uses a small modular monolith, not ceremonial hexagonal architecture. `domain` and `application` stay independent from `adapters` and `infrastructure`; ports are added only when a real use case needs replaceable implementations. This keeps mandatory delivery small while allowing later semantic retrieval, hybrid retrieval, incremental indexing, caching, and HTTP API bonuses without moving CLI-owned business logic.

## D-0006 — SQLite FTS5 BM25 and the first real application port
**Status:** accepted for #7.

The first persisted lexical baseline uses stdlib `sqlite3` with FTS5 and its native BM25 ranking data. This avoids a new dependency, persists exact chunk metadata beside warm-query retrieval data, and supports atomic full refreshes. The indexing use case now depends on a minimal structural `Chunker` Protocol because Python and text implementations are both real and interchangeable; explicit suffix wiring remains in the CLI composition root, with no factory or registry framework. The evaluator Python build must include FTS5; fixture tests and CI exercise that requirement directly.

## D-0007 — Subject models own evaluator-facing JSON
**Status:** accepted for #9.

Search inputs are validated as `RagDataset`, and every search output is built as
`StudentSearchResults` containing `MinimalSearchResults` before serialization.
The single-query command uses the subject's default UUID behavior and wraps its
one result in the same output contract. Ad hoc dictionaries are not output
boundaries; future answer stages must follow their corresponding subject models.

## D-0008 — Recall@k is macro source recall, not question hit rate
**Status:** accepted for #11.

For each evaluable question, Recall@k is the proportion of its ground-truth
sources matched in the top-k by exact path and half-open span IoU strictly above
0.05. Each expected source contributes at most once, and dataset Recall@k is
the macro-average of per-question recalls. Questions without ground-truth
sources are excluded; missing student results contribute zero. This deliberately
differs from HitRate@k, micro-recall, and duplicate-sensitive counting.

## D-0009 — Isolated Qwen CPU runtime and bounded context
**Status:** accepted for #24; integration remains #13/#14.

Use Qwen/Qwen3-0.6B with pinned Transformers 4.57.6 and torch 2.10.0 CPU
wheels. Pin the uv interpreter to Python 3.10 to align dependency resolution
with CI/mypy; the initial Python 3.14/NumPy 2.5 type incompatibility is documented,
not hidden by weaker checks. Use CPU float32 and `enable_thinking=False` as the
measured starting point. Full provenance, runnable probe and limitations live in
`docs/project/09_GENERATION_RUNTIME.md`.

The model capacity (40,960) bounds the tokenizer's advertised 131,072. Ignore
sentinel limits and default to a configurable 2,048 total-token operational budget,
including a 128-token answer reservation. Count the real complete chat template,
including generation/special tokens, before loading/generating. Only short-prompt
memory is measured; maximum architectural context is not a hardware guarantee.

Keep runtime details inside the future replaceable adapter; use only the minimal
fakeable interface needed by #13. Exact SQLite source lookup, complete ranked
fragments, source preservation, lazy abstention and Python-owned JSON remain the
approved #13/#14 plan, not delivered functionality here. No extra backend/framework.

Q4 is resolved for this measured host. Q5 remains open for evaluator network/cache:
local-only reuse works after explicit public download, but evaluator access is not
known. Weights/cache stay ignored and must be provisioned before offline execution.
