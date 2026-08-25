## Summary

Closes #

Explain the user/evaluator-visible outcome and why this slice exists.

## Scope

### Included
- 

### Explicit non-goals
- 

## Source / requirement context

- Subject section(s):
- Evaluation contract / parent issue:
- Decision/ADR if applicable:

## Design and data flow

Describe only the architecture touched by this PR. Include the exact path/offset invariant if retrieval/chunking changes.

## Files / components changed

- 

## Subject and evaluator invariants checked

- [ ] Python/uv/CLI contract preserved where applicable.
- [ ] Pydantic exchange/output contract preserved where applicable.
- [ ] Exact corpus `file_path` preserved.
- [ ] Exact original character offsets preserved.
- [ ] No emitted source exceeds configured max / 2000 chars.
- [ ] No moulinette import/call added.
- [ ] Expected edge cases do not leak unhandled tracebacks.
- [ ] No private-ground-truth tuning or hard-coded question/source mapping.
- [ ] No generated data/model weights/private evaluator data committed.

## Tests and fresh evidence

### RED / reproduction before fix (when applicable)

```text
Command:
Result:
```

### Focused tests

```text
Command:
Result:
```

### Full quality gates

```text
Command:
Result:
```

## Retrieval/performance evidence (if behavior changed)

| Metric | Before | After | Gate |
|---|---:|---:|---:|
| Indexing time |  |  | <= 300s |
| Warm retrieval (docs+code) |  |  | <= 90s |
| Docs Recall@5 |  |  | >= 0.80 |
| Code Recall@5 |  |  | >= 0.50 |
| Max emitted span |  |  | <= 2000 |

If not applicable, say why rather than fabricating numbers.

## Edge cases / compatibility / reversal

- Known risks:
- Backward compatibility:
- Reversal path:

## Documentation and project state

- [ ] `docs/progress/CURRENT.md` updated if state changed.
- [ ] `SESSION_LOG.md` contains concise evidence.
- [ ] `RISKS.md` / `DECISION_LOG.md` / `BENCHMARKS.md` updated only if needed.
- [ ] GitHub issue updated/linked.
- [ ] Associated GitHub Project status moved to Review when access permits.

## Ponytail review

Mode: `full`

Applied simplifications:
- 

Rejected findings and requirement/test justification:
- 

## Delivery checklist

- [ ] Final diff is issue-scoped and reviewed.
- [ ] No secrets/unrelated/generated files.
- [ ] Required local checks have fresh evidence above.
- [ ] Required CI is green on the final head, or PR remains draft/not-ready.
- [ ] No auto-merge unless Mario explicitly requested it.
