# Expected local data layout

The subject/evaluator expects this shape during execution:

```text
data/
├── raw/
│   └── vllm-0.10.1/
├── processed/
├── datasets/
│   ├── UnansweredQuestions/
│   ├── AnsweredQuestions/
│   └── private/                  # evaluator/holdout when present
└── output/
    ├── search_results/
    │   ├── UnansweredQuestions/
    │   └── AnsweredQuestions/
    └── search_results_and_answer/
        ├── UnansweredQuestions/
        └── AnsweredQuestions/
```

The provided public zip has an extra packaging prefix (`datasets_public/public/...`), so bootstrap tooling must place its inner `public/{AnsweredQuestions,UnansweredQuestions}` contents at the subject-compatible `data/datasets/{AnsweredQuestions,UnansweredQuestions}` locations.

All of `data/` is gitignored by this scaffold because the subject says not to submit large data/generated outputs. The implementation must create required runtime directories as needed.
