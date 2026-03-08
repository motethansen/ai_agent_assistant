from google import genai
import os
import json
import datetime
import requests
import re
from config_utils import get_config_value

try:
    from langchain_ollama import ChatOllama
    from langchain.agents import AgentExecutor, create_tool_calling_agent
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.tools import tool
except ImportError:
    ChatOllama = None
    AgentExecutor = None

from rag_agent import RAGAgent
from book_agent import BookAgent
from travel_agent import TravelAgent
import calendar_manager

# Load API key from .config or environment
api_key = get_config_value("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))

# Allowed categories for the backlog
VALID_CATEGORIES = [
    "Ref.team Book editing", "Ref.team Degree planning", "Ref.team innovation workshop",
    "winedragons", "urbanlife works", "cheers", "personal and vizneo website",
    "learning Thai", "writing academic papers", "budgeting app", "Personal"
]

# Load model activation from .config
MODELS_ENABLED = {
    "gemini": get_config_value("ENABLE_GEMINI", "false").lower() == "true",
    "openai": get_config_value("ENABLE_OPENAI", "false").lower() == "true",
    "claude": get_config_value("ENABLE_CLAUDE", "false").lower() == "true",
    "ollama": get_config_value("ENABLE_OLLAMA", "true").lower() == "true",
    "openclaw": get_config_value("ENABLE_OPENCLAW", "true").lower() == "true"
}

# --- Tools for the AI Agent ---

@tool
def get_current_time():
    """Returns the current date and time."""
    return datetime.datetime.now().astimezone().isoformat()

@tool
def search_notes(query: str):
    """Searches Obsidian and LogSeq notes for relevant context."""
    rag_agent = RAGAgent()
    return rag_agent.query_context(query)

@tool
def search_books(query: str):
    """Searches through the indexed book library for relevant passages."""
    book_agent = BookAgent()
    return book_agent.search_books(query)

@tool
def list_calendar_events(days: int = 1):
    """Lists scheduled events from Google Calendar for the next N days."""
    service = calendar_manager.get_calendar_service()
    if not service: return "Calendar service not available."
    calendar_id = get_config_value("CALENDAR_ID", "primary")
    events = calendar_manager.get_managed_events(service, calendar_id=calendar_id)
    return json.dumps(events)

@tool
def read_file_content(path: str):
    """Reads the content of a file from the workspace."""
    workspace = get_config_value("WORKSPACE_DIR", ".")
    full_path = os.path.join(workspace, path)
    if not os.path.exists(full_path):
        return f"File not found: {path}"
    try:
        with open(full_path, "r") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def is_ollama_running():
    """Checks if the local Ollama server is responding."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False

def is_openclaw_running():
    """Checks if the OpenClaw endpoint is responding."""
    endpoint = get_config_value('OPENCLAW_ENDPOINT', 'http://localhost:18789/v1')
    try:
        response = requests.get(f"{endpoint}/models", timeout=2)
        return response.status_code in [200, 401]
    except:
        return False

def get_routing(task_type="scheduling"):
    """Determines the best available model based on user priority and health."""
    priority_str = get_config_value("LLM_PRIORITY", "ollama,openclaw,gemini")
    priority_list = [m.strip().lower() for m in priority_str.split(",")]
    
    for model in priority_list:
        if model == "gemini" and MODELS_ENABLED["gemini"] and api_key and "your_gemini_api_key" not in api_key:
            return "gemini"
        elif model == "ollama" and MODELS_ENABLED["ollama"] and is_ollama_running():
            return "ollama"
        elif model == "openclaw" and MODELS_ENABLED["openclaw"] and is_openclaw_running():
            return "openclaw"
    
    return "ollama" if is_ollama_running() else "gemini"

def get_llm(model_type="chat"):
    """Returns a LangChain LLM instance based on routing."""
    model_name = get_routing(model_type)
    
    if model_name == "ollama":
        model = get_config_value("OLLAMA_MODEL", "qwen3:8b")
        host = get_config_value("OLLAMA_HOST", "http://localhost:11434")
        # Increase context window for RAG and agent tasks as suggested
        ctx_size = int(get_config_value("OLLAMA_NUM_CTX", "8192"))
        return ChatOllama(model=model, base_url=host, num_ctx=ctx_size, temperature=0)
    
    elif model_name == "openclaw":
        model = get_config_value("OPENCLAW_MODEL", "gpt-3.5-turbo")
        endpoint = get_config_value("OPENCLAW_ENDPOINT", "http://localhost:18789/v1")
        # ChatOllama can't do OpenClaw directly, but LangChain has OpenAI-compatible
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            openai_api_base=endpoint,
            openai_api_key=get_config_value("OPENCLAW_API_KEY", "not-needed"),
            temperature=0
        )
    
    # Fallback to Gemini (via Google GenAI) - LangChain also supports this
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=api_key)

def run_agent_query(user_input, context_data=None):
    """
    Runs a tool-calling agent to handle a user query.
    """
    llm = get_llm()
    tools = [get_current_time, search_notes, search_books, list_calendar_events, read_file_content]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a professional AI Assistant. Use tools to find information. "
                   "If asked about tasks, check notes and calendar. "
                   "Always return a helpful response and suggest actions if needed."),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    
    try:
        response = agent_executor.invoke({"input": user_input})
        return response["output"]
    except Exception as e:
        return f"Agent Error: {e}"

def generate_schedule(tasks, busy_slots, morning_mode=False, workspace_dir=None, logseq_dir=None):
    """Legacy wrapper for schedule generation, now using the improved RAG logic."""
    rag_context = ""
    try:
        rag_agent = RAGAgent(workspace_dir, logseq_dir)
        # Combine task queries for better context
        task_names = [t['task'] if isinstance(t, dict) else t for t in tasks[:5]]
        rag_context = rag_agent.query_context(" ".join(task_names))
    except Exception as e:
        print(f"⚠️ RAG error: {e}")

    llm = get_llm("scheduling")
    current_time = datetime.datetime.now().astimezone().isoformat()
    
    prompt = f"""
    You are a professional personal assistant.
    Current Time: {current_time}
    CONTEXT FROM NOTES: {rag_context}
    TASKS: {json.dumps(tasks)}
    BUSY SLOTS: {json.dumps(busy_slots)}
    
    OUTPUT: Return a JSON object with a "schedule" array. 
    Each item: {{"task": "...", "category": "...", "start": "ISO8601", "end": "ISO8601"}}.
    Return ONLY JSON.
    """
    
    try:
        response = llm.invoke(prompt)
        content = response.content.strip()
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        print(f"Schedule Gen Error: {e}")
    return None

def ollama_generate(prompt, model=None):
    """Simple wrapper for single generation."""
    llm = get_llm()
    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        return f"Error: {e}"

def openclaw_generate(prompt, model=None):
    """Simple wrapper for OpenClaw generation."""
    if model is None:
        model = get_config_value("OPENCLAW_MODEL", "gpt-3.5-turbo")
    endpoint = get_config_value('OPENCLAW_ENDPOINT', 'http://localhost:18789/v1')
    headers = {"Authorization": f"Bearer {get_config_value('OPENCLAW_API_KEY', '')}"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    try:
        response = requests.post(f"{endpoint}/chat/completions", json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"OpenClaw error: {e}"


if __name__ == "__main__":
    test_tasks = [{"task": "Review WineDragons wireframes", "source": "Obsidian"}]
    test_busy = []
    print(generate_schedule(test_tasks, test_busy))
