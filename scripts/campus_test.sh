#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_CACHE_DIRECTORY="${MODEL_CACHE_DIRECTORY:-models/huggingface}"
LOCAL_FILES_ONLY="${LOCAL_FILES_ONLY:-False}"
SKIP_GENERATION=0

usage() {
  cat <<'TXT'
Usage: bash scripts/campus_test.sh [options]

Run the mandatory pipeline on native campus Linux and save all stdout/stderr in
one log under evaluations/campus/. Private unanswered questions are used only
for retrieval timing; this script never opens answered labels or runs Moulinette.

Options:
  --model-cache-directory PATH  Qwen cache path (default: models/huggingface)
  --local-files-only BOOL       True forbids model downloads (default: False)
  --skip-generation             Skip the sourced Qwen answer smoke
  -h, --help                    Show this help

After the run, paste the complete CAMPUS_TEST_LOG file into the Hermes session.
TXT
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model-cache-directory)
      MODEL_CACHE_DIRECTORY="$2"
      shift 2
      ;;
    --local-files-only)
      LOCAL_FILES_ONLY="$2"
      shift 2
      ;;
    --skip-generation)
      SKIP_GENERATION=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

cd "$ROOT"
RUN_ID="$(date +'%Y-%m-%d_%H-%M-%S')"
RUN_DIR="$ROOT/evaluations/campus/$RUN_ID"
LOG_FILE="$RUN_DIR/campus_test.log"
SEARCH_DIR="$RUN_DIR/search_results"
PUBLIC_SUBSET="$RUN_DIR/public-unanswered.json"
PUBLIC_SEARCH_DIR="$RUN_DIR/public-search-results"
mkdir -p "$SEARCH_DIR"
touch "$LOG_FILE"
exec > >(tee -a "$LOG_FILE") 2>&1

FAILURES=0

run_step() {
  local name="$1"
  shift
  echo
  echo "===== BEGIN $name ====="
  printf 'COMMAND:'
  printf ' %q' "$@"
  echo
  set +e
  TIMEFORMAT='STEP_TIME real=%3R user=%3U sys=%3S'
  time "$@"
  local status=$?
  set -e
  echo "STEP_RESULT name=$name exit=$status"
  echo "===== END $name ====="
  if [[ $status -ne 0 ]]; then
    FAILURES=$((FAILURES + 1))
  fi
}

require_file() {
  if [[ ! -f "$1" ]]; then
    echo "Missing required file: $1" >&2
    echo "Stage the corpus/private datasets before running this script." >&2
    exit 2
  fi
}

require_directory() {
  if [[ ! -d "$1" ]]; then
    echo "Missing required directory: $1" >&2
    echo "Stage the corpus/private datasets before running this script." >&2
    exit 2
  fi
}

command -v uv >/dev/null || { echo "uv is required" >&2; exit 2; }
command -v make >/dev/null || { echo "make is required" >&2; exit 2; }
require_directory "data/raw/vllm-0.10.1"
require_file "data/datasets/private/UnansweredQuestions/dataset_docs_private.json"
require_file "data/datasets/private/UnansweredQuestions/dataset_code_private.json"
if [[ $SKIP_GENERATION -eq 0 ]]; then
  require_file \
    "data/datasets/datasets_public/public/UnansweredQuestions/dataset_docs_public.json"
fi

prepare_public_subset() {
  uv run python - "$PUBLIC_SUBSET" <<'PY'
import json
import sys
from pathlib import Path

source = Path(
    "data/datasets/datasets_public/public/UnansweredQuestions/"
    "dataset_docs_public.json"
)
output = Path(sys.argv[1])
dataset = json.loads(source.read_text(encoding="utf-8"))
output.write_text(
    json.dumps({"rag_questions": dataset["rag_questions"][:2]}, indent=2),
    encoding="utf-8",
)
PY
}

validate_batch_identity() {
  uv run python - "$PUBLIC_SEARCH_DIR/public-unanswered.json" \
    "$RUN_DIR/public-answers/public-unanswered.json" <<'PY'
import sys
from pathlib import Path

from src.domain import StudentSearchResults, StudentSearchResultsAndAnswer

source = StudentSearchResults.model_validate_json(Path(sys.argv[1]).read_text())
answer = StudentSearchResultsAndAnswer.model_validate_json(
    Path(sys.argv[2]).read_text()
)
assert answer.k == source.k
assert [item.question_id for item in answer.search_results] == [
    item.question_id for item in source.search_results
]
assert [item.question for item in answer.search_results] == [
    item.question for item in source.search_results
]
assert [item.retrieved_sources for item in answer.search_results] == [
    item.retrieved_sources for item in source.search_results
]
print("BATCH_IDENTITY=PASS")
PY
}

echo "CAMPUS_TEST_VERSION=1"
echo "CAMPUS_TEST_RUN_ID=$RUN_ID"
echo "CAMPUS_TEST_ROOT=$ROOT"
echo "CAMPUS_TEST_LOG=$LOG_FILE"
echo "GIT_HEAD=$(git rev-parse HEAD 2>/dev/null || echo unavailable)"
echo "STARTED_AT=$(date -Iseconds)"
echo "MODEL_CACHE_DIRECTORY=$MODEL_CACHE_DIRECTORY"
echo "LOCAL_FILES_ONLY=$LOCAL_FILES_ONLY"
echo "SKIP_GENERATION=$SKIP_GENERATION"
echo
uname -a
uv --version
python3 --version
command -v lscpu >/dev/null && lscpu
command -v free >/dev/null && free -h
command -v df >/dev/null && df -Th .

run_step uv_sync uv sync --locked
run_step make_check make check
run_step torch_default_threads uv run python -c \
  'import torch; print(f"PYTORCH_DEFAULT_THREADS={torch.get_num_threads()}")'
run_step index uv run python -m src index --max_chunk_size 2000
run_step search uv run python -m src search \
  "What is paged attention?" --k 5
run_step private_docs_search uv run python -m src search_dataset \
  --dataset_path \
  data/datasets/private/UnansweredQuestions/dataset_docs_private.json \
  --k 10 \
  --save_directory "$SEARCH_DIR"
run_step private_code_search uv run python -m src search_dataset \
  --dataset_path \
  data/datasets/private/UnansweredQuestions/dataset_code_private.json \
  --k 10 \
  --save_directory "$SEARCH_DIR"
run_step answer_k_zero uv run python -m src answer \
  "What is vLLM?" \
  --k 0 \
  --save_path "$RUN_DIR/answer-k-zero.json" \
  --model_cache_directory "$MODEL_CACHE_DIRECTORY" \
  --local_files_only="$LOCAL_FILES_ONLY"

if [[ $SKIP_GENERATION -eq 0 ]]; then
  run_step prepare_public_subset prepare_public_subset
  run_step public_subset_search uv run python -m src search_dataset \
    --dataset_path "$PUBLIC_SUBSET" \
    --k 10 \
    --save_directory "$PUBLIC_SEARCH_DIR"
  run_step sourced_answer uv run python -m src answer \
    "What does Volta refer to in vLLM hardware documentation?" \
    --k 1 \
    --save_path "$RUN_DIR/answer-smoke.json" \
    --model_cache_directory "$MODEL_CACHE_DIRECTORY" \
    --local_files_only="$LOCAL_FILES_ONLY"
  run_step public_answer_dataset uv run python -m src answer_dataset \
    --student_search_results_path \
    "$PUBLIC_SEARCH_DIR/public-unanswered.json" \
    --save_directory "$RUN_DIR/public-answers" \
    --model_cache_directory "$MODEL_CACHE_DIRECTORY" \
    --local_files_only="$LOCAL_FILES_ONLY"
  run_step validate_batch_identity validate_batch_identity
else
  echo
  echo "STEP_RESULT name=generation_smokes status=SKIPPED"
fi

if [[ -f exams/scripts/exam_edge_cases.sh ]]; then
  run_step edge_exam bash exams/scripts/exam_edge_cases.sh --student-path .
else
  echo
  echo "STEP_RESULT name=edge_exam status=SKIPPED reason=exams_not_present"
fi

echo
echo "===== REPOSITORY INTEGRITY ====="
git status --short --untracked-files=no || true
for path in \
  data/processed/lexical_index.sqlite3 \
  "$RUN_DIR" \
  models/huggingface; do
  git check-ignore "$path" 2>/dev/null || true
done

echo "FINISHED_AT=$(date -Iseconds)"
if [[ $FAILURES -eq 0 ]]; then
  echo "CAMPUS_TEST_RESULT=PASS"
else
  echo "CAMPUS_TEST_RESULT=FAIL failures=$FAILURES"
fi
echo "CAMPUS_TEST_LOG=$LOG_FILE"
echo "Paste the complete log file into the Hermes session."

[[ $FAILURES -eq 0 ]]
