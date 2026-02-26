#!/bin/bash

# Configuration and Installation Script
# This script sets up the local environment for the AI Agent Assistant.

echo "--- AI Agent Assistant: Starting Installation ---"

# 1. Create a virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
else
    echo "Virtual environment already exists."
fi

# 2. Activate the virtual environment
source .venv/bin/activate

# 3. Install Python dependencies
if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies..."
    pip install -r requirements.txt
else
    echo "Warning: requirements.txt not found. Skipping dependency installation."
fi

# 4. Generate the .config file from the template
if [ ! -f ".config" ]; then
    echo "Generating .config file from template..."
    
    # Check if we have secrets in environment variables (e.g., from a CI environment)
    # and use them if available, otherwise use placeholders.
    
    GEMINI_API_KEY=${GEMINI_API_KEY:-"your_gemini_api_key_here"}
    OPENCLAW_API_KEY=${OPENCLAW_API_KEY:-"your_openclaw_api_key_here"}
    
    cp config.template .config
    
    # (Optional) We could use 'sed' to replace values if we wanted to auto-inject from env vars:
    # sed -i "s/your_gemini_api_key_here/$GEMINI_API_KEY/" .config
    # sed -i "s/your_openclaw_api_key_here/$OPENCLAW_API_KEY/" .config
    
    echo "SUCCESS: .config file created. Please open it and fill in your actual API keys."
else
    echo ".config file already exists. Skipping generation."
fi

# 5. Reminder for Google Calendar credentials
if [ ! -f "credentials.json" ]; then
    echo "REMINDER: You still need to place your 'credentials.json' from Google Cloud in the root directory."
fi

echo "--- Installation Complete ---"
echo "To start the assistant, run: source .venv/bin/activate && python3 main.py"
