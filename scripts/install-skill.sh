#!/usr/bin/env bash
# install-skill.sh — copy a skill from this repo into the local Hermes skills dir.
# Usage: ./scripts/install-skill.sh <skill-name>
# Copies skills/<skill-name> -> ~/.hermes/skills/<skill-name> (overwrites if present).
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <skill-name>" >&2
  exit 1
fi

SKILL="$1"
SRC="$(cd "$(dirname "$0")/.." && pwd)/skills/$SKILL"
DEST="${HERMES_SKILLS_DIR:-$HOME/.hermes/skills}/$SKILL"

if [ ! -d "$SRC" ]; then
  echo "error: no skill at $SRC" >&2
  exit 1
fi
if [ ! -f "$SRC/SKILL.md" ]; then
  echo "error: $SRC has no SKILL.md" >&2
  exit 1
fi

mkdir -p "$(dirname "$DEST")"
rm -rf "$DEST"
cp -r "$SRC" "$DEST"
echo "installed $SKILL -> $DEST"
echo "reload Hermes (new session) to pick it up."
