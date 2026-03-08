#!/bin/bash

# AI Agent Assistant: Guided Installation Script
# Supports macOS (Darwin) and Linux (Ubuntu).

set -e

# ANSI Color Codes for better UI
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

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
TOTAL_STEPS=6
CURRENT_STEP=0

show_progress() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    PERCENT=$((CURRENT_STEP * 100 / TOTAL_STEPS))
    echo -e "${YELLOW}[Step $CURRENT_STEP/$TOTAL_STEPS - $PERCENT%] $1${NC}"
}

# 0. Upgrade Check
check_upgrade() {
    show_progress "Checking for updates..."
    if [ -d ".git" ]; then
        echo -e "${BLUE}Git repository detected. Checking for remote updates...${NC}"
        git fetch origin --quiet
        LOCAL=$(git rev-parse HEAD)
        REMOTE=$(git rev-parse @{u})
        if [ "$LOCAL" != "$REMOTE" ]; then
            echo -e "${YELLOW}New updates available!${NC}"
            read -p "Would you like to upgrade to the latest version? (y/n): " do_upgrade
            if [[ "$do_upgrade" == "y"* ]]; then
                git pull origin main --quiet
                echo -e "${GREEN}Project updated successfully.${NC}"
            fi
        else
            echo -e "${GREEN}Project is already up to date.${NC}"
        fi
    fi
}

# 1. Dependency Checks & Auto-Installation
check_dependencies() {
    show_progress "Checking System Dependencies..."
    
    # Try to find an existing Python 3.11+
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
            echo "Installing Python 3.12 via Homebrew..."
            brew install python@3.12
            PYTHON_CMD=$(brew --prefix)/bin/python3.12
        else
            echo "Installing Python 3.12 via apt..."
            sudo apt update
            sudo apt install software-properties-common -y
            sudo add-apt-repository ppa:deadsnakes/ppa -y
            sudo apt update
            sudo apt install python3.12 python3.12-venv -y
            PYTHON_CMD="/usr/bin/python3.12"
        fi
    fi

    if [ -z "$PYTHON_CMD" ] || ! $PYTHON_CMD --version &> /dev/null; then
        echo -e "${RED}Error: Failed to secure a Python 3.11+ environment.${NC}"
        exit 1
    fi

    echo -e "Using Python: ${GREEN}$($PYTHON_CMD --version)${NC}"
    # Export for use in venv creation
    export FINAL_PYTHON=$PYTHON_CMD

    # Check Git
    if ! command -v git &> /dev/null; then
        echo -e "${RED}Error: Git is not installed.${NC}"
        exit 1
    fi
    echo -e "${GREEN}System dependencies are OK.${NC}"
}

# 2. Virtual Environment & Requirements
setup_python_env() {
    show_progress "Setting up Python Environment..."
    if [ ! -d ".venv" ]; then
        echo "Creating virtual environment using $FINAL_PYTHON..."
        $FINAL_PYTHON -m venv .venv
    fi
    
    source .venv/bin/activate
    echo "Upgrading package manager (pip)..."
    pip install --quiet --upgrade pip
    
    echo "Installing required AI libraries (this may take a minute)..."
    if [ "$OS_TYPE" == "Linux" ]; then
        grep -v "pyobjc" requirements.txt > requirements_linux.txt
        pip install --quiet -r requirements_linux.txt
        rm requirements_linux.txt
    else
        pip install --quiet -r requirements.txt
    fi
    echo -e "${GREEN}Python environment is ready.${NC}"
}

# 3. Ollama & OpenClaw Installation (Local AI)
setup_local_ai() {
    show_progress "Checking Local AI (Ollama & OpenClaw)..."
    chmod +x scripts/manage_services.sh
    
    # Ollama
    if ! command -v ollama &> /dev/null; then
        echo "Ollama not found. It allows you to run AI models privately on your machine."
        read -p "Would you like to install Ollama now? (y/n): " install_ollama
        if [[ "$install_ollama" == "y"* ]]; then
            if [ "$OS_TYPE" == "Darwin" ]; then
                if command -v brew &> /dev/null; then
                    brew install --cask ollama
                else
                    echo "Downloading Ollama for Mac..."
                    curl -fsSL https://ollama.com/install.sh | sh
                fi
            else
                curl -fsSL https://ollama.com/install.sh | sh
            fi
        fi
    else
        echo -e "${GREEN}Ollama is already installed.${NC}"
    fi

    # OpenClaw (Node-based)
    if ! command -v node &> /dev/null; then
        echo -e "${YELLOW}Node.js not found. Node.js >= 22 is required for OpenClaw.${NC}"
        if [ "$OS_TYPE" == "Darwin" ]; then
             if command -v brew &> /dev/null; then
                 echo "Installing Node.js 22 via Homebrew..."
                 brew install node@22
                 brew link --force --overwrite node@22
             fi
        fi
    else
        NODE_VER=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
        if [ "$NODE_VER" -lt 22 ]; then
            echo -e "${YELLOW}Node.js version is $NODE_VER. Node.js >= 22 is required for OpenClaw.${NC}"
            if [ "$OS_TYPE" == "Darwin" ] && command -v brew &> /dev/null; then
                 echo "Upgrading Node.js to 22 via Homebrew..."
                 brew install node@22
                 brew link --force --overwrite node@22
            fi
        fi
    fi

    if ! command -v openclaw &> /dev/null; then
        echo "OpenClaw not found. It allows for more advanced agentic reasoning."
        read -p "Would you like to install OpenClaw now? (y/n): " install_oc
        if [[ "$install_oc" == "y"* ]]; then
            echo "Installing OpenClaw via official script..."
            curl -fsSL https://openclaw.ai/install.sh | bash

            # Run onboarding with daemon installation
            echo -e "${YELLOW}Launching OpenClaw Onboarding...${NC}"
            echo -e "${BLUE}Please follow the instructions in the new terminal window if it opens.${NC}"
            openclaw onboard --install-daemon
        fi
    else
        echo -e "${GREEN}OpenClaw is already installed.${NC}"
        # Ensure OpenClaw gateway is installed as a persistent background service
        if openclaw gateway status 2>&1 | grep -q "not loaded\|not installed\|Service not installed"; then
            echo -e "${YELLOW}Installing OpenClaw gateway as a background service...${NC}"
            openclaw gateway install
            openclaw gateway start 2>/dev/null || true
            echo -e "${GREEN}OpenClaw gateway service installed.${NC}"
        elif openclaw gateway status 2>&1 | grep -q "not running\|stopped"; then
            echo -e "${YELLOW}Starting OpenClaw gateway service...${NC}"
            openclaw gateway start 2>/dev/null || launchctl start ai.openclaw.gateway 2>/dev/null || true
        else
            echo -e "${GREEN}OpenClaw gateway service is active.${NC}"
        fi
    fi
    
    ./scripts/manage_services.sh start
}

# Helper: update or append a KEY=value in .config
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

# Helper: update OpenClaw auth-profiles.json with a provider API key
set_openclaw_provider_key() {
    local provider="$1"
    local api_key="$2"
    local profiles_file="$HOME/.openclaw/agents/main/agent/auth-profiles.json"
    if [ ! -f "$profiles_file" ]; then return; fi
    python3 - "$profiles_file" "$provider" "$api_key" <<'PYEOF'
import json, sys
path, provider, key = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path) as f:
    data = json.load(f)
profile_key = f"{provider}:default"
data.setdefault("profiles", {})[profile_key] = {
    "type": "api_key", "provider": provider, "key": key
}
with open(path, "w") as f:
    json.dump(data, f, indent=2)
PYEOF
}

# 4. Configuration (Web Wizard or CLI)
setup_configuration() {
    show_progress "System Configuration..."

    if [ ! -f ".config" ]; then
        cp config.template .config
        echo -e "${GREEN}Created .config from template.${NC}"
    else
        echo -e "${GREEN}Existing .config found.${NC}"
    fi

    echo ""
    echo -e "${BLUE}--- API Key Setup ---${NC}"
    echo "The assistant uses OpenClaw as its primary AI gateway (supports OpenAI, local models, etc.)"
    echo "You need at least one API key to get started."
    echo ""

    # OpenAI (primary/recommended)
    CURRENT_OPENAI=$(grep -E "^OPENAI_API_KEY=" .config | cut -d'=' -f2- | tr -d ' ')
    if [ -z "$CURRENT_OPENAI" ] || [[ "$CURRENT_OPENAI" == *"your_"* ]]; then
        read -p "OpenAI API Key (sk-proj-...) [Enter to skip]: " openai_key
        if [ -n "$openai_key" ]; then
            set_config_key "OPENAI_API_KEY" "$openai_key"
            set_config_key "ENABLE_OPENAI" "true"
            set_config_key "OPENCLAW_MODEL" "openai/gpt-4o-mini"
            set_openclaw_provider_key "openai" "$openai_key"
            echo -e "${GREEN}OpenAI API key saved and configured as primary model.${NC}"
        else
            echo -e "${YELLOW}Skipped. You can add it later with: /settings set OPENAI_API_KEY sk-proj-...${NC}"
        fi
    else
        echo -e "${GREEN}OpenAI API key already configured.${NC}"
    fi

    # Gemini (optional)
    CURRENT_GEMINI=$(grep -E "^GEMINI_API_KEY=" .config | cut -d'=' -f2- | tr -d ' ')
    if [ -z "$CURRENT_GEMINI" ] || [[ "$CURRENT_GEMINI" == *"your_"* ]]; then
        read -p "Google Gemini API Key [Enter to skip]: " gemini_key
        if [ -n "$gemini_key" ]; then
            set_config_key "GEMINI_API_KEY" "$gemini_key"
            set_config_key "ENABLE_GEMINI" "true"
            echo -e "${GREEN}Gemini API key saved.${NC}"
        fi
    else
        echo -e "${GREEN}Gemini API key already configured.${NC}"
    fi

    # Claude (optional)
    CURRENT_CLAUDE=$(grep -E "^CLAUDE_API_KEY=" .config | cut -d'=' -f2- | tr -d ' ')
    if [ -z "$CURRENT_CLAUDE" ] || [[ "$CURRENT_CLAUDE" == *"your_"* ]]; then
        read -p "Anthropic Claude API Key [Enter to skip]: " claude_key
        if [ -n "$claude_key" ]; then
            set_config_key "CLAUDE_API_KEY" "$claude_key"
            set_config_key "ENABLE_CLAUDE" "true"
            echo -e "${GREEN}Claude API key saved.${NC}"
        fi
    else
        echo -e "${GREEN}Claude API key already configured.${NC}"
    fi

    echo ""
    echo -e "${BLUE}--- Folder Paths ---${NC}"
    read -p "Path to your Obsidian/Markdown notes folder [Enter to skip]: " ws_path
    if [ -n "$ws_path" ]; then
        set_config_key "WORKSPACE_DIR" "$ws_path"
    fi

    echo -e "${GREEN}Configuration complete. You can update keys any time with /settings in chat.${NC}"
}

# 5. Background Automation (Cron)
setup_automation() {
    show_progress "Automation & Cron Job Setup..."
    EXISTING_CRON=$(crontab -l 2>/dev/null | grep "cron_job.py" || true)
    
    if [ -n "$EXISTING_CRON" ]; then
        echo -e "${YELLOW}An existing cron job for this project was found:${NC}"
        echo -e "${BLUE}$EXISTING_CRON${NC}"
        read -p "Is this cron job still okay? (y/n): " cron_ok
        if [[ "$cron_ok" != "y"* ]]; then
            echo "Removing old cron job..."
            crontab -l | grep -v "cron_job.py" | crontab -
            EXISTING_CRON=""
        fi
    fi

    if [ -z "$EXISTING_CRON" ]; then
        echo "I can set up a 'Cron Job' to automatically sync your tasks every hour."
        read -p "Enable hourly background sync? (y/n): " enable_cron
        if [[ "$enable_cron" == "y"* ]]; then
            VENV_PYTHON="$(pwd)/.venv/bin/python3"
            CRON_SCRIPT="$(pwd)/cron_job.py"
            CRON_LINE="0 * * * * cd $(pwd) && $VENV_PYTHON $CRON_SCRIPT >> $(pwd)/logs/cron_sync.log 2>&1"
            mkdir -p logs
            (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
            echo -e "${GREEN}Background sync enabled.${NC}"
        fi
    fi
}

# Main Execution
if [[ "$1" == "upgrade" ]]; then
    check_upgrade
    setup_python_env
    setup_local_ai
    echo -e "\n${BLUE}Verifying AI Assistant...${NC}"
    PYTHONPATH=. .venv/bin/python3 scripts/check_ai_working.py
    echo -e "${GREEN}Upgrade complete.${NC}"
    exit 0
elif [[ "$1" == "cron" ]]; then
    setup_automation
    exit 0
fi

check_upgrade
check_dependencies
setup_python_env
setup_local_ai
setup_configuration
setup_automation

echo -e "\n${BLUE}[6/6] Verifying AI Assistant...${NC}"
if ! PYTHONPATH=. .venv/bin/python3 scripts/check_ai_working.py; then
    echo -e "${YELLOW}Verification failed. Attempting to repair services...${NC}"
    ./scripts/manage_services.sh start
    echo -e "${BLUE}Re-verifying...${NC}"
    PYTHONPATH=. .venv/bin/python3 scripts/check_ai_working.py || echo -e "${RED}Verification failed again. Please check Ollama logs or your .config.${NC}"
fi

echo -e "\n${GREEN}🎉 SUCCESS! AI Agent Assistant is installed.${NC}"
echo -e "To start the dashboard, run: ${YELLOW}make run-ui${NC}"
echo -e "To chat with your agent, run: ${YELLOW}make run-chat${NC}"
echo ""
