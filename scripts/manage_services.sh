#!/bin/bash
# Manage local AI services (Ollama & OpenClaw)
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

OS_TYPE=$(uname -s)

start_ollama() {
    if pgrep -x "ollama" > /dev/null; then
        echo -e "${GREEN}Ollama is already running.${NC}"
    else
        echo -e "${YELLOW}Starting Ollama...${NC}"
        ollama serve > /dev/null 2>&1 &
        sleep 5
        if pgrep -x "ollama" > /dev/null; then
            echo -e "${GREEN}Ollama started successfully.${NC}"
        else
            echo -e "${RED}Failed to start Ollama. Please start it manually.${NC}"
        fi
    fi

    # Check for configured model (robust parsing)
    MODEL=$(awk -F'=' '/^OLLAMA_MODEL[ ]*=/ {print $2}' .config | tr -d ' \r')
    if [ -z "$MODEL" ]; then 
        echo -e "${YELLOW}Warning: OLLAMA_MODEL not found in .config. Defaulting to llama3.${NC}"
        MODEL="llama3"
    fi
    
    if ! ollama list | grep -q "$MODEL"; then
        echo -e "${YELLOW}Model '$MODEL' not found. Pulling now (this may take a few minutes)...${NC}"
        ollama pull "$MODEL"
    else
        echo -e "${GREEN}Model '$MODEL' is ready.${NC}"
    fi

    # --- Warm the model ---
    echo -e "${YELLOW}Warming model '$MODEL' (first-time load into memory)...${NC}"
    # Simple prompt to force loading
    curl -s -X POST http://localhost:11434/api/generate -d "{\"model\":\"$MODEL\", \"prompt\":\"hi\", \"stream\":false}" -m 120 > /dev/null
    echo -e "${GREEN}Model warmed and ready.${NC}"
}

start_openclaw() {
    if command -v openclaw &> /dev/null; then
        if lsof -Pi :18789 -sTCP:LISTEN -t >/dev/null ; then
            echo -e "${GREEN}OpenClaw is already running (Port 18789).${NC}"
        else
            echo -e "${YELLOW}Starting OpenClaw...${NC}"
            # Check if OpenClaw is installed as a daemon
            if [ "$OS_TYPE" == "Darwin" ]; then
                if launchctl list | grep -q "ai.openclaw.gateway"; then
                    launchctl start ai.openclaw.gateway
                else
                    openclaw gateway --port 18789 > /dev/null 2>&1 &
                fi
            else
                 # Linux (Systemd)
                 if systemctl --user is-active --quiet openclaw-gateway; then
                     systemctl --user start openclaw-gateway
                 else
                     openclaw gateway --port 18789 > /dev/null 2>&1 &
                 fi
            fi

            # Wait for port 18789 to be open
            echo "Waiting for OpenClaw to start on port 18789..."
            local max_retries=12 # 1 minute total
            local count=0
            while [ $count -lt $max_retries ]; do
                if lsof -Pi :18789 -sTCP:LISTEN -t >/dev/null ; then
                    echo -e "${GREEN}OpenClaw started successfully.${NC}"
                    return 0
                fi
                sleep 5
                ((count++))
            done
            echo -e "${RED}Failed to start OpenClaw or port is busy.${NC}"
            return 1
        fi
    else
        echo -e "${RED}Error: OpenClaw CLI not found.${NC}"
        return 1
    fi
}

check_services() {
    if pgrep -x "ollama" > /dev/null; then
        echo -e "Ollama: ${GREEN}RUNNING${NC}"
    else
        echo -e "Ollama: ${RED}STOPPED${NC}"
        start_ollama
    fi
    
    if lsof -Pi :18789 -sTCP:LISTEN -t >/dev/null ; then
        echo -e "OpenClaw: ${GREEN}RUNNING${NC}"
    else
        echo -e "OpenClaw: ${RED}STOPPED${NC}"
        start_openclaw
    fi
}

case "$1" in
    start) 
        start_ollama
        start_openclaw
        ;;
    check) check_services ;;
    *) echo "Usage: $0 {start|check}"; exit 1 ;;
esac
