# Source of truth

## Priority

1. `rag-subject.pdf` — 42 subject, version 2.0.
2. `exams/exam_scripts_instructions.md` and `exams/scripts/*.sh` — provided correction behavior that concretely exercises the subject.
3. Moulinette README/binary behavior — output validation and recall contract.
4. Public datasets — development questions and public ground truth.
5. vLLM 0.10.1 corpus — exact indexed source material.
6. Private datasets — holdout evaluator data; not a tuning source.

## Immutability
Treat supplied subject, exam scripts, public datasets, private datasets, and vLLM corpus as immutable inputs. Never edit them to make the implementation pass.

## Data policy
Public AnsweredQuestions are valid development ground truth for measuring and debugging retrieval. Private AnsweredQuestions are intentionally held out by this harness: do not inspect their source labels/answers to tune the system. A final blind evaluator rehearsal may use them only when explicitly authorized.

## Path fidelity
The grader compares `file_path` verbatim. The canonical corpus prefix shown by subject/datasets is:

```text
data/raw/vllm-0.10.1/...
```

Never rewrite it to an absolute path, normalize it to a different prefix, or emit paths relative to the vLLM root.
