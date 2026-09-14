# Open questions

Record only unresolved decisions that can materially change implementation.

- Q2: What Python structural granularity best balances exact source overlap and ranking specificity under 2000 chars?
- Q3: What Markdown/text overlap, if any, improves docs recall without flooding top-k with adjacent duplicates?
- Q5: Does the final evaluator environment have network access/model cache, or must README/setup make the model acquisition assumption explicit? Confirm from official staff guidance if available; do not guess.
- Q6: Does #45's locally measured 64 MiB SQLite page-cache improvement transfer to
  the campus native-Linux NFS filesystem with useful margin? Use one confirmation
  on unanswered inputs without rerunning private-label evaluation. Qwen timing is
  still not formal answer-quality evidence.
