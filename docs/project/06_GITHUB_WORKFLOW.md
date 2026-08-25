# GitHub workflow

## Project board
Use one Project associated with the repository. Reuse existing fields/status names if present. Recommended minimal flow:

```text
Backlog -> Ready -> In progress -> Review -> Done
```

Issues are the durable work specification; Project status is the work-state projection.

## Session GitHub read order

1. Repository default branch and current branch.
2. Open issues, especially Ready/In progress.
3. Active PRs and review threads.
4. Associated Project status.
5. CI on the branch/PR.

Do not plan from stale local docs without this readback.

## Issue quality bar
Use `.github/ISSUE_TEMPLATE/implementation.yml`, `bug.yml`, or `benchmark.yml`. A good issue is executable by another engineer without hidden chat context.

## PR quality bar
Use `.github/pull_request_template.md`. Include actual evidence, not generic prose. A PR with red/unknown required checks stays draft/not-ready. The owner merges manually unless explicitly requested otherwise.

## Project API limitation
GitHub Project v2 often needs extra token scopes. If `gh project` or an integration reports missing `read:project`/`project` scope:

- continue issue/branch/PR work if authorized;
- record the Project sync limitation visibly;
- do not create a duplicate Project as a workaround;
- synchronize later when credentials are fixed.
