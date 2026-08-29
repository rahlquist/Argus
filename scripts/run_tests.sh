#!/usr/bin/env bash
# run_tests.sh — run the skill test suite (stdlib + pytest, no network).
# Mirrors hermes-agent's tests/skills harness.
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v pytest >/dev/null 2>&1; then
  echo "pytest not found; installing into a venv via uv (or pip) is recommended." >&2
  echo "Fallback: pip install pytest" >&2
  exit 1
fi

pytest "${@:-tests/skills/}" -q
