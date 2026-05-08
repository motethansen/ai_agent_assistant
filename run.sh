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

MIN_MAJOR=3
MIN_MINOR=10

# ── Locate venv (support both venv/ and .venv/) ──────────────────────────────
if [ -f "$SCRIPT_DIR/venv/bin/python3" ]; then
    VENV_PYTHON="$SCRIPT_DIR/venv/bin/python3"
elif [ -f "$SCRIPT_DIR/.venv/bin/python3" ]; then
    VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python3"
else
    echo "ERROR: Virtual environment not found (venv/ or .venv/ missing)."
    echo "       Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# ── Check venv Python version ────────────────────────────────────────────────
VER=$("$VENV_PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
MAJ=$(echo "$VER" | cut -d. -f1)
MIN=$(echo "$VER" | cut -d. -f2)

if [ "$MAJ" -lt "$MIN_MAJOR" ] || { [ "$MAJ" -eq "$MIN_MAJOR" ] && [ "$MIN" -lt "$MIN_MINOR" ]; }; then
    echo "ERROR: venv is using Python $VER but ${MIN_MAJOR}.${MIN_MINOR}+ is required."
    exit 1
fi

# ── Default to interactive chat ───────────────────────────────────────────────
if [ $# -eq 0 ]; then
    exec "$VENV_PYTHON" main.py --chat
fi

exec "$VENV_PYTHON" main.py "$@"
