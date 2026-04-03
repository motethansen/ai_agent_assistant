from google import genai
import os
import json
import datetime
import requests
import re
from config_utils import get_config_value

try:
    from langchain_ollama import ChatOllama
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.tools import tool
    try:
        from langchain.agents import AgentExecutor, create_tool_calling_agent
    except ImportError:
        from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
except ImportError:
    ChatOllama = None
    AgentExecutor = None
    create_tool_calling_agent = None
    ChatPromptTemplate = None
    def tool(func): return func  # Fallback decorator

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
    "lmstudio": get_config_value("ENABLE_LM_STUDIO", "false").lower() == "true",
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
    from config_utils import is_google_calendar_enabled
    if not is_google_calendar_enabled():
        return "Google Calendar is disabled. Set ENABLE_GOOGLE_CALENDAR=true in .config to enable."
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

def list_ollama_models():
    """Query Ollama for installed models. Returns list of model name strings."""
    import subprocess
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return []
        lines = result.stdout.strip().splitlines()
        # Skip header line "NAME   ID   SIZE   MODIFIED"
        models = []
        for line in lines[1:]:
            parts = line.split()
            if parts:
                models.append(parts[0])  # e.g. "llama3:latest", "mistral:latest"
        return models
    except Exception:
        return []

def is_lmstudio_running():
    """Checks if the LM Studio local server is responding."""
    try:
        response = requests.get("http://localhost:1234/v1/models", timeout=2)
        return response.status_code == 200
    except Exception:
        return False

def _call_lmstudio(prompt, system=None, model=None):
    """Call LM Studio local server via the openai SDK pointed at http://localhost:1234/v1."""
    try:
        health = requests.get("http://localhost:1234/v1/models", timeout=2)
        if health.status_code != 200:
            raise RuntimeError("LM Studio local server is not reachable")
    except requests.exceptions.RequestException:
        raise RuntimeError("LM Studio local server is not reachable")

    import openai
    model_id = model or get_config_value("LM_STUDIO_MODEL", "local-model")
    client = openai.OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = client.chat.completions.create(model=model_id, messages=messages)
    return response.choices[0].message.content, f"lmstudio/{model_id}"

def is_openai_available():
    """Checks if OpenAI API key is configured and enabled."""
    key = get_config_value("OPENAI_API_KEY", "")
    return bool(key) and "your_openai" not in key and MODELS_ENABLED.get("openai", False)

def is_claude_available():
    """Checks if Claude API key is configured and enabled."""
    key = get_config_value("CLAUDE_API_KEY", "")
    return bool(key) and "your_claude" not in key and MODELS_ENABLED.get("claude", False)

# --- Complexity Classification ---
COMPLEXITY_KEYWORDS_SIMPLE = [
    "parse", "extract", "categorize", "list", "format", "convert",
    "remind", "sort", "filter", "count", "show", "display", "what time",
    "how many", "which", "status"
]
COMPLEXITY_KEYWORDS_COMPLEX = [
    "plan", "analyze", "compare", "generate code", "write code", "design",
    "debug", "explain why", "research", "strategy", "refactor", "review",
    "deep", "improve", "optimize", "architect", "suggest", "create a"
]

def classify_complexity(query):
    """Returns 'simple' or 'complex' based on query content."""
    query_lower = query.lower()
    complex_score = sum(1 for kw in COMPLEXITY_KEYWORDS_COMPLEX if kw in query_lower)
    simple_score = sum(1 for kw in COMPLEXITY_KEYWORDS_SIMPLE if kw in query_lower)
    if len(query) > 500:
        complex_score += 1
    return "complex" if complex_score > simple_score else "simple"

def _is_model_available(model, try_start=False):
    """Check if a model backend is both enabled and reachable."""
    if model == "ollama":
        return MODELS_ENABLED.get("ollama", False) and is_ollama_running()
    if model == "lmstudio":
        return MODELS_ENABLED.get("lmstudio", False) and is_lmstudio_running()
    if model == "gemini":
        return MODELS_ENABLED.get("gemini", False) and api_key and "your_gemini" not in api_key
    if model == "openai":
        return is_openai_available()
    if model == "claude":
        return is_claude_available()
    return False

def get_routing(task_type="chat", query=""):
    """Routes to the best LLM based on task type, complexity, and availability.

    1. Check ROUTING_{task_type} config for explicit assignment
    2. Route by complexity: simple -> local, complex -> powerful
    3. Fall back through LLM_PRIORITY chain
    """
    # Check explicit routing config
    explicit = get_config_value(f"ROUTING_{task_type.upper()}", None)
    if explicit:
        explicit = explicit.strip().lower()
        if _is_model_available(explicit, try_start=True):
            return explicit

    # Complexity-based routing
    complexity = classify_complexity(query) if query else "simple"

    if complexity == "simple":
        for model in ["ollama", "lmstudio", "gemini"]:
            if _is_model_available(model, try_start=True):
                return model
    else:
        for model in ["openai", "claude", "gemini", "ollama"]:
            if _is_model_available(model, try_start=True):
                return model

    # Fallback through priority list
    priority_str = get_config_value("LLM_PRIORITY", "ollama,lmstudio,gemini,openai,claude")
    for model in [m.strip().lower() for m in priority_str.split(",")]:
        if _is_model_available(model, try_start=True):
            return model

    return "ollama"

def get_llm(model_type="chat", query=""):
    """Returns a LangChain LLM instance based on routing. Also returns the model name used."""
    model_name = get_routing(model_type, query)

    if model_name == "ollama":
        if not is_ollama_running():
            print("⚠️  Ollama is not running. Start it with: ollama serve")
            print("    Falling back to next available LLM.")
            # Try priority fallback excluding ollama
            priority_str = get_config_value("LLM_PRIORITY", "ollama,gemini,openai,claude")
            for fallback in [m.strip().lower() for m in priority_str.split(",")]:
                if fallback != "ollama" and _is_model_available(fallback):
                    model_name = fallback
                    break
        if model_name == "ollama":
            model = get_config_value("OLLAMA_MODEL", "qwen3:8b")
            host = get_config_value("OLLAMA_HOST", "http://localhost:11434")
            ctx_size = int(get_config_value("OLLAMA_NUM_CTX", "8192"))
            return ChatOllama(model=model, base_url=host, num_ctx=ctx_size, temperature=0), f"ollama/{model}"

    elif model_name == "openai":
        from langchain_openai import ChatOpenAI
        openai_key = get_config_value("OPENAI_API_KEY", "")
        openai_model = get_config_value("OPENAI_MODEL", "gpt-4o-mini")
        return ChatOpenAI(model=openai_model, openai_api_key=openai_key, temperature=0), f"openai/{openai_model}"

    elif model_name == "claude":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            print("langchain-anthropic not installed. Install with: pip install langchain-anthropic")
            # Fall through to gemini
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=api_key), "gemini/gemini-2.0-flash"
        claude_key = get_config_value("CLAUDE_API_KEY", "")
        claude_model = get_config_value("CLAUDE_MODEL", "claude-sonnet-4-20250514")
        return ChatAnthropic(model=claude_model, anthropic_api_key=claude_key, temperature=0), f"claude/{claude_model}"

    # Fallback to Gemini
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=api_key), "gemini/gemini-2.0-flash"

def run_agent_query(user_input, context_data=None):
    """Runs a tool-calling agent to handle a user query."""
    llm, model_used = get_llm("chat", user_input)
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
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False, handle_parsing_errors=True)

    try:
        response = agent_executor.invoke({"input": user_input})
        return response["output"], model_used
    except Exception as e:
        return f"Agent Error: {e}", model_used

def _get_file_context(user_input):
    """
    Fetch relevant context from LogSeq (journals + pages) and Obsidian
    based on the user's query. Returns a formatted string for the LLM system prompt.
    """
    from logseq_agent import LogSeqAgent, parse_date_from_text
    context_parts = []
    input_lower = user_input.lower()

    logseq_dir = get_config_value("LOGSEQ_DIR", None)
    if logseq_dir and os.path.exists(logseq_dir):
        agent = LogSeqAgent(logseq_dir)

        # ── Journal: specific date ────────────────────────────────────────
        date_key = parse_date_from_text(user_input)
        if date_key:
            raw_text, tasks = agent.get_tasks_for_date(date_key)
            if raw_text is None:
                context_parts.append(
                    f"LogSeq journal {date_key}: file not found."
                )
            else:
                context_parts.append(agent.context_for_date(date_key))

        # ── Journal: recent tasks (no date specified) ─────────────────────
        elif any(kw in input_lower for kw in ['logseq', 'journal', 'task', 'todo', 'later', 'recent']):
            context_parts.append(agent.context_for_recent(days=7))

        # ── Pages: tasks ──────────────────────────────────────────────────
        if any(kw in input_lower for kw in ['page', 'pages', 'todo', 'task', 'all tasks']):
            page_ctx = agent.context_for_all_page_tasks()
            if "0 found" not in page_ctx:
                context_parts.append(page_ctx)

        # ── Pages: keyword search ─────────────────────────────────────────
        if any(kw in input_lower for kw in ['page', 'pages', 'note', 'find', 'search', 'about']):
            results = agent.search_pages(user_input)
            if results:
                lines = ["LogSeq pages — matching content:"]
                for page_name, hits in results:
                    lines.append(f"\n**{page_name}**")
                    lines.extend(f"  • {h}" for h in hits)
                context_parts.append("\n".join(lines))

    # ── Obsidian: RAG search ──────────────────────────────────────────────
    obsidian_keywords = ['obsidian', 'vault', 'project', 'plan', 'note', 'notes']
    if any(kw in input_lower for kw in obsidian_keywords):
        try:
            rag = RAGAgent(
                get_config_value("WORKSPACE_DIR", None),
                get_config_value("LOGSEQ_DIR", None)
            )
            rag_context = rag.query_context(user_input)
            if rag_context:
                context_parts.append(f"Obsidian notes — relevant context:\n{rag_context}")
        except Exception:
            pass

    return "\n\n".join(context_parts)


def run_agent_query_stream(user_input, chat_history=None):
    """Streams LLM response chunks for real-time display. Returns (stream_iterator, model_used)."""
    llm, model_used = get_llm("chat", user_input)

    # Pre-fetch file context for LogSeq/Obsidian queries
    file_context = _get_file_context(user_input)

    system_msg = (
        "You are a professional AI Assistant. Be concise and helpful. "
        "Format responses in markdown when appropriate. "
        "If asked about tasks, schedules, or plans, provide actionable suggestions."
    )
    if file_context:
        system_msg += f"\n\nCONTEXT FROM FILES:\n{file_context}"

    messages = [("system", system_msg)]
    if chat_history:
        for msg in chat_history[-10:]:
            role = "human" if msg["role"] == "user" else "ai"
            messages.append((role, msg["content"]))
    messages.append(("human", user_input))

    try:
        return llm.stream(messages), model_used
    except Exception:
        response = llm.invoke(messages)
        return iter([response]), model_used

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

    llm, _ = get_llm("scheduling", str(tasks[:3]))
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

def suggest_task_organization(tasks):
    """
    Analyzes a list of tasks and suggests categories and scheduling dates.
    """
    llm, _ = get_llm("scheduling")
    
    prompt = f"""
    Analyze the following tasks and suggest the best category and target date for each.
    
    VALID CATEGORIES: {json.dumps(VALID_CATEGORIES)}
    
    TASKS: {json.dumps(tasks)}
    
    OUTPUT: Return a JSON object with a "suggestions" array.
    Each item: {{
        "task": "Original Task Name", 
        "suggested_category": "Category from list", 
        "target_date": "YYYY-MM-DD", 
        "reason": "Brief explanation"
    }}
    Return ONLY JSON.
    """
    
    try:
        response = llm.invoke(prompt)
        content = response.content.strip()
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        print(f"Task Organization Error: {e}")
    return {"suggestions": []}

def process_tasks_with_command(tasks, command):
    """
    Processes tasks based on a custom natural language command.
    """
    llm, _ = get_llm("chat", command)
    
    prompt = f"""
    The user wants to perform the following action on these tasks: "{command}"
    
    TASKS: {json.dumps(tasks)}
    
    OUTPUT: Return a JSON object with a "suggestions" array.
    Each item: {{
        "task": "Task Name", 
        "suggested_category": "Category", 
        "target_date": "YYYY-MM-DD", 
        "reason": "Applied change based on command"
    }}
    Return ONLY JSON.
    """
    
    try:
        response = llm.invoke(prompt)
        content = response.content.strip()
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        print(f"Custom Command Error: {e}")
    return {"suggestions": []}

def generate(prompt, system=None, task_type="chat"):
    """Route a single prompt through the configured LLM for the given task type.

    Returns (response_text, model_name). On error returns ("LLM error: ...", model_name).
    """
    from langchain_core.messages import SystemMessage, HumanMessage
    try:
        model_name = get_routing(task_type, prompt)
        if model_name == "lmstudio":
            return _call_lmstudio(prompt, system=system)
        llm, model_name = get_llm(task_type, prompt)
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        response = llm.invoke(messages)
        return response.content, model_name
    except Exception as e:
        model_name = get_routing(task_type)
        return f"LLM error: {e}", model_name


def generate_with(provider, prompt, system=None):
    """Call a specific provider directly, bypassing routing.

    provider: "gemini" | "ollama" | "openai" | "claude"
    Returns (response_text, model_name). On error returns ("LLM error: ...", model_name).
    """
    from langchain_core.messages import SystemMessage, HumanMessage
    messages = []
    if system:
        messages.append(SystemMessage(content=system))
    messages.append(HumanMessage(content=prompt))

    try:
        if provider == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            model_id = get_config_value("GEMINI_MODEL", "gemini-2.0-flash")
            llm = ChatGoogleGenerativeAI(model=model_id, google_api_key=api_key)
            response = llm.invoke(messages)
            return response.content, f"gemini/{model_id}"
        elif provider == "ollama":
            model_id = get_config_value("OLLAMA_MODEL", "qwen3:8b")
            host = get_config_value("OLLAMA_HOST", "http://localhost:11434")
            llm = ChatOllama(model=model_id, base_url=host)
            response = llm.invoke(messages)
            return response.content, f"ollama/{model_id}"
        elif provider == "lmstudio":
            return _call_lmstudio(prompt, system=system)
        elif provider == "openai":
            from langchain_openai import ChatOpenAI
            model_id = get_config_value("OPENAI_MODEL", "gpt-4o-mini")
            llm = ChatOpenAI(model=model_id, openai_api_key=get_config_value("OPENAI_API_KEY", ""))
            response = llm.invoke(messages)
            return response.content, f"openai/{model_id}"
        elif provider == "claude":
            from langchain_anthropic import ChatAnthropic
            model_id = get_config_value("CLAUDE_MODEL", "claude-sonnet-4-20250514")
            llm = ChatAnthropic(model=model_id, anthropic_api_key=get_config_value("CLAUDE_API_KEY", ""))
            response = llm.invoke(messages)
            return response.content, f"claude/{model_id}"
        else:
            return generate(prompt, system=system, task_type="chat")
    except Exception as e:
        return f"LLM error: {e}", provider


def ollama_generate(prompt, model=None):
    """Simple wrapper for single generation."""
    llm, _ = get_llm()
    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        return f"Error: {e}"

def route(task_type: str, prompt: str = None, action: str = None, args: list = None, **kwargs):
    """
    Route a task to a NanoClaw Skill (when NANOCLAW_ENABLED=true and task_type
    is 'obsidian' or 'logseq') or to the existing LLM chain.

    For Skill dispatch: returns the parsed JSON dict from run_skill().
    For LLM dispatch: returns (response_text, model_name) from generate().
    Falls back to LLM silently if NanoClaw raises RuntimeError.
    """
    import logging
    _log = logging.getLogger(__name__)
    nanoclaw_enabled = get_config_value("NANOCLAW_ENABLED", "false").lower() == "true"
    args = args or []
    write = kwargs.get("write", False)

    if nanoclaw_enabled and task_type in ("obsidian", "logseq"):
        try:
            from nanoclaw.client import run_skill
            return run_skill(f"{task_type}_skill", action, *args, write=write)
        except RuntimeError as exc:
            _log.warning("NanoClaw dispatch failed (%s/%s), falling back to LLM: %s",
                         task_type, action, exc)

    if prompt:
        return generate(prompt, task_type=task_type)
    return None


def send_to_n8n(flow_type: str, payload: dict) -> bool:
    """
    Send a data-flow event to n8n with a standard envelope.
    Returns True if accepted. Returns False silently if n8n is down — never raises.
    """
    import logging
    import datetime as _dt
    _log = logging.getLogger(__name__)
    try:
        from n8n_client import trigger, is_n8n_running
        if not is_n8n_running():
            _log.warning("send_to_n8n: n8n not reachable — '%s' not sent", flow_type)
            return False
        envelope = {
            "flow_type": flow_type,
            "sent_at": _dt.datetime.now().isoformat(),
            **payload,
        }
        return trigger(flow_type, envelope)
    except Exception as exc:
        _log.warning("send_to_n8n error (%s): %s", flow_type, exc)
        return False


if __name__ == "__main__":
    test_tasks = [{"task": "Review WineDragons wireframes", "source": "Obsidian"}]
    test_busy = []
    print(generate_schedule(test_tasks, test_busy))
