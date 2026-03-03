#!/bin/bash
# Manage local AI services (Ollama & OpenClaw)
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
    # Simple prompt to force loading
    curl -s -X POST http://localhost:11434/api/generate -d "{\"model\":\"$MODEL\", \"prompt\":\"hi\", \"stream\":false}" -m 120 > /dev/null
    echo -e "${GREEN}Model warmed and ready.${NC}"
}

start_openclaw() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Error: Docker not found. Cannot start OpenClaw locally.${NC}"
        return 1
    fi

    # Check if Docker daemon is running
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}Error: Docker daemon is not running.${NC}"
        echo -e "${YELLOW}Please start OrbStack or Docker Desktop and try again.${NC}"
        return 1
    fi

    if docker ps | grep -q "openclaw"; then
        echo -e "${GREEN}OpenClaw is already running (Docker).${NC}"
    else
        echo -e "${YELLOW}Starting OpenClaw via Docker...${NC}"
        
        # Check if the openclaw repo exists
        if [ ! -d "openclaw" ]; then
            echo "Cloning OpenClaw repository..."
            git clone https://github.com/openclaw/openclaw.git
        fi

        cd openclaw
        if [ -f "./docker-setup.sh" ]; then
            echo -e "${YELLOW}Running OpenClaw Docker setup (this may take a few minutes to build/pull)...${NC}"
            # Use docker-setup.sh --yes if possible, or run it directly. 
            # Note: This script typically builds the 'openclaw:local' image and starts the container.
            # If it's the first time, it takes a while.
            bash ./docker-setup.sh --yes || bash ./docker-setup.sh
        else
            echo -e "${RED}Error: docker-setup.sh not found in openclaw directory.${NC}"
            cd ..
            return 1
        fi
        cd ..
        
        # Wait for startup and check again (Port 18789 is default for Web UI)
        echo "Waiting for OpenClaw containers to stabilize..."
        local max_retries=24 # 2 minutes total
        local count=0
        while [ $count -lt $max_retries ]; do
            if docker ps --format '{{.Names}}' | grep -q "openclaw"; then
                echo -e "${GREEN}OpenClaw started successfully (Port 18789).${NC}"
                return 0
            fi
            sleep 5
            ((count++))
        done

        echo -e "${RED}Failed to start OpenClaw.${NC}"
        docker ps -a --filter "name=openclaw"
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
    
    if docker ps | grep -q "openclaw"; then
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
