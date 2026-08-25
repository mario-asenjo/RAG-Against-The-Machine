# Decision log

## D-0001 — Mandatory-first, lexical-first
**Status:** accepted for bootstrap.

The harness will not begin with embeddings/hybrid retrieval. The subject requires a lexical method and only grades bonuses after mandatory validation. Establish a lexical public baseline first.

## D-0002 — Private datasets are holdout
**Status:** accepted for harness workflow.

Although private datasets were supplied with the project materials, their answered ground truth will not be inspected to tune retrieval. This keeps evaluator evidence meaningful and reduces overfitting risk.

## D-0003 — AGENTS is always-on; Hermes skills are optional/on-demand
**Status:** accepted.

Project-specific hard constraints live in root `AGENTS.md`. The optional project skill is installed into Hermes's skill catalog by setup scripts so it is loaded on demand rather than permanently bloating context.

## D-0004 — One GitHub Project, issue-first delivery
**Status:** accepted.

Every non-trivial implementation slice is issue-backed and synchronized to the existing associated Project when scopes permit. No duplicate board is created to work around missing token scope.
