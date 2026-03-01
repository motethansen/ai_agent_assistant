#!/bin/bash
# Manage local AI services (Ollama, etc.)
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
    start) start_ollama ;;
    check) check_services ;;
    *) echo "Usage: $0 {start|check}"; exit 1 ;;
esac
