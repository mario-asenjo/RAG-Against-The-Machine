# Expected local data layout

The subject/evaluator expects this shape during execution:

```text
data/
├── raw/
│   └── vllm-0.10.1/
├── processed/
├── datasets/
│   ├── datasets_public/
│   │   └── public/
│   │       ├── UnansweredQuestions/
│   │       └── AnsweredQuestions/
│   └── private/                  # evaluator/holdout when present
└── output/
    ├── search_results/
    │   ├── UnansweredQuestions/
    │   └── AnsweredQuestions/
    └── search_results_and_answer/
        ├── UnansweredQuestions/
        └── AnsweredQuestions/
```

The provided public zip layout is canonical for local development. Bootstrap
tooling must preserve it under
`data/datasets/datasets_public/public/{AnsweredQuestions,UnansweredQuestions}`;
it must not flatten the two question directories directly under `data/datasets/`.

All of `data/` is gitignored by this scaffold because the subject says not to submit large data/generated outputs. The implementation must create required runtime directories as needed.
