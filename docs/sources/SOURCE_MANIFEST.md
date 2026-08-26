# Supplied source inventory

The harness was prepared against the following user-supplied materials. They
remain immutable local inputs under ignored `docs/extra/`; they are not
submission content and must not be committed.

| Material | Role |
|---|---|
| `rag-subject.pdf` | 42 subject v2.0; mandatory requirements and README/bonus/submission rules |
| `README (8).md` | Moulinette usage, schema examples, recall thresholds |
| `exams.zip` | Corrector guide plus retrieval/answer/edge-case scripts |
| `datasets_public.zip` | Public Answered/Unanswered docs/code development datasets |
| `datasets_private.zip` | Private evaluator/holdout datasets; do not tune against answered ground truth |
| `vllm-0.10.1 (2).zip` | Corpus to index under `data/raw/vllm-0.10.1/` |
| `moulinette.zip` | Corrector binaries; student implementation must not import/call moulinette |

## Observed dataset packaging

- Public docs: 100 questions.
- Public code: 99 questions.
- Private docs: 100 questions.
- Private code: 100 questions.
- Public archive is packaged under `datasets_public/public/...`; `scripts/bootstrap-data.sh` flattens this to the subject-compatible `data/datasets/...` layout.

## Source protection
Do not edit supplied data/corpus to improve scores. Any derived fixtures belong under `tests/fixtures/` and should state provenance/assumptions.
