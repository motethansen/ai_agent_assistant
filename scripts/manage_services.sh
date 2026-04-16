#!/bin/bash
# Manage local AI services (Ollama, LM Studio)
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

start_ollama() {
    # Skip if Ollama is disabled in config
    OLLAMA_ENABLED=$(awk -F'=' '/^ENABLE_OLLAMA[ ]*=/ {print $2}' .config 2>/dev/null | tr -d ' \r')
    if [ "$OLLAMA_ENABLED" == "false" ]; then
        echo -e "${YELLOW}Ollama is disabled (ENABLE_OLLAMA=false) — skipping.${NC}"
        return
    fi

    if ! command -v ollama > /dev/null 2>&1; then
        echo -e "${YELLOW}Ollama not installed — skipping.${NC}"
        return
    fi

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
            return
        fi
    fi

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

    echo -e "${YELLOW}Warming model '$MODEL'...${NC}"
    curl -s -X POST http://localhost:11434/api/generate -d "{\"model\":\"$MODEL\", \"prompt\":\"hi\", \"stream\":false}" -m 120 > /dev/null
    echo -e "${GREEN}Ollama model warmed and ready.${NC}"
}

check_services() {
    # Ollama (primary local backend)
    OLLAMA_ENABLED=$(awk -F'=' '/^ENABLE_OLLAMA[ ]*=/ {print $2}' .config 2>/dev/null | tr -d ' \r')
    if [ "$OLLAMA_ENABLED" == "true" ]; then
        if pgrep -x "ollama" > /dev/null; then
            echo -e "Ollama: ${GREEN}RUNNING${NC}"
        else
            echo -e "Ollama: ${RED}STOPPED${NC}"
            start_ollama
        fi
    fi
}

case "$1" in
    start)
        # Start whichever backends are enabled
        OLLAMA_ENABLED=$(awk -F'=' '/^ENABLE_OLLAMA[ ]*=/ {print $2}' .config 2>/dev/null | tr -d ' \r')
        
        if [ "$OLLAMA_ENABLED" == "true" ]; then
            start_ollama
        else
            echo -e "${YELLOW}No local LLM enabled. Set ENABLE_OLLAMA=true in .config${NC}"
        fi
        ;;
    check) check_services ;;
    *) echo "Usage: $0 {start|check}"; exit 1 ;;
esac
