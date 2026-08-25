# Benchmark session

```text
Run an evidence-only retrieval benchmark session. Do not change code until the baseline is recorded.

Use only public Answered/Unanswered datasets for tuning. Record commit, retrieval method, chunk parameters, index time, indexed chunk count, maximum source span, warm docs+code search time, Recall@1/3/5/10 for docs and code, and any validation failures.

If a change is proposed, change one meaningful variable at a time when practical. Reject improvements that depend on exact public question strings, file-specific hard-coding, or private ground truth. After each accepted change, rerun the same benchmark and update docs/progress/BENCHMARKS.md.

Use Ponytail to prefer the simplest change that achieves the required threshold.
```
