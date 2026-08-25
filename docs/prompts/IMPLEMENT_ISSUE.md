# Implement one issue

```text
Implement only GitHub issue #<N>.

Before editing:
- re-read AGENTS.md and the issue;
- inspect git status/current diff;
- inspect issue comments/dependencies and Project status;
- set/confirm the issue is In progress when Project access permits;
- activate Ponytail full.

Work as one vertical slice. Add the smallest failing test/check when practical, then the minimum implementation. Preserve exact source-path/offset invariants. Do not start follow-up scope.

Before opening/updating the PR:
- run focused tests;
- run affected full gates;
- run public benchmark if retrieval behavior changed;
- run /ponytail-review;
- update CURRENT/SESSION_LOG/RISKS/DECISION_LOG/BENCHMARKS only where changed;
- inspect final diff for scope creep/secrets/generated data;
- push and create/update a complete PR using the repository template;
- read CI back and leave the PR draft/not-ready while required checks are red or unknown.

Return issue, branch, PR, exact evidence, Ponytail outcome, Project sync state, risks, and the next smallest follow-up without implementing it.
```
