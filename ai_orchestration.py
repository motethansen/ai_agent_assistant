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
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import BaseMessage, ChatMessage, AIMessage, HumanMessage, SystemMessage
    from langchain_core.outputs import ChatResult, ChatGeneration
    try:
        from langchain.agents import AgentExecutor, create_tool_calling_agent
    except ImportError:
        from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
except ImportError:
    ChatOllama = None
    AgentExecutor = None
    create_tool_calling_agent = None
    ChatPromptTemplate = None
    BaseChatModel = object
    def tool(func): return func  # Fallback decorator

from rag_agent import RAGAgent
from book_agent import BookAgent
from travel_agent import TravelAgent
import calendar_manager

try:
    from agent_tools import ACTION_TOOLS, ACTION_KEYWORDS
except Exception:
    ACTION_TOOLS = []
    ACTION_KEYWORDS = []

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
    "groq": get_config_value("ENABLE_GROQ", "false").lower() == "true",
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
    """Lists scheduled events from the local calendar and n8n cache for the next N days."""
    events = []
    
    # 1. Try n8n YAML cache
    from calendar_agent import CalendarAgent
    agent = CalendarAgent()
    busy_slots = agent.get_busy_slots_from_yml()
    if busy_slots:
        events.extend(busy_slots)
        
    # 2. Try local ICS
    try:
        from local_calendar_agent import list_events
        today = datetime.date.today()
        local_events = list_events(start_date=today, end_date=today + datetime.timedelta(days=days))
        for le in local_events:
            events.append({
                "summary": le["summary"],
                "start": le["start"],
                "end": le["end"]
            })
    except Exception:
        pass
        
    if not events:
        return "No calendar events found."
        
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

def is_openai_available():
    """Checks if OpenAI API key is configured and enabled."""
    key = get_config_value("OPENAI_API_KEY", "")
    return bool(key) and "your_openai" not in key and MODELS_ENABLED.get("openai", False)

def is_claude_available():
    """Checks if Claude API key is configured and enabled."""
    key = get_config_value("CLAUDE_API_KEY", "")
    return bool(key) and "your_claude" not in key and MODELS_ENABLED.get("claude", False)

def is_groq_available():
    """Checks if Groq API key is configured and enabled."""
    key = get_config_value("GROQ_API_KEY", "")
    return bool(key) and "your_groq" not in key and MODELS_ENABLED.get("groq", False)

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
    if model == "gemini":
        return MODELS_ENABLED.get("gemini", False) and api_key and "your_gemini" not in api_key
    if model == "openai":
        return is_openai_available()
    if model == "claude":
        return is_claude_available()
    if model == "groq":
        return is_groq_available()
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
        # Prioritize Ollama for simple tasks
        for model in ["ollama", "groq", "gemini"]:
            if _is_model_available(model, try_start=True):
                return model
    else:
        # Prioritize Groq/Gemini/OpenAI for complex tasks, then Ollama
        for model in ["groq", "gemini", "openai", "claude", "ollama"]:
            if _is_model_available(model, try_start=True):
                return model

    # Fallback through priority list
    priority_str = get_config_value("LLM_PRIORITY", "ollama,groq,gemini,openai,claude")
    for model in [m.strip().lower() for m in priority_str.split(",")]:
        if _is_model_available(model, try_start=True):
            return model

    # Last resort — return first enabled provider even if not reachable
    for model in [m.strip().lower() for m in priority_str.split(",")]:
        if MODELS_ENABLED.get(model, False):
            return model

    return "ollama"

def _build_llm(provider):
    """
    Build and return a (LangChain LLM instance, label) for a specific provider name.
    Does NOT call get_routing() — use this when you already know the provider.
    """

    if provider == "ollama":
        model = get_config_value("OLLAMA_MODEL", "qwen3.5:8b")
        host = get_config_value("OLLAMA_HOST", "http://localhost:11434")
        # Default to 4096 for better memory efficiency on Apple Silicon
        ctx_size = int(get_config_value("OLLAMA_NUM_CTX", "4096"))
        return ChatOllama(model=model, base_url=host, num_ctx=ctx_size, temperature=0), f"ollama/{model}"

    if provider == "gemini":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise RuntimeError("langchain-google-genai not installed. Run: pip install langchain-google-genai")
        gemini_key = get_config_value("GEMINI_API_KEY", "")
        gemini_model = get_config_value("GEMINI_MODEL", "gemini-2.0-flash")
        return ChatGoogleGenerativeAI(model=gemini_model, google_api_key=gemini_key, temperature=0), f"gemini/{gemini_model}"

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        openai_key = get_config_value("OPENAI_API_KEY", "")
        openai_model = get_config_value("OPENAI_MODEL", "gpt-4o-mini")
        return ChatOpenAI(model=openai_model, openai_api_key=openai_key, temperature=0), f"openai/{openai_model}"

    if provider == "claude":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise RuntimeError("langchain-anthropic not installed. Run: pip install langchain-anthropic")
        claude_key = get_config_value("CLAUDE_API_KEY", "")
        claude_model = get_config_value("CLAUDE_MODEL", "claude-sonnet-4-20250514")
        return ChatAnthropic(model=claude_model, anthropic_api_key=claude_key, temperature=0), f"claude/{claude_model}"

    if provider == "groq":
        from langchain_openai import ChatOpenAI
        groq_key = get_config_value("GROQ_API_KEY", "")
        groq_model = get_config_value("GROQ_MODEL", "llama-3.3-70b-versatile")
        return ChatOpenAI(
            model=groq_model,
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_key,
            temperature=0,
        ), f"groq/{groq_model}"

    raise ValueError(f"Unknown provider '{provider}'")


def _get_llm_fallback(exclude=None):
    """Walk LLM_PRIORITY and return the first available (LLM, label) that isn't `exclude`."""
    priority_str = get_config_value("LLM_PRIORITY", "ollama,groq,gemini,openai,claude")
    for name in [m.strip().lower() for m in priority_str.split(",")]:
        if name == exclude:
            continue
        if _is_model_available(name):
            try:
                return _build_llm(name)
            except Exception:
                continue
    raise RuntimeError("No LLM backend is available. Check ENABLE_OLLAMA in .config.")


def get_llm(model_type="chat", query=""):
    """Returns a LangChain LLM instance based on routing. Also returns the model name used."""
    provider = get_routing(model_type, query)

    # Special case: Ollama needs a liveness check before we try to connect
    if provider == "ollama" and not is_ollama_running():
        print("⚠️  Ollama is not running. Falling back through LLM_PRIORITY chain.")
        return _get_llm_fallback("ollama")

    try:
        return _build_llm(provider)
    except Exception as e:
        print(f"⚠️  Failed to build LLM for provider '{provider}': {e}. Trying fallback.")
        return _get_llm_fallback(provider)

def run_agent_query(user_input, context_data=None):
    """Runs a tool-calling agent to handle a user query, including agent-execution tools."""
    llm, model_used = get_llm("chat", user_input)
    read_tools = [get_current_time, search_notes, search_books, list_calendar_events, read_file_content]
    tools = read_tools + ACTION_TOOLS

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a professional AI Assistant with the ability to both retrieve information "
         "and execute tasks. Use read tools to find context, and action tools to actually "
         "perform operations like rescheduling tasks, syncing notes, or organising the planner. "
         "When the user asks you to move, reschedule, sync, or organise — use the appropriate "
         "action tool rather than just describing how to do it. "
         "Always confirm what action was taken and summarise the result."),
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
    """
    Streams LLM response chunks for real-time display.

    If the query looks like an action request (reschedule, sync, organise, etc.)
    it routes through the tool-calling AgentExecutor instead of raw streaming,
    so the LLM can actually execute agents rather than just describing how to.
    Returns (stream_iterator, model_used).
    """
    # Detect action intent — route to tool-calling agent when the user wants
    # something done, not just answered.
    if ACTION_KEYWORDS and any(kw in user_input.lower() for kw in ACTION_KEYWORDS):
        response, model_used = run_agent_query(user_input)
        return iter([response]), model_used

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

def _prioritise_tasks(tasks, max_tasks=40):
    """
    Return at most max_tasks items, prioritising by due_date proximity.
    Tasks with a due_date today or in the past come first, then soonest-due,
    then undated tasks. Strips the verbose 'source'/'file'/'line' keys to
    keep the prompt compact.
    """
    today = datetime.date.today()
    dated, undated = [], []
    for t in tasks:
        entry = {k: v for k, v in (t.items() if isinstance(t, dict) else {}.items())
                 if k not in ("source", "file", "line")}
        if not entry:
            entry = {"task": str(t)}
        due = entry.get("due_date")
        if due:
            try:
                entry["_due"] = datetime.date.fromisoformat(str(due)[:10])
                dated.append(entry)
                continue
            except ValueError:
                pass
        undated.append(entry)

    dated.sort(key=lambda x: x.pop("_due"))
    selected = (dated + undated)[:max_tasks]
    return selected


def generate_schedule(tasks, busy_slots, morning_mode=False, workspace_dir=None, logseq_dir=None):
    """Legacy wrapper for schedule generation, now using the improved RAG logic."""
    # Cap tasks to avoid blowing the local LLM context window
    tasks_for_prompt = _prioritise_tasks(tasks, max_tasks=40)
    if len(tasks) > len(tasks_for_prompt):
        print(f"ℹ️  Scheduling top {len(tasks_for_prompt)} prioritised tasks (of {len(tasks)} total).")

    rag_context = ""
    try:
        rag_agent = RAGAgent(workspace_dir, logseq_dir)
        # Combine task queries for better context
        task_names = [t['task'] if isinstance(t, dict) else t for t in tasks_for_prompt[:5]]
        rag_context = rag_agent.query_context(" ".join(task_names))
    except Exception as e:
        print(f"⚠️ RAG error: {e}")

    llm, _ = get_llm("scheduling", str(tasks_for_prompt[:3]))
    current_time = datetime.datetime.now().astimezone().isoformat()

    prompt = f"""
    You are a professional personal assistant.
    Current Time: {current_time}
    CONTEXT FROM NOTES: {rag_context}
    TASKS: {json.dumps(tasks_for_prompt)}
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

    provider: "lmstudio" | "gemini" | "ollama" | "openai" | "claude"
    Returns (response_text, model_name). On error returns ("LLM error: ...", model_name).
    """
    from langchain_core.messages import SystemMessage, HumanMessage
    try:
        llm, model_name = _build_llm(provider)
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        response = llm.invoke(messages)
        return response.content, model_name
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
