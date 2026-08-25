# GitHub Project playbook

## Rule
Use the repository's existing associated Project. The board is a workflow view of issues; it is not a substitute for detailed issue bodies.

## Recommended fields
Only add fields if the existing Project does not already express the need.

- Status: Backlog / Ready / In progress / Review / Done.
- Milestone/Phase: M0..M5, Bonus.
- Optional Priority: P0/P1/P2 only if useful.

Avoid story points, multiple duplicate status fields, or custom automation until the team actually uses them.

## Agent synchronization
At session start and handoff:

1. Read current issue and Project item status.
2. Move to In progress only when work starts.
3. Move to Review when a PR is genuinely reviewable and checks are not known-red.
4. Move to Done after merge/closure, not merely after local coding.
5. If Project API scope is missing, note it and leave issue/PR truth accurate.
