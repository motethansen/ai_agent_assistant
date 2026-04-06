#!/bin/bash
# Manage local AI services (Ollama, LM Studio)
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

start_lmstudio() {
    # No-op when ENABLE_LM_STUDIO is not true
    LMS_ENABLED=$(awk -F'=' '/^ENABLE_LM_STUDIO[ ]*=/ {print $2}' .config 2>/dev/null | tr -d ' \r')
    if [ "$LMS_ENABLED" != "true" ]; then
        return
    fi

    if ! command -v lms > /dev/null 2>&1; then
        echo -e "${YELLOW}lms CLI not found. Open LM Studio at least once to register it in PATH.${NC}"
        echo -e "  See: https://lmstudio.ai/docs/cli"
        return
    fi

    echo -e "${YELLOW}Starting LM Studio server...${NC}"
    lms server start

    LMS_MODEL=$(awk -F'=' '/^LM_STUDIO_MODEL[ ]*=/ {print $2}' .config 2>/dev/null | tr -d ' \r')
    if [ -z "$LMS_MODEL" ]; then
        echo -e "${YELLOW}Warning: LM_STUDIO_MODEL not set in .config — skipping model load.${NC}"
        return
    fi

    if ! lms ps 2>/dev/null | grep -qF "$LMS_MODEL"; then
        echo -e "${YELLOW}Loading model '$LMS_MODEL' into LM Studio...${NC}"
        lms load "$LMS_MODEL"
    fi

    echo -e "${GREEN}LM Studio ready: $LMS_MODEL${NC}"
}

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
    # LM Studio (shown first when it is the primary)
    LMS_ENABLED=$(awk -F'=' '/^ENABLE_LM_STUDIO[ ]*=/ {print $2}' .config 2>/dev/null | tr -d ' \r')
    if [ "$LMS_ENABLED" == "true" ]; then
        if command -v lms > /dev/null 2>&1 && lms ps 2>/dev/null | grep -q .; then
            echo -e "LM Studio: ${GREEN}RUNNING${NC}"
        else
            echo -e "LM Studio: ${RED}STOPPED${NC}"
            start_lmstudio
        fi
    fi

    # Ollama (only when enabled)
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
        LMS_ENABLED=$(awk -F'=' '/^ENABLE_LM_STUDIO[ ]*=/ {print $2}' .config 2>/dev/null | tr -d ' \r')
        OLLAMA_ENABLED=$(awk -F'=' '/^ENABLE_OLLAMA[ ]*=/ {print $2}' .config 2>/dev/null | tr -d ' \r')
        if [ "$LMS_ENABLED" == "true" ]; then
            start_lmstudio
        fi
        if [ "$OLLAMA_ENABLED" == "true" ]; then
            start_ollama
        fi
        if [ "$LMS_ENABLED" != "true" ] && [ "$OLLAMA_ENABLED" != "true" ]; then
            echo -e "${YELLOW}No local LLM enabled. Set ENABLE_LM_STUDIO=true or ENABLE_OLLAMA=true in .config${NC}"
        fi
        ;;
    check) check_services ;;
    *) echo "Usage: $0 {start|check}"; exit 1 ;;
esac
