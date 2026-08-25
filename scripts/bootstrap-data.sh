#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'TXT'
Usage:
  scripts/bootstrap-data.sh \
    --vllm /path/to/vllm-0.10.1.zip \
    --public /path/to/datasets_public.zip \
    [--private /path/to/datasets_private.zip]

The private archive is optional and is staged only as a holdout. Do not inspect its
AnsweredQuestions ground truth for tuning.
TXT
}

VLLM=""
PUBLIC=""
PRIVATE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --vllm) VLLM="$2"; shift 2 ;;
    --public) PUBLIC="$2"; shift 2 ;;
    --private) PRIVATE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

[[ -f "$VLLM" ]] || { echo "Missing --vllm archive" >&2; exit 2; }
[[ -f "$PUBLIC" ]] || { echo "Missing --public archive" >&2; exit 2; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$ROOT/data/raw" "$ROOT/data/datasets" "$ROOT/data/processed" "$ROOT/data/output"

unzip -q "$VLLM" -d "$TMP/vllm"
VLLM_DIR="$(find "$TMP/vllm" -maxdepth 1 -type d -name 'vllm-0.10.1' | head -1)"
[[ -n "$VLLM_DIR" ]] || { echo "Could not find vllm-0.10.1 in archive" >&2; exit 1; }
rm -rf "$ROOT/data/raw/vllm-0.10.1"
cp -R "$VLLM_DIR" "$ROOT/data/raw/vllm-0.10.1"

unzip -q "$PUBLIC" -d "$TMP/public"
PUB_ROOT="$(find "$TMP/public" -type d -path '*/public' | head -1)"
[[ -n "$PUB_ROOT" ]] || { echo "Could not find public/ dataset root" >&2; exit 1; }
rm -rf "$ROOT/data/datasets/AnsweredQuestions" "$ROOT/data/datasets/UnansweredQuestions"
cp -R "$PUB_ROOT/AnsweredQuestions" "$ROOT/data/datasets/AnsweredQuestions"
cp -R "$PUB_ROOT/UnansweredQuestions" "$ROOT/data/datasets/UnansweredQuestions"

if [[ -n "$PRIVATE" ]]; then
  [[ -f "$PRIVATE" ]] || { echo "Private archive not found: $PRIVATE" >&2; exit 2; }
  unzip -q "$PRIVATE" -d "$TMP/private"
  PRIV_ROOT="$(find "$TMP/private" -type d -path '*/private' | head -1)"
  [[ -n "$PRIV_ROOT" ]] || { echo "Could not find private/ dataset root" >&2; exit 1; }
  rm -rf "$ROOT/data/datasets/private"
  cp -R "$PRIV_ROOT" "$ROOT/data/datasets/private"
  echo "Private holdout staged at data/datasets/private/. Do not tune against its answered labels."
fi

cat <<TXT
Staged:
  data/raw/vllm-0.10.1/
  data/datasets/AnsweredQuestions/
  data/datasets/UnansweredQuestions/
These paths are gitignored.
TXT
