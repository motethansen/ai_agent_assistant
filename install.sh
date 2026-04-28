#!/bin/bash
# AI Agent Assistant — setup script
# Run: ./install.sh

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $1"; }
info() { echo -e "${CYAN}→${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
ask()  { echo -e "${BOLD}$1${NC}"; }

echo ""
echo -e "${BLUE}${BOLD}AI Agent Assistant — Setup${NC}"
echo -e "${BLUE}─────────────────────────────────────${NC}"
echo ""

# ── 1. Python check ────────────────────────────────────────────────────────────
info "Checking Python..."
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}✗ Python 3 not found. Install from https://python.org${NC}"
    exit 1
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
ok "Python $PY_VER"

# ── 2. Virtual environment ─────────────────────────────────────────────────────
if [ ! -d "venv" ]; then
    info "Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
ok "Virtual environment ready"

# ── 3. Core dependencies ───────────────────────────────────────────────────────
info "Installing core dependencies..."
pip install -q --upgrade pip
pip install -q google-genai groq icalendar rich python-frontmatter watchdog python-dateutil httpx pyyaml pytest pytest-mock
ok "Core dependencies installed"

# ── 4. Ollama (optional) ───────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}─────────────────────────────────────${NC}"
ask "[Optional] Local LLM (Ollama)"
echo "  Runs AI models locally — no internet required, no API cost."
echo "  Recommended for: mac mini, offline use, privacy."
echo "  Requires: ~4GB+ disk per model, 8GB+ RAM."
echo ""
read -p "$(echo -e ${BOLD}Install Ollama? [y/N]: ${NC})" INSTALL_OLLAMA
INSTALL_OLLAMA=${INSTALL_OLLAMA:-N}

OLLAMA_ENABLED="false"
OLLAMA_MODEL="qwen2.5:7b"

if [[ "$INSTALL_OLLAMA" =~ ^[Yy]$ ]]; then
    if command -v ollama &>/dev/null; then
        ok "Ollama already installed"
    else
        info "Installing Ollama..."
        if [[ "$(uname -s)" == "Darwin" ]]; then
            if command -v brew &>/dev/null; then
                brew install ollama
            else
                curl -fsSL https://ollama.ai/install.sh | sh
            fi
        else
            curl -fsSL https://ollama.ai/install.sh | sh
        fi
        ok "Ollama installed"
    fi

    echo ""
    ask "Which model would you like to use?"
    echo "  1. qwen2.5:7b  (recommended — 4.4GB, fast)"
    echo "  2. llama3.2:3b  (smaller — 2GB, faster)"
    echo "  3. Enter custom model name"
    read -p "$(echo -e ${BOLD}Choice [1]: ${NC})" MODEL_CHOICE
    MODEL_CHOICE=${MODEL_CHOICE:-1}
    case "$MODEL_CHOICE" in
        1) OLLAMA_MODEL="qwen2.5:7b" ;;
        2) OLLAMA_MODEL="llama3.2:3b" ;;
        *) read -p "$(echo -e ${BOLD}Model name: ${NC})" OLLAMA_MODEL ;;
    esac

    info "Pulling model: $OLLAMA_MODEL (this may take a few minutes)..."
    ollama pull "$OLLAMA_MODEL"
    ok "Model ready: $OLLAMA_MODEL"
    OLLAMA_ENABLED="true"

    pip install -q ollama
    ok "Ollama Python SDK installed"
fi

# ── 5. LLM routing ────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}─────────────────────────────────────${NC}"
ask "Choose your primary LLM"
if [[ "$OLLAMA_ENABLED" == "true" ]]; then
    echo "  1. Gemini Flash 2.0  (free tier — recommended)"
    echo "  2. Groq Llama 3.3    (free tier — fast)"
    echo "  3. Ollama ($OLLAMA_MODEL) — local, no internet"
else
    echo "  1. Gemini Flash 2.0  (free tier — recommended)"
    echo "  2. Groq Llama 3.3    (free tier — fast)"
fi
echo ""
read -p "$(echo -e ${BOLD}Choice [1]: ${NC})" LLM_CHOICE
LLM_CHOICE=${LLM_CHOICE:-1}

case "$LLM_CHOICE" in
    2)
        ROUTING_CHAT="groq"
        ROUTING_PLANNING="groq"
        ROUTING_NOTES="groq"
        ROUTING_QUICK="groq"
        ;;
    3)
        ROUTING_CHAT="ollama"
        ROUTING_PLANNING="ollama"
        ROUTING_NOTES="ollama"
        ROUTING_QUICK="ollama"
        ;;
    *)
        ROUTING_CHAT="gemini-flash"
        ROUTING_PLANNING="gemini-pro"
        ROUTING_NOTES="gemini-flash"
        ROUTING_QUICK="groq"
        ;;
esac
ok "LLM routing configured"

# ── 6. API keys ────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}─────────────────────────────────────${NC}"
ask "API Keys"

GEMINI_API_KEY=""
GROQ_API_KEY=""

if [[ "$LLM_CHOICE" != "3" ]]; then
    echo ""
    echo "  Gemini API key — get free key at: https://aistudio.google.com"
    read -p "$(echo -e ${BOLD}Gemini API key: ${NC})" GEMINI_API_KEY
fi

if [[ "$LLM_CHOICE" != "3" ]]; then
    echo ""
    echo "  Groq API key (optional) — get free key at: https://console.groq.com"
    read -p "$(echo -e ${BOLD}Groq API key (press Enter to skip): ${NC})" GROQ_API_KEY
fi

# ── 7. Paths ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}─────────────────────────────────────${NC}"
ask "Vault paths"
echo ""

# Try to detect common iCloud paths
DEFAULT_OBSIDIAN=""
DEFAULT_LOGSEQ=""
if [[ "$(uname -s)" == "Darwin" ]]; then
    ICLOUD_BASE="$HOME/Library/Mobile Documents"
    if [ -d "$ICLOUD_BASE/iCloud~md~obsidian/Documents" ]; then
        DEFAULT_OBSIDIAN="$ICLOUD_BASE/iCloud~md~obsidian/Documents"
    fi
    if [ -d "$ICLOUD_BASE/iCloud~com~logseq~logseq/Documents" ]; then
        DEFAULT_LOGSEQ="$ICLOUD_BASE/iCloud~com~logseq~logseq/Documents"
    fi
fi

read -p "$(echo -e ${BOLD}Obsidian vault path [${DEFAULT_OBSIDIAN}]: ${NC})" OBSIDIAN_DIR
OBSIDIAN_DIR=${OBSIDIAN_DIR:-$DEFAULT_OBSIDIAN}

read -p "$(echo -e ${BOLD}LogSeq graph path [${DEFAULT_LOGSEQ}]: ${NC})" LOGSEQ_DIR
LOGSEQ_DIR=${LOGSEQ_DIR:-$DEFAULT_LOGSEQ}

ok "Paths configured"

# ── 8. Planning preferences ────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}─────────────────────────────────────${NC}"
ask "Planning preferences (press Enter to accept defaults)"
echo ""
read -p "$(echo -e ${BOLD}Deep work start [09:00]: ${NC})" DEEP_WORK_START
DEEP_WORK_START=${DEEP_WORK_START:-09:00}
read -p "$(echo -e ${BOLD}Deep work end [12:00]: ${NC})" DEEP_WORK_END
DEEP_WORK_END=${DEEP_WORK_END:-12:00}
read -p "$(echo -e ${BOLD}Focus categories [dev,writing,learning]: ${NC})" FOCUS_CATS
FOCUS_CATS=${FOCUS_CATS:-dev,writing,learning}

ok "Preferences saved"

# ── 9. Write .config ──────────────────────────────────────────────────────────
info "Writing .config..."
cat > .config << EOF
# AI Agent Assistant — generated by install.sh
# Edit any values here, then restart the assistant.

# Paths
WORKSPACE_DIR=$OBSIDIAN_DIR
LOGSEQ_DIR=$LOGSEQ_DIR
OBSIDIAN_DASHBOARD_FILE=Dashboard.md
LOGSEQ_JOURNAL_DAYS=2

# LLM routing
ROUTING_CHAT=$ROUTING_CHAT
ROUTING_PLANNING=$ROUTING_PLANNING
ROUTING_NOTES=$ROUTING_NOTES
ROUTING_QUICK=$ROUTING_QUICK
ROUTING_OFFLINE=ollama

# Gemini (Google AI Studio — free tier)
GEMINI_API_KEY=$GEMINI_API_KEY
GEMINI_FLASH_MODEL=gemini-2.0-flash
GEMINI_PRO_MODEL=gemini-1.5-pro

# Groq (free tier)
GROQ_API_KEY=$GROQ_API_KEY
GROQ_MODEL=llama-3.3-70b-versatile

# Ollama (local — optional)
OLLAMA_ENABLED=$OLLAMA_ENABLED
OLLAMA_MODEL=$OLLAMA_MODEL
OLLAMA_HOST=http://localhost:11434

# Planning
CHRONOTYPE=morning_owl
DEEP_WORK_START=$DEEP_WORK_START
DEEP_WORK_END=$DEEP_WORK_END
FOCUS_CATEGORIES=$FOCUS_CATS

# Sync
SYNC_INTERVAL_MINUTES=30

# Calendar
GCAL_TAG=gcal
LOCAL_CALENDAR_FILE=output/local_calendar.ics
GOOGLE_CAL_ENABLED=false
GOOGLE_CAL_CREDENTIALS=
APPLE_CALENDAR_NAME=Home
EOF
ok ".config written"

# ── 10. Output directory ───────────────────────────────────────────────────────
mkdir -p output
ok "Output directory ready"

# ── 11. Cron setup (optional) ─────────────────────────────────────────────────
echo ""
echo -e "${BLUE}─────────────────────────────────────${NC}"
ask "Background sync (every 30 min)"
echo "  Automatically syncs LogSeq → Obsidian while you work."
echo ""
read -p "$(echo -e ${BOLD}Set up background sync? [Y/n]: ${NC})" SETUP_CRON
SETUP_CRON=${SETUP_CRON:-Y}

if [[ "$SETUP_CRON" =~ ^[Yy]$ ]]; then
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    PYTHON_BIN="$SCRIPT_DIR/venv/bin/python3"
    CRON_CMD="*/30 * * * * cd $SCRIPT_DIR && $PYTHON_BIN cron_job.py >> $SCRIPT_DIR/output/cron.log 2>&1"
    (crontab -l 2>/dev/null | grep -v "cron_job.py"; echo "$CRON_CMD") | crontab -
    ok "Cron job added (every 30 min)"
else
    info "Skipped — run manually: python cron_job.py"
fi

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}Setup complete!${NC}"
echo ""
echo "  Start the assistant:  source venv/bin/activate && python main.py"
echo "  Run a sync now:       python main.py --sync"
echo "  Show status:          python main.py --status"
echo "  See today's tasks:    python main.py --today"
echo ""
