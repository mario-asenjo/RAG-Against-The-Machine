# Clean-checkout mandatory rehearsal — issues #25 and #16

## Scope and authorization

The rehearsal used a disposable Git worktree at merged mandatory commit
`7cd34f8119bef6c331a022cbf987e93172882ac0`. Mario explicitly authorized one
blind private retrieval run in the active session. The run below is that single
#16 holdout use: only aggregate timing, Recall, and pass/fail are retained. No
private answered JSON, source spans, answers, or question-level results were
opened or copied, and no private-label tuning or rerun was performed.

The worktree ran under WSL Ubuntu on the Windows-mounted `v9fs` filesystem. It
was deleted after evidence was committed and pushed.

## Evaluator artifact layout

Extracting `exams.zip` in the repository root produced the expected
`exams/scripts/` tree. All three scripts passed `bash -n`, and their
`SCRIPT_DIR/../..` calculation correctly resolved the repository root.

Extracting `moulinette.zip` in the repository root produced
`moulinette-ubuntu` and `moulinette-fedora`. The Ubuntu binary executed under
WSL and evaluated generated search output successfully. Moulinette binaries,
indexes, datasets, model files, outputs, and `evaluations/` are ignored. The
injected `exams/` directory is intentionally untracked rather than ignored and
must never be staged.

## Clean setup

The repository helper exposed one real setup defect. Running
`scripts/bootstrap-data.sh` with the supplied archives failed before tests:

```text
cp: cannot stat '<tmp>/public/AnsweredQuestions': No such file or directory
```

The staging directory itself is named `<tmp>/public`, so its `find ... -path
'*/public'` selects that directory instead of the archive's
`datasets_public/public` directory. Issue #43 tracks both selecting the real
archive root and preserving it at
`data/datasets/datasets_public/public/{AnsweredQuestions,UnansweredQuestions}`.
For this rehearsal, the same archives were staged manually without changing any
source or dataset content.

A fresh WSL `.venv` then completed `uv sync --locked`. Installing 44 packages
onto the mounted filesystem took 6m58s because uv could not hardlink from its
cache and copied packages instead. This setup duration is environmental and is
not the subject's index/retrieval timing gate.

```text
make check
Context validation passed.
Flake8 passed.
Mypy passed over 35 source files.
122 passed in 237.04s.
```

An earlier tool timeout interrupted the first environment creation and left an
incomplete torch install. Removing that disposable `.venv` and repeating a
fresh sync resolved it without repository changes.

## Blind private retrieval result

Exact evaluator script:

```text
bash exams/scripts/exam_retrieval.sh \
  --student-path . \
  --moulinette-path ./moulinette-ubuntu
```

Aggregate result from the one authorized private run:

| Gate | Result |
|---|---:|
| Indexing | PASS, 55s <= 300s |
| Warm retrieval | Inconclusive/FAIL in this environment |
| Docs Recall@5 | PASS, 0.800 >= 0.80 |
| Code Recall@5 | PASS, 0.510 >= 0.50 |
| Script summary | 3/4 |

The script reported docs retrieval as 46,453s because its `date +%s` interval
crossed a host/WSL clock discontinuity while the process was suspended between
tool waits. That number is not a valid runtime measurement. The subsequent
code search reported 115s, and a separate two-question public WSL smoke took
about 1.17s/question. These mounted-`v9fs` observations do not establish the
native Linux campus timing gate. The private run is not repeated: retrieval
timing must be measured on the campus filesystem without evaluating private
labels again.

The private recall result is therefore encouraging but narrow: both mandatory
Recall@5 thresholds passed, with docs exactly on its threshold. No tuning is
authorized from this holdout result.

## Mandatory command smokes

The supplied edge script passed all four required cases without tracebacks:

```text
bash exams/scripts/exam_edge_cases.sh --student-path .
FINAL RESULT: 4/4
STATUS: PASS
```

Using public data and the index built by the evaluator rehearsal:

- `search` returned ranked source locations;
- `search_dataset` wrote valid Pydantic output for a two-question public subset;
- `evaluate` validated that subset and produced Recall@5 1.000;
- `answer --k 0` passed through the supplied edge script without model assets;
- sourced `answer` completed with provisioned external Qwen cache in 124.67s;
- two-question `answer_dataset` completed in 131.87s;
- both answer outputs revalidated as `StudentSearchResultsAndAnswer`;
- batch `k`, IDs, questions, order, and source lists matched its search input.

The successful sourced answer commands used the separately provisioned local
Qwen cache via configurable `--model_cache_directory`; `uv sync` alone does not
download model weights. Their wall times include WSL startup and mounted-filesystem
cost and are integration evidence, not campus performance evidence.

## Repository integrity

Git Bash confirmed no tracked changes in the disposable checkout after all
commands. Generated index/output/evaluation files and Moulinette were ignored.
The evaluator-injected `exams/` tree remained untracked and unstaged. No private
artifact or generated result entered Git.

After the evidence documentation was written, final gates passed again on the
same mounted worktree: context validation, Flake8, normal mypy, 122 tests, and
strict mypy. The final pytest run took 909.48s on v9fs, further confirming that
this mounted environment is unsuitable for evaluator timing claims.

Git commands invoked inside WSL could not follow the worktree `.git` pointer
because Git for Windows wrote a native `C:/...` worktree metadata path. Git Bash
readback was used for repository-integrity checks; this does not affect the
Python evaluator commands.

## Outcome

Mandatory behavior and both private Recall@5 thresholds passed. #25 is not a
fully green bonus-unlock gate yet because:

1. clean data bootstrap has the focused #43 defect;
2. private warm-retrieval timing was invalid on this WSL/v9fs run;
3. campus-native timing and model-cache provisioning still need documentation.

No production code change is justified by this rehearsal.

## Campus-native follow-up

Run from the repository root on a native campus Linux filesystem after staging
the corpus plus public and private datasets. The public datasets must be under
`data/datasets/datasets_public/public/`:

```text
bash scripts/campus_test.sh
```

The script captures its complete stdout and stderr with `tee` under:

```text
evaluations/campus/<timestamp>/campus_test.log
```

It records environment/filesystem/CPU information, clean dependency and quality
gates, index time, separate private-unanswered docs/code retrieval times, edge
behavior, one public sourced answer, a two-question public `answer_dataset`, and
batch identity validation. It never opens private answered labels or invokes
Moulinette, so it does not repeat the consumed private-label evaluation.

If the model is already cached and campus network access should be forbidden:

```text
bash scripts/campus_test.sh \
  --model-cache-directory models/huggingface \
  --local-files-only True
```

Use `--skip-generation` when only retrieval timing is needed. After completion,
paste the entire file printed as `CAMPUS_TEST_LOG=...` into the Hermes session.
