#!/bin/bash
# Manage local AI services (Ollama)
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

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
    curl -s -X POST http://localhost:11434/api/generate -d "{\"model\":\"$MODEL\", \"prompt\":\"hi\", \"stream\":false}" -m 120 > /dev/null
    echo -e "${GREEN}Model warmed and ready.${NC}"
}

check_services() {
    if pgrep -x "ollama" > /dev/null; then
        echo -e "Ollama: ${GREEN}RUNNING${NC}"
    else
        echo -e "Ollama: ${RED}STOPPED${NC}"
        start_ollama
    fi
}

case "$1" in
    start)
        start_ollama
        ;;
    check) check_services ;;
    *) echo "Usage: $0 {start|check}"; exit 1 ;;
esac
