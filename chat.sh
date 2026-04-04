#!/bin/bash
# AI Agent Assistant — interactive chat
# Launches the terminal chat interface using the project venv.
# The background daemon (service) is a separate process — see service.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python3"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: Virtual environment not found. Run: ./install.sh"
    exit 1
fi

exec "$VENV_PYTHON" main.py --chat "$@"
