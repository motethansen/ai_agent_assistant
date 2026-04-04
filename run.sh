#!/bin/bash
# AI Agent Assistant — venv-aware launcher
#
# ./run.sh          → interactive chat (recommended for daily use)
# ./run.sh --today  → show today's tasks and exit
# ./run.sh --plan   → run planning session
# ./run.sh --help   → all available flags
#
# To run the background file-watcher daemon:
#   ./service.sh start       (background, logs to logs/daemon.log)
#   ./service.sh install     (install as launchd/systemd service)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python3"
MIN_MAJOR=3
MIN_MINOR=11

# ── Check venv exists ────────────────────────────────────────────────────────
if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: Virtual environment not found (.venv/bin/python3 missing)."
    echo "       Run: ./install.sh"
    exit 1
fi

# ── Check venv Python version ────────────────────────────────────────────────
VER=$("$VENV_PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
MAJ=$(echo "$VER" | cut -d. -f1)
MIN=$(echo "$VER" | cut -d. -f2)

if [ "$MAJ" -lt "$MIN_MAJOR" ] || { [ "$MAJ" -eq "$MIN_MAJOR" ] && [ "$MIN" -lt "$MIN_MINOR" ]; }; then
    echo "ERROR: .venv is using Python $VER but ${MIN_MAJOR}.${MIN_MINOR}+ is required."
    echo "       Recreate the venv with a newer Python:"
    echo "         rm -rf .venv && ./install.sh"
    exit 1
fi

# ── Default to interactive chat ───────────────────────────────────────────────
if [ $# -eq 0 ]; then
    exec "$VENV_PYTHON" main.py --chat
fi

exec "$VENV_PYTHON" main.py "$@"
