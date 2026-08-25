#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v hermes >/dev/null 2>&1; then
  echo "ERROR: hermes executable not found in PATH." >&2
  exit 1
fi

echo "Installing/enabling Ponytail..."
hermes plugins enable ponytail --no-allow-tool-override || hermes plugins install DietrichGebert/ponytail --enable

(cd "$ROOT" && python scripts/install-hermes-skill.py)
(cd "$ROOT" && python scripts/validate-context.py)
echo "Hermes setup complete. Restart Hermes before using the plugin/skill."
