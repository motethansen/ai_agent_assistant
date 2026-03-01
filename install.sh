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

# 1. Dependency Checks & Auto-Installation
check_dependencies() {
    echo -e "${BLUE}[1/5] Checking System Dependencies...${NC}"
    
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
    echo -e "\n${BLUE}[2/5] Setting up Python Environment...${NC}"
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

# 3. Ollama Installation (Local AI)
setup_ollama() {
    echo -e "\n${BLUE}[3/5] Checking Local AI (Ollama)...${NC}"
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
}

# 4. Configuration (Web Wizard or CLI)
setup_configuration() {
    echo -e "\n${BLUE}[4/5] System Configuration...${NC}"
    
    if [ ! -f ".config" ]; then
        echo "I will now help you configure your API keys and folder paths."
        echo "I recommend using the ${GREEN}Web Setup Wizard${NC} for a better experience."
        read -p "Launch Web Setup Wizard? (y/n): " use_wizard
        
        if [[ "$use_wizard" == "y"* ]]; then
            echo -e "${YELLOW}Launching Setup Wizard in your browser...${NC}"
            .venv/bin/streamlit run setup_wizard.py
            exit 0
        else
            echo "Proceeding with manual CLI configuration..."
            cp config.template .config
            # Basic CLI config logic (shortened for brevity)
            read -p "Enter Gemini API Key: " gkey
            sed -i.bak "s|GEMINI_API_KEY=.*|GEMINI_API_KEY=$gkey|" .config && rm .config.bak
        fi
    else
        echo -e "${GREEN}Existing configuration (.config) found.${NC}"
    fi
}

# 5. Background Automation (Cron)
setup_automation() {
    echo -e "\n${BLUE}[5/5] Automation (Optional)...${NC}"
    if ! crontab -l 2>/dev/null | grep -q "cron_job.py"; then
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
check_dependencies
setup_python_env
setup_ollama
setup_configuration
setup_automation

echo -e "\n${GREEN}🎉 SUCCESS! AI Agent Assistant is installed.${NC}"
echo -e "To start the dashboard, run: ${YELLOW}make run-ui${NC}"
echo -e "To chat with your agent, run: ${YELLOW}make run-chat${NC}"
echo ""
