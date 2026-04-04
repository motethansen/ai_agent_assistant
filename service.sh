#!/bin/bash
# AI Agent Assistant — background file-watcher daemon
#
# USAGE:
#   ./service.sh start    — start the daemon in the background (logs to logs/daemon.log)
#   ./service.sh stop     — stop the daemon
#   ./service.sh status   — show whether the daemon is running
#   ./service.sh logs     — tail the daemon log
#
# For a persistent macOS launch agent (survives reboot), run:
#   ./service.sh install
# This installs a launchd plist and starts it immediately.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python3"
PID_FILE="$SCRIPT_DIR/logs/daemon.pid"
LOG_FILE="$SCRIPT_DIR/logs/daemon.log"
PLIST_LABEL="dev.aiagent.assistant"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_LABEL}.plist"

mkdir -p "$SCRIPT_DIR/logs"

# ── Helpers ──────────────────────────────────────────────────────────────────
is_running() {
    [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

cmd_start() {
    if is_running; then
        echo "Daemon already running (PID $(cat "$PID_FILE"))."
        return
    fi
    if [ ! -f "$VENV_PYTHON" ]; then
        echo "ERROR: Virtual environment not found. Run: ./install.sh"
        exit 1
    fi
    # Start LM Studio daemon for headless use (Linux) if enabled
    LMS_ENABLED=$(awk -F'=' '/^ENABLE_LM_STUDIO[ ]*=/ {print $2}' "$SCRIPT_DIR/.config" 2>/dev/null | tr -d ' \r')
    if [ "$LMS_ENABLED" == "true" ] && command -v lms > /dev/null 2>&1; then
        echo "Starting LM Studio daemon..."
        lms daemon start || true
    fi

    echo "Starting AI Agent Assistant daemon..."
    nohup "$VENV_PYTHON" main.py >> "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "Started (PID $!). Logs: $LOG_FILE"
}

cmd_stop() {
    if ! is_running; then
        echo "Daemon is not running."
        [ -f "$PID_FILE" ] && rm "$PID_FILE"
        return
    fi
    PID=$(cat "$PID_FILE")
    echo "Stopping daemon (PID $PID)..."
    kill "$PID"
    rm -f "$PID_FILE"
    echo "Stopped."
}

cmd_status() {
    if is_running; then
        echo "✓ Daemon is running (PID $(cat "$PID_FILE"))."
        echo "  Log: $LOG_FILE"
    else
        echo "✗ Daemon is not running."
    fi
}

cmd_logs() {
    if [ ! -f "$LOG_FILE" ]; then
        echo "No log file yet. Start the daemon first: ./service.sh start"
        exit 1
    fi
    tail -f "$LOG_FILE"
}

cmd_install() {
    # Install as a macOS launchd launch agent (auto-starts on login)
    if [ "$(uname -s)" != "Darwin" ]; then
        echo "launchd install is macOS only."
        echo "On Linux, use systemd:"
        echo ""
        echo "  sudo tee /etc/systemd/system/ai-agent.service <<EOF"
        echo "  [Unit]"
        echo "  Description=AI Agent Assistant daemon"
        echo "  [Service]"
        echo "  WorkingDirectory=$SCRIPT_DIR"
        echo "  ExecStart=$VENV_PYTHON $SCRIPT_DIR/main.py"
        echo "  Restart=on-failure"
        echo "  [Install]"
        echo "  WantedBy=multi-user.target"
        echo "  EOF"
        echo ""
        echo "  sudo systemctl daemon-reload"
        echo "  sudo systemctl enable --now ai-agent"
        exit 0
    fi

    cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${VENV_PYTHON}</string>
        <string>${SCRIPT_DIR}/main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>StandardOutPath</key>
    <string>${LOG_FILE}</string>
    <key>StandardErrorPath</key>
    <string>${LOG_FILE}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF

    launchctl load "$PLIST_PATH"
    echo "✓ Launch agent installed and started."
    echo "  Plist: $PLIST_PATH"
    echo "  Logs:  $LOG_FILE"
    echo ""
    echo "To uninstall:"
    echo "  launchctl unload $PLIST_PATH && rm $PLIST_PATH"
}

# ── Dispatch ─────────────────────────────────────────────────────────────────
case "${1:-}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    status)  cmd_status ;;
    logs)    cmd_logs ;;
    install) cmd_install ;;
    *)
        echo "Usage: ./service.sh {start|stop|status|logs|install}"
        echo ""
        echo "  start    — run daemon in background (logs to logs/daemon.log)"
        echo "  stop     — stop the background daemon"
        echo "  status   — show whether daemon is running"
        echo "  logs     — tail the daemon log"
        echo "  install  — install as a launchd agent (macOS) / print systemd unit (Linux)"
        exit 1
        ;;
esac
