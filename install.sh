#!/bin/bash

# Configuration and Installation Script
# This script sets up the local environment for the AI Agent Assistant.

echo "--- AI Agent Assistant: Starting Installation ---"

# 1. Install Ollama if not present
echo "Checking for Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "Ollama is not installed. Installing Ollama..."
    # For macOS (darwin) or Linux
    if [[ "$OSTYPE" == "darwin"* ]]; then
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

# Start Ollama service in background if not running (optional)
# We assume the user can start it or we could use brew services start ollama.

# 2. Create a virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
else
    echo "Virtual environment already exists."
fi

# 3. Activate the virtual environment
source .venv/bin/activate

# 4. Install Python dependencies
if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies from requirements.txt..."
    pip install -r requirements.txt
else
    echo "Warning: requirements.txt not found. Skipping dependency installation."
fi

# 5. Install OpenClaw
echo "Checking for OpenClaw module..."
# Installing OpenClaw Python package
pip install openclaw

# 6. Generate the .config file and ask user for configuration
if [ ! -f ".config" ]; then
    echo "Generating .config file from template..."
    cp config.template .config
    
    echo "--- System Configuration ---"
    echo "Please provide your API keys and settings. Press ENTER to skip and use defaults/placeholders."

    read -p "Enter your Google Gemini API Key: " gemini_key
    read -p "Enter your OpenClaw API Key: " openclaw_key
    read -p "Enter your Google Calendar ID (default: primary): " calendar_id
    read -p "Enter your Apple Reminders List Name (default: Reminders): " reminders_list
    read -p "Enter your Markdown Workspace Path: " workspace_dir

    # Default fallbacks
    gemini_key=${gemini_key:-"your_gemini_api_key_here"}
    openclaw_key=${openclaw_key:-"your_openclaw_api_key_here"}
    calendar_id=${calendar_id:-"primary"}
    reminders_list=${reminders_list:-"Reminders"}
    workspace_dir=${workspace_dir:-"/path/to/your/markdown/notes"}

    # Update the .config file
    # Using sed to replace the placeholder values
    sed -i.bak "s|GEMINI_API_KEY=.*|GEMINI_API_KEY=$gemini_key|" .config
    sed -i.bak "s|OPENCLAW_API_KEY=.*|OPENCLAW_API_KEY=$openclaw_key|" .config
    sed -i.bak "s|CALENDAR_ID=.*|CALENDAR_ID=$calendar_id|" .config
    sed -i.bak "s|APPLE_REMINDERS_LIST=.*|APPLE_REMINDERS_LIST=$reminders_list|" .config
    sed -i.bak "s|WORKSPACE_DIR=.*|WORKSPACE_DIR=$workspace_dir|" .config
    
    # Remove the backup file created by sed on macOS
    rm -f .config.bak
    
    echo "SUCCESS: .config file created and updated."
else
    echo ".config file already exists. Skipping generation."
fi

# 7. Reminder for Google Calendar credentials
if [ ! -f "credentials.json" ]; then
    echo "REMINDER: You still need to place your 'credentials.json' from Google Cloud in the root directory."
fi

echo "--- Installation Complete ---"
echo "To start the assistant, run: source .venv/bin/activate && python3 main.py"
