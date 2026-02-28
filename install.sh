#!/bin/bash

# Configuration and Installation Script
# This script sets up the local environment for the AI Agent Assistant.
# It works on both macOS (Darwin) and Linux (Ubuntu).

set -e

echo "--- AI Agent Assistant: Starting Installation/Upgrade ---"

# Detect OS
OS_TYPE=$(uname -s)
echo "Detected OS: $OS_TYPE"

# 1. Environment Check
check_env() {
    echo "Checking for core dependencies..."
    if ! command -v python3 &> /dev/null; then
        echo "Error: python3 not found. Please install Python 3.10+."
        exit 1
    fi
    if ! command -v git &> /dev/null; then
        echo "Error: git not found. Please install git."
        exit 1
    fi
    echo "Core dependencies OK."
}

# 2. Upgrade Function
upgrade_solution() {
    echo "Upgrading AI Agent Assistant..."
    if [ -d ".git" ]; then
        echo "Fetching latest code from repository..."
        git pull
    fi
    
    if [ -d ".venv" ]; then
        echo "Updating Python dependencies..."
        source .venv/bin/activate
        pip install --upgrade pip
        pip install -r requirements.txt
    fi
    echo "Upgrade complete."
}

# 3. Setup Cron Job
setup_cron() {
    echo "Setting up a regular check using the agents..."
    
    # Get the absolute path to the virtual environment's python
    VENV_PYTHON="$(pwd)/.venv/bin/python3"
    CRON_SCRIPT="$(pwd)/cron_job.py"
    LOG_FILE="$(pwd)/logs/cron_sync.log"
    
    mkdir -p "$(pwd)/logs"
    
    # Create the cron line (runs every hour)
    CRON_LINE="0 * * * * cd $(pwd) && $VENV_PYTHON $CRON_SCRIPT >> $LOG_FILE 2>&1"
    
    # Check if the cron job already exists
    if crontab -l 2>/dev/null | grep -q "$CRON_SCRIPT"; then
        echo "Cron job already exists. Updating..."
        (crontab -l | grep -v "$CRON_SCRIPT"; echo "$CRON_LINE") | crontab -
    else
        echo "Adding new cron job..."
        (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
    fi
    echo "Cron job scheduled (runs hourly). Logs available in logs/cron_sync.log"
}

# Parse Arguments
COMMAND=$1

check_env

# If already installed and no command provided, ask if user wants to upgrade
if [ -z "$COMMAND" ] && [ -d ".venv" ] && [ -f ".config" ]; then
    read -p "Existing installation detected. Would you like to check for updates? (y/n): " want_upgrade
    if [[ "$want_upgrade" == "y"* ]]; then
        upgrade_solution
    fi
fi

if [ "$COMMAND" == "upgrade" ]; then
    upgrade_solution
    exit 0
fi

if [ "$COMMAND" == "cron" ]; then
    setup_cron
    exit 0
fi

# Standard Installation flow (if not already handled)

# 1. Install/Check Ollama
echo "Checking for Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "Ollama is not installed. Installing Ollama..."
    if [ "$OS_TYPE" == "Darwin" ]; then
        if command -v brew &> /dev/null; then
            brew install --cask ollama
        else
            curl -fsSL https://ollama.com/install.sh | sh
        fi
    else
        curl -fsSL https://ollama.com/install.sh | sh
    fi
    echo "Ollama installed successfully."
else
    echo "Ollama is already installed."
fi

# Ensure default model is present if Ollama is running
if command -v ollama &> /dev/null; then
    echo "Ensuring Ollama model 'llama3' is available..."
    # We use '|| true' because ollama might not be running yet, which is fine for now
    ollama pull llama3 || echo "Note: Could not pull llama3 automatically. Make sure Ollama app is running."
fi

# 2. Virtual environment setup
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# 3. Activate and Install Dependencies
source .venv/bin/activate
pip install --upgrade pip

if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies..."
    if [ "$OS_TYPE" == "Linux" ]; then
        grep -v "pyobjc" requirements.txt > requirements_linux.txt
        pip install -r requirements_linux.txt
        rm requirements_linux.txt
    else
        pip install -r requirements.txt
    fi
fi

# 4. Configuration
if [ ! -f ".config" ]; then
    echo "Generating .config file from template..."
    cp config.template .config
    
    echo "--- System Configuration ---"
    read -p "Enter your Google Gemini API Key: " gemini_key
    read -p "Enter your Google Calendar ID (default: primary): " calendar_id
    read -p "Enter your Obsidian Workspace Path: " workspace_dir
    read -p "Enter your LogSeq Graph Path: " logseq_dir

    gemini_key=${gemini_key:-"your_gemini_api_key_here"}
    calendar_id=${calendar_id:-"primary"}
    workspace_dir=${workspace_dir:-"/path/to/your/markdown/notes"}
    logseq_dir=${logseq_dir:-"/path/to/your/logseq/graph"}

    update_config() {
        sed "s|$1=.*|$1=$2|" .config > .config.tmp && mv .config.tmp .config
    }

    update_config "GEMINI_API_KEY" "$gemini_key"
    update_config "CALENDAR_ID" "$calendar_id"
    update_config "WORKSPACE_DIR" "$workspace_dir"
    update_config "LOGSEQ_DIR" "$logseq_dir"
fi

# 5. Background Sync Option
if ! crontab -l 2>/dev/null | grep -q "cron_job.py"; then
    read -p "Would you like to enable automated hourly background sync (cron)? (y/n): " enable_cron
    if [[ "$enable_cron" == "y"* ]]; then
        setup_cron
    fi
fi

echo "--- Installation Complete ---"
echo "To start the assistant: source .venv/bin/activate && python3 main.py"
echo "To upgrade in the future: ./install.sh upgrade"
