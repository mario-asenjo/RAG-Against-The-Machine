# Workflow provenance and adaptations

This harness intentionally reuses the strongest patterns already present in Mario's repositories while removing project-specific assumptions that do not belong in RAG Against the Machine.

## Reused from Fly-In

- Root `AGENTS.md` as the always-on project operating contract.
- Mandatory session-start readback instead of assuming working-tree/project state.
- Vertical slices with explicit scope and non-goals.
- Fresh tests/lint/type/benchmark evidence before claiming completion.
- Ponytail `full` for coding, diff review after non-trivial slices, audit at milestones.
- Progress files as durable repository state rather than bloated global agent memory.
- Detailed PRs that explain architecture/data flow, invariants, tests, risk, reversal, and Ponytail outcome.
- Manual merge by the owner unless explicitly requested otherwise.
- Honest handling of GitHub Project token-scope limitations rather than pretending synchronization succeeded.

## Reused from Codexion

- Incremental implementation instead of opaque full-project generation.
- Public Hermes skills for general Git/software delivery workflows where possible.
- Project-specific expert rules expressed as a local operating contract rather than unnecessary custom tooling.
- Evaluation/defense readiness treated as a first-class engineering requirement.

## Adapted for this RAG project

- Public-vs-private dataset policy is explicit to prevent evaluator overfitting.
- Exact source path/character offsets are elevated to a core invariant because Recall@k depends on them.
- Benchmark ledger tracks Recall@1/3/5/10, index time, warm retrieval time, and maximum source span.
- Mandatory lexical retrieval is prioritized before semantic/hybrid bonus work.
- GitHub issue templates include benchmark experiments because retrieval quality is empirical.

## Current Hermes/Ponytail compatibility

Current Hermes documentation favors progressively disclosed skills: project-wide hard constraints stay in `AGENTS.md`, while procedural project knowledge can live in an on-demand skill. The setup scripts therefore copy the local project skill into the user's Hermes skill catalog and install the upstream Ponytail plugin rather than vendoring Ponytail itself.
