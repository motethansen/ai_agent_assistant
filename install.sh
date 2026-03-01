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

# 1. Dependency Checks (Python & Git)
check_dependencies() {
    echo -e "${BLUE}[1/5] Checking System Dependencies...${NC}"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Error: Python 3 is not installed.${NC}"
        if [ "$OS_TYPE" == "Darwin" ]; then
            echo -e "Please install Python 3.11+ from ${YELLOW}https://www.python.org/downloads/macos/${NC}"
        else
            echo -e "Please run: ${YELLOW}sudo apt update && sudo apt install python3.11 python3.11-venv${NC}"
        fi
        exit 1
    fi

    # Check version 3.11 or higher
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 11 ]); then
        echo -e "${RED}Error: Python $PYTHON_VERSION detected. Minimum version 3.11 required.${NC}"
        echo -e "Please upgrade to Python 3.11 or higher to ensure compatibility with Google AI libraries."
        exit 1
    fi
    
    echo -e "Python Version: ${GREEN}$PYTHON_VERSION${NC} (OK)"

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
        echo "Creating virtual environment (this keeps your system clean)..."
        python3 -m venv .venv
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
