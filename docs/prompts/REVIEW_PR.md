# PR review session

```text
Review PR #<N> as an evaluator and senior maintainer. Read the linked issue, complete diff, PR discussion/review threads, CI status, and relevant subject/evaluation requirements.

Check:
- issue scope and non-goals;
- exact file-path and character-offset invariants when relevant;
- source spans <= 2000;
- required CLI/Pydantic/uv/Fire/tqdm behavior;
- graceful edge cases;
- fresh test/lint/type evidence;
- public Recall@5/performance evidence when retrieval changed;
- no private-ground-truth tuning;
- no generated/large evaluator data committed;
- docs/README claims match implementation;
- no speculative bonus architecture;
- Ponytail simplification opportunities.

Run /ponytail-review on the diff. Request changes for correctness/evidence gaps. Never approve based only on the PR description. Do not merge unless Mario explicitly asks for the merge and required checks are green.
```
