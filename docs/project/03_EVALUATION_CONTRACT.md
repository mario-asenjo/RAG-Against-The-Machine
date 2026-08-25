# Evaluation contract

This document distills the provided correction scripts into engineering gates.

## Automated retrieval flow
The corrector runs the student project from its root and uses the default module name `src` unless overridden.

1. `uv sync`.
2. Index once:

```text
uv run python -m src index --max_chunk_size 2000
```

3. Run `search_dataset` on private docs questions (`k=10`).
4. Run `search_dataset` on private code questions (`k=10`).
5. Combined warm retrieval time for 200 questions must be <= 90s.
6. Moulinette validates result files with `max_context_length=2000`.
7. Docs Recall@5 must be >= 0.80.
8. Code Recall@5 must be >= 0.50.

Indexing must finish <= 300s.

## Recall matching
A ground-truth source counts as found when a retrieved result:

- has the exact same `file_path`; and
- overlaps the ground-truth character range enough to pass the evaluator IoU threshold (> 0.05 in the supplied corrector guide/script context).

Implications:

- Exact character boundaries are not required, but correct region and exact file are essential.
- Larger chunks can improve overlap recall but are capped at 2000 chars and may add ranking noise.
- Path-prefix mistakes cause zero credit even with perfect semantic content.

## Edge-case exam
The supplied edge-case script invokes:

```text
search "" --k 10
search "asdfghjkl zxcvbnm qwertyuiop" --k 10
answer "What is vLLM?" --k 0
search_dataset --dataset_path /nonexistent/dataset.json --k 10
```

Non-zero exit codes or clear error messages are acceptable. An unhandled Python traceback is not.

## Answer exam
The corrector first identifies questions whose sources were validly retrieved, then tests three single-query answers. At least 2/3 should be satisfactory. Retrieval quality and grounding are prioritized because Qwen/Qwen3-0.6B has known reasoning limits.

## Forbidden coupling
The subject explicitly says the student solution must never import or call moulinette. Local `evaluate` is the student's own implementation for iteration only.

## Holdout policy for development
The provided private data mirrors evaluator use. This harness treats it as blind. Development uses public datasets; private data is a final confidence check, not a hyperparameter search set.
