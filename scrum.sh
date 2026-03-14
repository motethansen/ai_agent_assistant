#!/bin/bash
# scrum.sh — Activate venv and run scrum.py
# Usage: ./scrum.sh <project> <command> [args]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV" ]; then
    echo "Virtual environment not found. Run ./install.sh first."
    exit 1
fi

source "$VENV/bin/activate"
exec python "$SCRIPT_DIR/scrum.py" "$@"
