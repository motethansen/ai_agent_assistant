#!/bin/bash

# AI Agent Assistant: Guided Installation Script
# Supports macOS (Darwin) with OrbStack or Docker Desktop, and Linux with Docker.

set -e

# ANSI Color Codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BLUE}#######################################${NC}"
echo -e "${BLUE}#                                     #${NC}"
echo -e "${BLUE}#    🤖 AI AGENT ASSISTANT SETUP      #${NC}"
echo -e "${BLUE}#                                     #${NC}"
echo -e "${BLUE}#######################################${NC}"
echo ""

# Detect OS
OS_TYPE=$(uname -s)
echo -e "Detected Operating System: ${GREEN}$OS_TYPE${NC}"

# Progress Tracking
TOTAL_STEPS=10
CURRENT_STEP=0

# Global: install mode (set by select_install_mode)
INSTALL_MODE="local"

show_progress() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    PERCENT=$((CURRENT_STEP * 100 / TOTAL_STEPS))
    echo -e "\n${YELLOW}[Step $CURRENT_STEP/$TOTAL_STEPS - $PERCENT%] $1${NC}"
}

# Global: container runtime command (set by detect_container_runtime)
DOCKER_CMD=""

# ─────────────────────────────────────────────
# Helper: update or append a KEY=value in .config
# ─────────────────────────────────────────────
set_config_key() {
    local key="$1"
    local value="$2"
    local file=".config"
    if grep -qE "^#?\s*${key}=" "$file" 2>/dev/null; then
        sed -i.bak "s|^#\?\s*${key}=.*|${key}=${value}|" "$file" && rm -f "${file}.bak"
    else
        echo "${key}=${value}" >> "$file"
    fi
}

# ─────────────────────────────────────────────
# Helper: call Ollama for contextual advice
# Returns empty string if Ollama is not ready.
# ─────────────────────────────────────────────
ask_ollama() {
    local prompt="$1"
    local model
    model=$(awk -F'=' '/^OLLAMA_MODEL[ ]*=/ {print $2}' .config 2>/dev/null | tr -d ' \r')
    [ -z "$model" ] && model="llama3"

    local host
    host=$(awk -F'=' '/^OLLAMA_HOST[ ]*=/ {print $2}' .config 2>/dev/null | tr -d ' \r')
    [ -z "$host" ] && host="http://localhost:11434"

    # Quick reachability check (1s timeout)
    if ! curl -sf --max-time 1 "${host}/api/tags" > /dev/null 2>&1; then
        echo ""
        return
    fi

    local payload
    payload=$(printf '{"model":"%s","prompt":"%s","stream":false}' \
        "$model" \
        "$(echo "$prompt" | sed 's/"/\\"/g; s/$/\\n/' | tr -d '\n' | sed 's/\\n$//')")

    curl -s --max-time 20 -X POST "${host}/api/generate" \
        -H "Content-Type: application/json" \
        -d "$payload" 2>/dev/null \
        | python3 -c "import sys,json
try:
    d=json.load(sys.stdin)
    print(d.get('response','').strip())
except:
    pass" 2>/dev/null || true
}

# ─────────────────────────────────────────────
# Step 0: Upgrade check
# ─────────────────────────────────────────────
check_upgrade() {
    show_progress "Checking for project updates..."
    if [ -d ".git" ]; then
        echo -e "${BLUE}Git repository detected. Checking for remote updates...${NC}"
        git fetch origin --quiet 2>/dev/null || true
        LOCAL=$(git rev-parse HEAD 2>/dev/null || echo "")
        REMOTE=$(git rev-parse @{u} 2>/dev/null || echo "")
        if [ -n "$LOCAL" ] && [ -n "$REMOTE" ] && [ "$LOCAL" != "$REMOTE" ]; then
            echo -e "${YELLOW}New updates available!${NC}"
            read -p "Would you like to upgrade to the latest version? (y/n): " do_upgrade
            if [[ "$do_upgrade" == "y"* ]]; then
                git pull origin main --quiet
                echo -e "${GREEN}Project updated successfully.${NC}"
            fi
        else
            echo -e "${GREEN}Project is up to date.${NC}"
        fi
    fi
}

# ─────────────────────────────────────────────
# Step 1: Choose installation mode
# ─────────────────────────────────────────────
select_install_mode() {
    show_progress "Choose Installation Mode..."

    # Ensure .config exists so set_config_key can write to it
    if [ ! -f ".config" ]; then
        cp config.template .config
        echo -e "${GREEN}Created .config from template.${NC}"
    fi

    echo ""
    echo -e "${BOLD}Choose your installation mode:${NC}"
    echo ""
    echo -e "  ${GREEN}1) Full install${NC}  — local AI (Ollama) + optional cloud APIs"
    echo -e "     Best for privacy / offline use. Needs 4-8 GB RAM for a local model."
    echo ""
    echo -e "  ${CYAN}2) Cloud-only${NC}     — Groq / HuggingFace / OpenAI / Gemini / Claude only"
    echo -e "     No local model required. Lighter on RAM and disk. Requires API keys."
    echo ""
    read -p "Enter 1 or 2 [default: 1]: " mode_choice

    case "$mode_choice" in
        2)
            INSTALL_MODE="cloud"
            set_config_key "ENABLE_OLLAMA" "false"
            # Switch LLM_PRIORITY away from local models if it still points at ollama
            CURRENT_PRIORITY=$(grep -E "^LLM_PRIORITY=" .config | cut -d'=' -f2- | tr -d ' ')
            if [ -z "$CURRENT_PRIORITY" ] || [[ "$CURRENT_PRIORITY" == ollama* ]]; then
                set_config_key "LLM_PRIORITY" "groq,gemini,openai,claude,huggingface"
            fi
            echo -e "${CYAN}Cloud-only mode selected — local AI setup will be skipped.${NC}"
            ;;
        *)
            INSTALL_MODE="local"
            echo -e "${GREEN}Full install mode selected.${NC}"
            ;;
    esac
}

# ─────────────────────────────────────────────
# Step 2: Python + Git
# ─────────────────────────────────────────────
check_dependencies() {
    show_progress "Checking System Dependencies..."

    PYTHON_CMD=""
    for cmd in "python3.12" "python3.11" "python3"; do
        if command -v $cmd &> /dev/null; then
            VER=$($cmd -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
            MAJ=$(echo $VER | cut -d. -f1)
            MIN=$(echo $VER | cut -d. -f2)
            if [ "$MAJ" -eq 3 ] && [ "$MIN" -ge 11 ]; then
                PYTHON_CMD=$(command -v $cmd)
                break
            fi
        fi
    done

    if [ -z "$PYTHON_CMD" ]; then
        echo -e "${YELLOW}Python 3.11+ not found. Attempting to install Python 3.12...${NC}"
        if [ "$OS_TYPE" == "Darwin" ]; then
            if ! command -v brew &> /dev/null; then
                echo "Homebrew not found. Installing Homebrew first..."
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
                eval "$(/opt/homebrew/bin/brew shellenv)"
            fi
            brew install python@3.12
            PYTHON_CMD=$(brew --prefix)/bin/python3.12
        else
            sudo apt update -q
            sudo apt install -y software-properties-common
            sudo add-apt-repository -y ppa:deadsnakes/ppa
            sudo apt update -q
            sudo apt install -y python3.12 python3.12-venv
            PYTHON_CMD="/usr/bin/python3.12"
        fi
    fi

    if [ -z "$PYTHON_CMD" ] || ! $PYTHON_CMD --version &> /dev/null; then
        echo -e "${RED}✗ Failed to secure Python 3.11+.${NC}"
        echo -e "  Manual fix: install Python 3.11 or 3.12 from https://python.org"
        exit 1
    fi

    echo -e "  Python:  ${GREEN}$($PYTHON_CMD --version)${NC}"

    if ! command -v git &> /dev/null; then
        echo -e "${RED}✗ Git is not installed.${NC}"
        echo -e "  Manual fix (macOS):  brew install git"
        echo -e "  Manual fix (Linux):  sudo apt install git"
        exit 1
    fi
    echo -e "  Git:     ${GREEN}$(git --version)${NC}"
    export FINAL_PYTHON=$PYTHON_CMD
}

# ─────────────────────────────────────────────
# Step 2: Python venv + pip requirements
# ─────────────────────────────────────────────
setup_python_env() {
    show_progress "Setting up Python Environment..."
    if [ ! -d ".venv" ]; then
        echo "Creating virtual environment using $FINAL_PYTHON..."
        $FINAL_PYTHON -m venv .venv
    fi
    source .venv/bin/activate
    pip install --quiet --upgrade pip
    echo "Installing dependencies (this may take a minute)..."
    if [ "$OS_TYPE" == "Linux" ]; then
        grep -v "pyobjc" requirements.txt > requirements_linux.txt
        pip install --quiet -r requirements_linux.txt
        rm requirements_linux.txt
    else
        pip install --quiet -r requirements.txt
    fi
    echo -e "${GREEN}Python environment ready.${NC}"
}

# ─────────────────────────────────────────────
# Step 4: Local LLM (LM Studio or Ollama)
# ─────────────────────────────────────────────
setup_local_ai() {
    show_progress "Checking Local AI..."
    chmod +x scripts/manage_services.sh

    if [ "$INSTALL_MODE" == "cloud" ]; then
        echo -e "${CYAN}Cloud-only mode — skipping local AI setup.${NC}"
        return
    fi

    # Determine which backend is configured
    OLLAMA_ENABLED=$(awk -F'=' '/^ENABLE_OLLAMA[ ]*=/ {print $2}' .config 2>/dev/null | tr -d ' \r')

    # ── Ollama path ──
    if [ "$OLLAMA_ENABLED" == "true" ]; then
        echo -e "${CYAN}Primary LLM: Ollama${NC}"
        if ! command -v ollama &> /dev/null; then
            echo -e "${YELLOW}Ollama not found.${NC}"
            read -p "  Install Ollama now? (y/n): " install_ollama
            if [[ "$install_ollama" == "y"* ]]; then
                if [ "$OS_TYPE" == "Darwin" ] && command -v brew &> /dev/null; then
                    brew install --cask ollama
                else
                    curl -fsSL https://ollama.com/install.sh | sh
                fi
            else
                echo -e "${YELLOW}  ⚠ Skipped. Manual install: https://ollama.com/download${NC}"
            fi
        else
            echo -e "${GREEN}Ollama is installed.${NC}"
        fi
    fi

    # ── Neither enabled ──
    if [ "$OLLAMA_ENABLED" != "true" ]; then
        echo -e "${YELLOW}No local LLM enabled in .config.${NC}"
        echo "  Set ENABLE_OLLAMA=true"
    fi

    ./scripts/manage_services.sh start
}

# ─────────────────────────────────────────────
# Step 5: Container runtime (OrbStack / Docker)
# ─────────────────────────────────────────────
detect_container_runtime() {
    show_progress "Detecting container runtime..."

    # OrbStack ships a docker-compatible CLI; test that first on macOS
    if [ "$OS_TYPE" == "Darwin" ]; then
        # OrbStack check: either `orb` CLI exists or docker provided by OrbStack
        if command -v orb &> /dev/null; then
            echo -e "${GREEN}OrbStack detected.${NC}"
        fi
    fi

    # Docker CLI reachable?
    if command -v docker &> /dev/null; then
        if docker info &> /dev/null 2>&1; then
            DOCKER_CMD="docker"
            echo -e "  Container runtime: ${GREEN}docker — running ✓${NC}"
            return 0
        else
            echo -e "  ${YELLOW}docker CLI found but the daemon is not running.${NC}"
            if [ "$OS_TYPE" == "Darwin" ]; then
                echo -e "  → Start OrbStack (open the app) or start Docker Desktop, then re-run install."
            else
                echo -e "  → Run: sudo systemctl start docker"
            fi
            echo -e "  ${YELLOW}n8n setup will be skipped — you can run it later with: ./install.sh n8n${NC}"
            return 1
        fi
    else
        echo -e "  ${YELLOW}No container runtime found (docker command missing).${NC}"
        if [ "$OS_TYPE" == "Darwin" ]; then
            echo -e "  → Install OrbStack (recommended, free): https://orbstack.dev"
            echo -e "    or Docker Desktop: https://docs.docker.com/desktop/install/mac-install/"
        else
            echo -e "  → Run: sudo apt install docker.io && sudo systemctl enable --now docker"
        fi
        echo -e "  ${YELLOW}n8n setup will be skipped — you can run it later with: ./install.sh n8n${NC}"
        return 1
    fi
}

# ─────────────────────────────────────────────
# Step 6: n8n via docker compose
# ─────────────────────────────────────────────
setup_n8n() {
    show_progress "Setting up n8n (workflow automation)..."

    if [ -z "$DOCKER_CMD" ]; then
        echo -e "${YELLOW}  Skipping n8n setup — no container runtime available.${NC}"
        return
    fi

    N8N_PORT=$(awk -F'=' '/^N8N_PORT[ ]*=/ {print $2}' .config 2>/dev/null | tr -d ' \r')
    [ -z "$N8N_PORT" ] && N8N_PORT="5679"
    N8N_URL="http://localhost:${N8N_PORT}"

    # Check if n8n container is already up
    if $DOCKER_CMD compose ps n8n 2>/dev/null | grep -q "running\|Up"; then
        echo -e "${GREEN}  n8n is already running at ${N8N_URL}${NC}"
    else
        echo "  n8n is not running."
        read -p "  Start n8n now via docker compose? (y/n): " start_n8n
        if [[ "$start_n8n" == "y"* ]]; then
            echo "  Starting n8n..."
            # Temporarily disable set -e for compose startup
            set +e
            $DOCKER_CMD compose up -d n8n
            COMPOSE_EXIT=$?
            set -e

            if [ $COMPOSE_EXIT -ne 0 ]; then
                echo -e "${RED}  ✗ docker compose up failed.${NC}"
                echo -e "    Manual fix: run 'docker compose up -d n8n' from the project root"
                echo -e "    Check logs: docker compose logs n8n"
                return
            fi

            # Wait for n8n to be healthy (up to 30s)
            echo -n "  Waiting for n8n to be ready..."
            for i in $(seq 1 15); do
                if curl -sf --max-time 2 "${N8N_URL}/healthz" > /dev/null 2>&1 || \
                   curl -sf --max-time 2 "${N8N_URL}" > /dev/null 2>&1; then
                    echo -e " ${GREEN}ready!${NC}"
                    break
                fi
                echo -n "."
                sleep 2
            done

            if ! curl -sf --max-time 2 "${N8N_URL}" > /dev/null 2>&1; then
                echo -e "\n${YELLOW}  n8n may still be starting. Check: ${N8N_URL}${NC}"
            fi
        else
            echo -e "${YELLOW}  Skipped. Start later with: docker compose up -d n8n${NC}"
            return
        fi
    fi

    # Write webhook URL to .config
    set_config_key "N8N_WEBHOOK_URL" "${N8N_URL}/webhook"
    echo -e "  N8N_WEBHOOK_URL set to: ${CYAN}${N8N_URL}/webhook${NC}"

    # Workflow import instructions — only show files that are new or changed
    # Track each workflow's last-changed sprint so we only flag what needs attention.
    # Format: "filename|Sprint-XX — reason"
    CHANGED_WORKFLOWS=(
        "morning-planning.json|Sprint-08 — webhook changed to /webhook/morning-plan"
    )
    STABLE_WORKFLOWS=(
        "universal_task_sync.json"
        "add-task.json"
        "backlog-digest.json"
    )

    echo ""
    echo -e "  ${BOLD}n8n workflows — what needs importing:${NC}"
    echo ""
    echo -e "  ${YELLOW}${BOLD}New / Updated (re-import these):${NC}"
    for entry in "${CHANGED_WORKFLOWS[@]}"; do
        file="${entry%%|*}"
        reason="${entry##*|}"
        echo -e "    ${YELLOW}↻  n8n-workflows/${file}${NC}"
        echo -e "       ${reason}"
    done
    echo ""
    echo -e "  ${GREEN}Already imported — no action needed:${NC}"
    for file in "${STABLE_WORKFLOWS[@]}"; do
        echo -e "    ${GREEN}✓  n8n-workflows/${file}${NC}"
    done
    echo ""
    echo -e "  ${BOLD}To re-import a workflow:${NC}"
    echo -e "  1. Open ${CYAN}${N8N_URL}${NC}"
    echo -e "  2. Open the existing workflow → top-right ⋯ menu → ${BOLD}Import from file${NC}"
    echo -e "     (this updates in place without losing your credentials)"
    echo -e "  3. Toggle ${BOLD}Active${NC} if it was active before"
}

# ─────────────────────────────────────────────
# Step 7: Configuration (.config keys)
# ─────────────────────────────────────────────
setup_configuration() {
    show_progress "System Configuration..."

    if [ ! -f ".config" ]; then
        cp config.template .config
        echo -e "${GREEN}Created .config from template.${NC}"
    else
        echo -e "${GREEN}Existing .config found.${NC}"
    fi

    if [ "$INSTALL_MODE" == "cloud" ]; then
        echo ""
        echo -e "${BLUE}--- Free Cloud API Keys (at least one required) ---${NC}"
    else
        echo ""
        echo -e "${BLUE}--- API Keys (all optional — local AI runs without these) ---${NC}"
    fi

    # Groq (free tier, fast inference — show first in cloud-only mode)
    CURRENT_GROQ=$(grep -E "^GROQ_API_KEY=" .config | cut -d'=' -f2- | tr -d ' ')
    if [ -z "$CURRENT_GROQ" ] || [[ "$CURRENT_GROQ" == *"your_"* ]]; then
        read -p "Groq API Key — free at console.groq.com [Enter to skip]: " groq_key
        if [ -n "$groq_key" ]; then
            set_config_key "GROQ_API_KEY" "$groq_key"
            set_config_key "ENABLE_GROQ" "true"
            echo -e "${GREEN}Groq key saved.${NC}"
        fi
    else
        echo -e "${GREEN}Groq key already configured.${NC}"
    fi

    # HuggingFace
    CURRENT_HF=$(grep -E "^HF_TOKEN=" .config | cut -d'=' -f2- | tr -d ' ')
    if [ -z "$CURRENT_HF" ] || [[ "$CURRENT_HF" == *"your_"* ]]; then
        read -p "HuggingFace Token — free at huggingface.co [Enter to skip]: " hf_key
        if [ -n "$hf_key" ]; then
            set_config_key "HF_TOKEN" "$hf_key"
            set_config_key "ENABLE_HUGGINGFACE" "true"
            echo -e "${GREEN}HuggingFace token saved.${NC}"
        fi
    else
        echo -e "${GREEN}HuggingFace token already configured.${NC}"
    fi

    echo ""
    echo -e "${BLUE}--- Paid Cloud API Keys (optional) ---${NC}"

    CURRENT_OPENAI=$(grep -E "^OPENAI_API_KEY=" .config | cut -d'=' -f2- | tr -d ' ')
    if [ -z "$CURRENT_OPENAI" ] || [[ "$CURRENT_OPENAI" == *"your_"* ]]; then
        read -p "OpenAI API Key (sk-proj-...) [Enter to skip]: " openai_key
        if [ -n "$openai_key" ]; then
            set_config_key "OPENAI_API_KEY" "$openai_key"
            set_config_key "ENABLE_OPENAI" "true"
            echo -e "${GREEN}OpenAI key saved.${NC}"
        fi
    else
        echo -e "${GREEN}OpenAI key already configured.${NC}"
    fi

    CURRENT_GEMINI=$(grep -E "^GEMINI_API_KEY=" .config | cut -d'=' -f2- | tr -d ' ')
    if [ -z "$CURRENT_GEMINI" ] || [[ "$CURRENT_GEMINI" == *"your_"* ]]; then
        read -p "Google Gemini API Key [Enter to skip]: " gemini_key
        if [ -n "$gemini_key" ]; then
            set_config_key "GEMINI_API_KEY" "$gemini_key"
            set_config_key "ENABLE_GEMINI" "true"
            echo -e "${GREEN}Gemini key saved.${NC}"
        fi
    else
        echo -e "${GREEN}Gemini key already configured.${NC}"
    fi

    CURRENT_CLAUDE=$(grep -E "^CLAUDE_API_KEY=" .config | cut -d'=' -f2- | tr -d ' ')
    if [ -z "$CURRENT_CLAUDE" ] || [[ "$CURRENT_CLAUDE" == *"your_"* ]]; then
        read -p "Anthropic Claude API Key [Enter to skip]: " claude_key
        if [ -n "$claude_key" ]; then
            set_config_key "CLAUDE_API_KEY" "$claude_key"
            set_config_key "ENABLE_CLAUDE" "true"
            echo -e "${GREEN}Claude key saved.${NC}"
        fi
    else
        echo -e "${GREEN}Claude key already configured.${NC}"
    fi

    echo ""
    echo -e "${BLUE}--- Folder Paths ---${NC}"
    CURRENT_WS=$(grep -E "^WORKSPACE_DIR=" .config | cut -d'=' -f2- | tr -d ' ')
    if [ -z "$CURRENT_WS" ] || [[ "$CURRENT_WS" == *"yourname"* ]]; then
        read -p "Path to your Obsidian/Markdown notes folder [Enter to skip]: " ws_path
        if [ -n "$ws_path" ]; then
            set_config_key "WORKSPACE_DIR" "$ws_path"
        fi
    else
        echo -e "${GREEN}WORKSPACE_DIR already set: $CURRENT_WS${NC}"
    fi

    CURRENT_LQ=$(grep -E "^LOGSEQ_DIR=" .config | cut -d'=' -f2- | tr -d ' ')
    if [ -z "$CURRENT_LQ" ] || [[ "$CURRENT_LQ" == *"yourname"* ]]; then
        read -p "Path to your LogSeq folder [Enter to skip]: " lq_path
        if [ -n "$lq_path" ]; then
            set_config_key "LOGSEQ_DIR" "$lq_path"
        fi
    else
        echo -e "${GREEN}LOGSEQ_DIR already set: $CURRENT_LQ${NC}"
    fi

    echo -e "${GREEN}Configuration complete.${NC}"
}

# ─────────────────────────────────────────────
# Step 8: Cron / background automation
# ─────────────────────────────────────────────
setup_automation() {
    show_progress "Automation & Cron Job Setup..."
    EXISTING_CRON=$(crontab -l 2>/dev/null | grep "cron_job.py" || true)

    if [ -n "$EXISTING_CRON" ]; then
        echo -e "${YELLOW}Existing cron job found:${NC}"
        echo -e "${BLUE}$EXISTING_CRON${NC}"
        read -p "Keep it? (y/n): " cron_ok
        if [[ "$cron_ok" != "y"* ]]; then
            crontab -l | grep -v "cron_job.py" | crontab -
            EXISTING_CRON=""
        fi
    fi

    if [ -z "$EXISTING_CRON" ]; then
        echo "Enable hourly background sync (LogSeq → Obsidian, reminders, tasks)?"
        read -p "Set up cron job? (y/n): " enable_cron
        if [[ "$enable_cron" == "y"* ]]; then
            VENV_PYTHON="$(pwd)/.venv/bin/python3"
            CRON_SCRIPT="$(pwd)/cron_job.py"
            CRON_LINE="0 * * * * cd $(pwd) && $VENV_PYTHON $CRON_SCRIPT >> $(pwd)/logs/cron_sync.log 2>&1"
            mkdir -p logs
            (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
            echo -e "${GREEN}Hourly sync enabled.${NC}"
        fi
    fi
}

# ─────────────────────────────────────────────
# Step 9: Service check summary + AI advice
# ─────────────────────────────────────────────
run_service_checks() {
    show_progress "Service Health Check..."

    ISSUES=()
    ADVICE=()

    # --- Python assistant verification ---
    echo -e "\n  ${BOLD}Checking services:${NC}"

    LMS_ENABLED=$(awk -F'=' '/^ENABLE_LM_STUDIO[ ]*=/ {print $2}' .config 2>/dev/null | tr -d ' \r')
    OLLAMA_ENABLED=$(awk -F'=' '/^ENABLE_OLLAMA[ ]*=/ {print $2}' .config 2>/dev/null | tr -d ' \r')
    GROQ_ENABLED=$(awk -F'=' '/^ENABLE_GROQ[ ]*=/ {print $2}' .config 2>/dev/null | tr -d ' \r')
    HF_ENABLED=$(awk -F'=' '/^ENABLE_HUGGINGFACE[ ]*=/ {print $2}' .config 2>/dev/null | tr -d ' \r')
    OLLAMA_OK=false

    if [ "$INSTALL_MODE" == "cloud" ]; then
        # --- Cloud-only: show which providers are configured ---
        echo -e "  ${CYAN}Cloud-only mode — local AI skipped.${NC}"
        if [ "$GROQ_ENABLED" == "true" ]; then
            echo -e "  ${GREEN}✓ Groq enabled${NC}"
        else
            echo -e "  ${YELLOW}⚠ Groq not configured (ENABLE_GROQ not set)${NC}"
        fi
        if [ "$HF_ENABLED" == "true" ]; then
            echo -e "  ${GREEN}✓ HuggingFace enabled${NC}"
        fi
    else
        # --- Ollama (primary local backend) ---
        if [ "$OLLAMA_ENABLED" == "true" ]; then
            OLLAMA_HOST=$(awk -F'=' '/^OLLAMA_HOST[ ]*=/ {print $2}' .config 2>/dev/null | tr -d ' \r')
            [ -z "$OLLAMA_HOST" ] && OLLAMA_HOST="http://localhost:11434"
            if curl -sf --max-time 3 "${OLLAMA_HOST}/api/tags" > /dev/null 2>&1; then
                echo -e "  ${GREEN}✓ Ollama API (${OLLAMA_HOST})${NC}"
                OLLAMA_OK=true
            else
                echo -e "  ${RED}✗ Ollama API unreachable (${OLLAMA_HOST})${NC}"
                ISSUES+=("Ollama API unreachable at ${OLLAMA_HOST}")
                ADVICE+=("Start Ollama: ollama serve   or open the Ollama app")
            fi
        fi
    fi

    # --- General AI assistant check (uses whichever backend is active) ---
    set +e
    PYTHONPATH=. .venv/bin/python3 scripts/check_ai_working.py > /tmp/ai_check.txt 2>&1
    AI_CHECK_EXIT=$?
    set -e

    if [ $AI_CHECK_EXIT -eq 0 ]; then
        echo -e "  ${GREEN}✓ AI assistant check passed${NC}"
    else
        echo -e "  ${RED}✗ AI assistant check failed${NC}"
        if [ "$INSTALL_MODE" == "cloud" ]; then
            ISSUES+=("No cloud LLM responding")
            ADVICE+=("Add at least one API key in .config and set ENABLE_GROQ=true (or ENABLE_GEMINI/OPENAI/CLAUDE=true)")
        else
            ISSUES+=("Ollama LLM not responding")
            ADVICE+=("Run: ollama serve   then: ollama pull <model>   (check OLLAMA_MODEL in .config)")
        fi
    fi

    # --- n8n ---
    N8N_PORT=$(awk -F'=' '/^N8N_PORT[ ]*=/ {print $2}' .config 2>/dev/null | tr -d ' \r')
    [ -z "$N8N_PORT" ] && N8N_PORT="5679"
    if curl -sf --max-time 3 "http://localhost:${N8N_PORT}" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ n8n (http://localhost:${N8N_PORT})${NC}"
    else
        echo -e "  ${YELLOW}⚠ n8n not reachable (http://localhost:${N8N_PORT})${NC}"
        ISSUES+=("n8n not running")
        if [ -n "$DOCKER_CMD" ]; then
            ADVICE+=("Run: docker compose up -d n8n   then open http://localhost:${N8N_PORT} and import workflows from n8n-workflows/")
        else
            ADVICE+=("Install a container runtime first (OrbStack or Docker), then: docker compose up -d n8n")
        fi
    fi

    # --- Container runtime ---
    if [ -n "$DOCKER_CMD" ]; then
        echo -e "  ${GREEN}✓ Container runtime (docker)${NC}"
    else
        echo -e "  ${YELLOW}⚠ Container runtime not available${NC}"
        ISSUES+=("No container runtime (Docker/OrbStack)")
        if [ "$OS_TYPE" == "Darwin" ]; then
            ADVICE+=("Install OrbStack (free, lightweight): https://orbstack.dev   or Docker Desktop: https://docs.docker.com/desktop/install/mac-install/")
        else
            ADVICE+=("Install Docker: sudo apt install docker.io && sudo systemctl enable --now docker")
        fi
    fi

    # --- Python API server (api_server.py) ---
    WEBHOOK_PORT=$(awk -F'=' '/^WEBHOOK_PORT[ ]*=/ {print $2}' .config 2>/dev/null | tr -d ' \r')
    [ -z "$WEBHOOK_PORT" ] && WEBHOOK_PORT="5678"
    if curl -sf --max-time 2 "http://localhost:${WEBHOOK_PORT}/health" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓ API server (http://localhost:${WEBHOOK_PORT})${NC}"
    else
        echo -e "  ${YELLOW}⚠ API server not running (http://localhost:${WEBHOOK_PORT})${NC}"
        ISSUES+=("Python API server not running (needed for n8n webhooks back to Python)")
        ADVICE+=("Start when needed: python api_server.py   (only required if using n8n Universal Task Sync)")
    fi

    # --- Summary ---
    echo ""
    if [ ${#ISSUES[@]} -eq 0 ]; then
        echo -e "  ${GREEN}${BOLD}All services healthy.${NC}"
    else
        echo -e "  ${YELLOW}${BOLD}Issues found (${#ISSUES[@]}):${NC}"
        for i in "${!ISSUES[@]}"; do
            echo -e "  ${RED}  [$(( i+1 ))] ${ISSUES[$i]}${NC}"
            echo -e "  ${CYAN}      → ${ADVICE[$i]}${NC}"
        done
    fi

    # --- AI-powered advice (Ollama only, when available and there are issues) ---
    if [ "$OLLAMA_OK" == "true" ] && [ ${#ISSUES[@]} -gt 0 ]; then
        echo ""
        echo -e "  ${BLUE}Asking Ollama for setup guidance...${NC}"

        ISSUE_LIST=$(printf '%s\n' "${ISSUES[@]}" | awk '{print NR". "$0}')
        PROMPT="You are a helpful assistant. The user just installed an AI agent assistant on their $(uname -s) machine. The following setup issues were detected:

${ISSUE_LIST}

Give a short, friendly, plain-text summary (no markdown) of what each issue means and the quickest way to fix it. Be concise — 2-3 sentences per issue maximum."

        ADVICE_TEXT=$(ask_ollama "$PROMPT")
        if [ -n "$ADVICE_TEXT" ]; then
            echo ""
            echo -e "  ${CYAN}${BOLD}AI Setup Advisor:${NC}"
            echo "$ADVICE_TEXT" | sed 's/^/  /'
        fi
    fi
}

# ─────────────────────────────────────────────
# Subcommand: ./install.sh n8n
# ─────────────────────────────────────────────
if [[ "$1" == "n8n" ]]; then
    detect_container_runtime || true
    setup_n8n
    run_service_checks
    exit 0
fi

# ─────────────────────────────────────────────
# Subcommand: ./install.sh upgrade
# ─────────────────────────────────────────────
if [[ "$1" == "upgrade" ]]; then
    check_upgrade
    setup_python_env
    setup_local_ai
    detect_container_runtime || true
    # Show workflow change notices (non-interactive — just prints what needs re-importing)
    setup_n8n
    # Check/update cron job if schedule or path has changed
    setup_automation
    echo -e "\n${BLUE}Verifying AI Assistant...${NC}"
    PYTHONPATH=. .venv/bin/python3 scripts/check_ai_working.py
    run_service_checks
    echo -e "${GREEN}Upgrade complete.${NC}"
    exit 0
fi

# ─────────────────────────────────────────────
# Subcommand: ./install.sh cron
# ─────────────────────────────────────────────
if [[ "$1" == "cron" ]]; then
    setup_automation
    exit 0
fi

# ─────────────────────────────────────────────
# Full installation
# ─────────────────────────────────────────────
check_upgrade
select_install_mode
check_dependencies
setup_python_env
setup_local_ai
detect_container_runtime || true
setup_n8n
setup_configuration
setup_automation
run_service_checks

echo -e "\n${GREEN}${BOLD}🎉 Installation complete.${NC}"
echo -e "  Start the assistant:   ${YELLOW}./run.sh${NC}"
echo -e "  Run tests:             ${YELLOW}make test${NC}"
echo -e "  Service health:        ${YELLOW}python scripts/status.py${NC}"
echo ""
