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

## D-0010 — Exact-source, complete-prefix grounded answers
**Status:** accepted for #13; batch orchestration remains #14.

Single-query `answer` performs one existing lexical search, then resolves every
ranked source through parameterized SQLite equality on path and both half-open
offsets. Missing or duplicate identities are errors; no corpus reload, second
retrieval, all-chunk scan, nearby substitution, or partial fragment is allowed.

The application use case accepts the Pydantic `MinimalSearchResults`, a direct
source-loader callable, and one minimal `TextGenerator` Protocol. No source port,
factory, backend registry or dependency container is added. The Qwen adapter owns
one real no-thinking template for token counting and generation and loads tokenizer
then model lazily. A frozen local result tracks included sources while the
`MinimalAnswer` preserves every retrieved source unchanged.

Use a ranked prefix of complete labeled chunks under
`prompt_tokens + max_new_tokens <= token_budget`. Base-prompt or first-fragment
overflow is a technical budget error. Empty retrieval is the explicit fixed
abstention and performs no source/model work. Python/Pydantic, never the model,
owns `StudentSearchResultsAndAnswer` serialization. Single-output writing is kept
direct; #14 owns atomic batch replacement and shared batch resources.

## D-0011 — Sequential batch reuse and atomic answer output
**Status:** accepted for #14.

`answer_dataset` consumes validated prior `StudentSearchResults`; it never runs
retrieval. Process questions in order through `answer_search_result`, preserving
the exact wrapper `k` and each item's ID, question, order, and retrieved sources.
Reuse one lazy Qwen adapter and one lazily opened/closed SQLite connection for the
batch. Empty-source items retain the shared fixed abstention without source or
model work.

The CLI owns one stderr tqdm batch bar and enables existing Qwen phase bars while
the reusable generator remains quiet by default. Serialize only the Pydantic
`StudentSearchResultsAndAnswer` to a closed sibling temporary file, then atomically
replace `<save_directory>/<input filename>`. Any failure leaves an existing output
unchanged. No concurrency, retrieval, cache, alternate backend, or new framework.

## D-0012 — Mandatory readiness before bonuses; incremental first
**Status:** accepted from the post-#40 roadmap review.

Do not use answer speed pressure to reduce `max_new_tokens` or shorten answers.
Profile `answer_dataset` on a fixed public subset and benchmark CPU thread counts
before optimizing. Finish #25 clean-checkout rehearsal and #15 documentation /
defense readiness before any bonus implementation.

Once the mandatory gate is green, implement bonuses in dependency order:
#19 incremental indexing, #17 semantic retrieval, #18 hybrid retrieval,
#20 persistent query cache, then #21 local HTTP API. Incremental indexing comes
first because file manifests, content hashes, transactional partial replacement,
stale cleanup, and persistent `index_revision` are prerequisites for efficient
semantic updates and correct persistent cache invalidation. Caching generated
answers remains out of scope.

## D-0013 — Authorized private holdout is evidence, never a tuning source
**Status:** accepted for #16 during #25.

Mario explicitly authorized a blind private retrieval rehearsal. Record only
aggregate timing, Recall, and pass/fail; do not inspect or publish private answered
JSON or ground-truth source spans. The initial WSL run passed Docs Recall@5 at
0.800 and Code Recall@5 at 0.510 but had invalid timing. Mario later ran the
unchanged frozen configuration through the supplied correction script on campus,
reproducing the same aggregate Recall while measuring 92s retrieval. No parameter
change occurred between runs and private labels must not be used for tuning or
evaluated again; subsequent #45 work uses public or unanswered inputs only.

## D-0014 — Mandatory uncached retrieval before bonus cache
**Status:** accepted and campus-confirmed by #45.

Campus retrieval took 92s for 200 distinct questions, failing the mandatory 90s
gate by 2s while Recall remained passing. Do not use #20's persistent repeated-query
cache as the remedy: the evaluator executes distinct queries in two fresh CLI
processes, so useful cache hits are not expected. Profile the existing SQLite/NFS
path first and compare one change at a time. Perform optimization on repeatable
local public runs, retaining only an output-identical option with a stable >=15%
gain across at least three runs. Use at most one later campus confirmation on
unanswered inputs; preserve BM25 ranking, exact spans, and public Recall. Query-result
cache, concurrency, semantic retrieval, and ranking changes remain out of scope until the
mandatory gate is green.

The one post-merge confirmation at `6ff741a` processed 200 private unanswered
questions on campus NFS in 8.193 seconds without opening labels or invoking
Moulinette. The mandatory timing gate is green; no repeated campus tuning is
authorized.

## D-0015 — Expand the batch SQLite page cache, not query-result cache
**Status:** accepted and confirmed on campus NFS for #45.

Public phase profiling attributed 99.92% of local retrieval time to FTS execution.
The 35.230 MiB index used SQLite's approximately 2 MiB default page cache. Setting
`PRAGMA cache_size=-65536` on the existing batch connection improved the median
two-process public CLI workload from 7.987s to 5.445s across three measured pairs
(31.83%) while preserving byte-identical output and all public recall values.

Keep this single per-connection 64 MiB page-cache statement. Do not use immutable
mode: it did not improve the local probe. Do not retain mmap despite its small extra
local gain because the target is campus NFS and the filesystem-dependent mechanism
adds risk without needed margin. This is page reuse across distinct FTS queries, not
#20's persistent repeated-query cache; it adds no cache entries or invalidation model.
The home Windows result did not itself close the mandatory timing gate. The one
allowed post-merge campus confirmation later passed at 8.193 seconds combined.
Because that observation used another host and an uncommitted runner modification,
it proves compliance but does not attribute the full cross-run improvement to the
page-cache statement.

## D-0016 — Freeze the mandatory baseline before bonuses
**Status:** accepted; mandatory baseline frozen at `7c411ef`.

The mandatory baseline is Python/text exact chunking at maximum 2,000 characters,
SQLite FTS5 BM25 with the batch-local 64 MiB page cache, exact Pydantic outputs,
and Qwen/Qwen3-0.6B revision `c1899de289a04d12100db370d81485cdf75e47ca`
with 2,048/128 token defaults. The final clean public rehearsal at `010e568`
reproduced all Recall values, exercised every CLI command and kept private data
unused. Merged PR #49 commit `7c411ef` is the known-good mandatory baseline.

Bonus work starts with #19 and must preserve this lexical path, schemas, paths,
offsets, chunk limit, CLI behavior, public Recall and mandatory timing. A bonus may
add an explicit mode or lifecycle capability, but it must not silently redefine
the mandatory default or use private labels for development.

## D-0017 — Incremental lexical lifecycle uses content identity and copy-update
**Status:** accepted for #19.

Full rebuild remains the default and `--incremental=True` is explicit. Schema v2
persists exact-path SHA-256 file identities and a monotonic `index_revision`; mtime is
not a correctness signal. An unchanged corpus is a byte-stable no-op. Changed updates
copy the live SQLite artifact beside itself, mutate and validate the copy in one
transaction, then atomically replace the live index. Any failure leaves the prior live
artifact intact, while incompatible lifecycle state visibly falls back to full rebuild.

Canonical `rank_order`, derived from path and source spans, replaces mutable SQLite row
ID as the BM25 tie-break. This preserves exact equivalence with a clean full rebuild
without renumbering FTS row IDs. Rename remains delete plus add; watchers, concurrency,
migrations, semantic data and persistent query caching remain outside #19.

## D-0018 — Semantic is an atomic projection over canonical SQLite chunks
**Status:** accepted for #17.

BM25 and full lexical indexing remain the mandatory default. Explicit semantic mode
uses pinned `sentence-transformers/all-MiniLM-L6-v2` through existing torch and
Transformers CPU dependencies, with attention-mask mean pooling, 256-token truncation,
float32 output and L2 normalization. No sentence-transformers dependency, vector
database, service, hybrid fusion, or second chunk/change lifecycle is added.

`files + chunks` remain canonical, `chunks_fts` is the lexical projection, and one
atomic `semantic_index.pt` is the semantic projection. It stores only normalized
embeddings, exact ordered chunk identities, and validated model/count/source-revision
metadata. Incremental semantic updates consume #19's existing plan, invalidate complete
changed files, reuse unchanged-file rows and embed only new chunks. Missing, stale or
incompatible semantic state rebuilds from SQLite; stale revision/identity blocks search.

Public standalone MiniLM Recall is lower than BM25 for docs and code, and the measured
optional full build took 379.690s on this host. Semantic therefore remains explicit and
does not alter mandatory defaults; #18 may evaluate hybrid fusion separately.

## D-0019 — Hybrid uses fixed equal-weight reciprocal rank fusion
**Status:** accepted for #18.

Hybrid mode reuses the existing lexical and semantic ranked top-`k` lists and combines
them with reciprocal rank fusion using equal weights and fixed rank constant 60. Exact
path plus half-open offsets is the deduplication identity; overlapping but different
spans remain distinct. Final score ties use exact identity order. No raw BM25/cosine
score calibration, learned/manual weights, reranker, new index or persisted artifact is
introduced.

`search` and `search_dataset` expose explicit `--hybrid=True`; default remains lexical,
and semantic plus hybrid flags are mutually exclusive. Public evidence improved only
Code Recall@10 (0.667 to 0.707) while reducing other BM25 cutoffs. Hybrid therefore
remains experimental and explicit. Probes of rank constants and deeper candidate pools
did not justify configuration or further complexity.

## D-0020 — Cache exact retrieval results, never generated answers
**Status:** accepted for #20.

Persistent caching is explicit (`--cache=True`) and stores only ordered exact
`MinimalSource` lists in one lazy SQLite `query_cache` table. The primary key is cache
schema version, canonical `index_revision`, deterministic retriever signature, SHA-256 of
the exact UTF-8 query, and `k`. Signatures cover lexical algorithm version, semantic
model/revision/max-length/pooling/cosine behavior, and hybrid RRF parameters plus child
signatures. Default uncached behavior and ranking remain unchanged.

Validate cached JSON with Pydantic and every identity against canonical `chunks` before
returning it. Incremental revision changes create misses while preserving historical rows;
full rebuild replaces the database. Errors are not cached. No TTL, eviction framework,
query equivalence, second database, service, or generated-answer cache is introduced.

`answer --cache=True` may reuse only its lexical retrieval result; source hydration,
prompt fitting, and Qwen generation still execute. `answer_dataset` remains unchanged
because it consumes prior search output and performs no retrieval. Public no-cache/miss /
hit outputs and Recall were identical across lexical, semantic and hybrid modes; measured
misses confirmed that this bonus is not a substitute for first-seen evaluator performance.
