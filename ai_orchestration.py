from google import genai
import os
import json
import datetime
import requests
from config_utils import get_config_value

# Load API key from .config or environment
api_key = get_config_value("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))

# Allowed categories for the backlog
VALID_CATEGORIES = [
    "Ref.team Book editing", "Ref.team Degree planning", "Ref.team innovation workshop",
    "winedragons", "urbanlife works", "cheers", "personal and vizneo website",
    "learning Thai", "writing academic papers", "budgeting app", "Personal"
]

from rag_agent import RAGAgent
from book_agent import BookAgent
from travel_agent import TravelAgent

# Load model activation from .config
MODELS_ENABLED = {
    "gemini": get_config_value("ENABLE_GEMINI", "false").lower() == "true",
    "openai": get_config_value("ENABLE_OPENAI", "false").lower() == "true",
    "claude": get_config_value("ENABLE_CLAUDE", "false").lower() == "true",
    "ollama": get_config_value("ENABLE_OLLAMA", "true").lower() == "true",
    "openclaw": get_config_value("ENABLE_OPENCLAW", "true").lower() == "true"
}

def is_ollama_running():
    """Checks if the local Ollama server is responding."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False

def get_routing(task_type="scheduling"):
    """
    Determines the best available model based on user priority and health.
    """
    # 1. Check for an explicit override for this specific task
    config_key = f"ROUTING_{task_type.upper()}"
    explicit_model = get_config_value(config_key, None)
    
    # 2. Get the global priority list
    priority_str = get_config_value("LLM_PRIORITY", "ollama,openclaw,gemini")
    priority_list = [m.strip().lower() for m in priority_str.split(",")]
    
    # If there's an explicit override, put it at the front of the line
    if explicit_model:
        priority_list = [explicit_model.lower()] + [m for m in priority_list if m != explicit_model.lower()]

    # 3. Iterate through models in priority order and return the first one that is "Ready"
    for model in priority_list:
        if model == "gemini":
            if MODELS_ENABLED["gemini"] and api_key and "your_gemini_api_key" not in api_key:
                return "gemini"
        
        elif model == "ollama":
            if MODELS_ENABLED["ollama"] and is_ollama_running():
                return "ollama"
        
        elif model == "openclaw":
            if MODELS_ENABLED["openclaw"]:
                # We assume OpenClaw is ready if enabled, as it's an API
                return "openclaw"

        elif model == "openai":
            if MODELS_ENABLED.get("openai") and get_config_value("OPENAI_API_KEY", None):
                return "openai"

        elif model == "claude":
            if MODELS_ENABLED.get("claude") and get_config_value("CLAUDE_API_KEY", None):
                return "claude"

    # 4. Absolute Final Fallback
    if is_ollama_running():
        return "ollama"
    return "openclaw" # Assumed available as an API

def ollama_generate(prompt, model="llama3"):
    """
    Calls a local Ollama instance for generation.
    """
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(url, json=payload, timeout=120)
        return response.json().get("response", "")
    except Exception as e:
        return f"Error calling local Ollama: {e}"

def openclaw_generate(prompt, model="gpt-3.5-turbo"):
    """
    Calls an OpenClaw (OpenAI-compatible) endpoint for generation.
    """
    url = f"{get_config_value('OPENCLAW_ENDPOINT', 'https://api.openclaw.ai/v1')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {get_config_value('OPENCLAW_API_KEY', '')}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error calling OpenClaw: {e}"

def generate_schedule(tasks, busy_slots, morning_mode=False, workspace_dir=None, logseq_dir=None):
    """
    Sends tasks and busy slots to the AI to generate a daily schedule.
    """
    model_to_use = get_routing("scheduling")
    
    rag_context = ""
    if workspace_dir or logseq_dir:
        try:
            rag_agent = RAGAgent(workspace_dir, logseq_dir)
            if rag_agent.collection.count() == 0:
                rag_agent.index_vault()
            
            unique_contexts = []
            for t in tasks[:5]:
                task_name = t['task'] if isinstance(t, dict) else t
                ctx = rag_agent.query_context(task_name, n_results=1)
                if ctx and ctx not in unique_contexts:
                    unique_contexts.append(ctx)
            rag_context = "\n".join(unique_contexts)
        except Exception as e:
            print(f"⚠️ RAG Agent error: {e}")

    current_time = datetime.datetime.now().astimezone().isoformat()
    chronotype = get_config_value("CHRONOTYPE", "balanced")
    dw_start = get_config_value("DEEP_WORK_START", "09:00")
    dw_end = get_config_value("DEEP_WORK_END", "12:00")
    focus_cats = get_config_value("FOCUS_CATEGORIES", "")

    mode_instruction = ""
    if morning_mode:
        mode_instruction = f"This is a MORNING PLANNING session. Chronotype: {chronotype}. Deep Work Window: {dw_start}-{dw_end}."

    prompt = f"""
    You are a professional personal assistant.
    Current Date/Time: {current_time}
    {mode_instruction}
    USER PROFILE: Chronotype={chronotype}, Deep Work={dw_start}-{dw_end}, Focus={focus_cats}

    TASKS: {json.dumps(tasks)}
    BUSY SLOTS: {json.dumps(busy_slots)}
    CONTEXT: {rag_context}
    
    OUTPUT FORMAT: Return a JSON object with a "schedule" array. Each item must have "task", "category", "start" (ISO8601), and "end" (ISO8601).
    Do not include any other text.
    """

    response_text = ""
    if model_to_use == "ollama":
        response_text = ollama_generate(prompt)
    elif model_to_use == "openclaw":
        response_text = openclaw_generate(prompt)
    else:
        if not api_key or "your_gemini_api_key" in api_key:
            response_text = ollama_generate(prompt)
        else:
            try:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(model='gemini-flash-latest', contents=prompt)
                response_text = response.text
            except Exception:
                response_text = ollama_generate(prompt)

    try:
        content = response_text.strip()
        # Find first { and last } to extract JSON
        start_idx = content.find('{')
        end_idx = content.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            json_str = content[start_idx:end_idx+1]
            return json.loads(json_str)
        else:
            print(f"⚠️ No JSON found in response: {content[:100]}...")
            return None
    except Exception as e:
        print(f"Error parsing JSON from AI: {e}")
        print(f"Raw response: {response_text[:200]}...")
        return None

def process_tasks_with_command(tasks, command):
    """
    Asks the AI to perform a specific action on a list of tasks.
    """
    model_to_use = get_routing("chat") # Using chat model for custom commands
    current_time = datetime.datetime.now().astimezone().isoformat()
    
    prompt = f"""
    Current Date: {current_time}
    User Instruction: "{command}"
    
    TASKS TO PROCESS:
    {json.dumps(tasks)}
    
    INSTRUCTIONS:
    1. Apply the user's instruction to the tasks provided.
    2. If the instruction involves dates, suggest a 'target_date' (YYYY-MM-DD).
    3. If the instruction involves categories, suggest a 'category'.
    
    OUTPUT FORMAT:
    Return a JSON object with a "suggestions" array. Each item MUST have:
    "task", "category", "target_date", "reason".
    
    Do not include any other text.
    """
    
    response_text = ""
    if model_to_use == "ollama":
        response_text = ollama_generate(prompt)
    elif model_to_use == "openclaw":
        response_text = openclaw_generate(prompt)
    else:
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(model='gemini-flash-latest', contents=prompt)
            response_text = response.text
        except:
            response_text = ollama_generate(prompt)

    try:
        content = response_text.strip()
        start_idx = content.find('{')
        end_idx = content.rfind('}')
        if start_idx != -1 and end_idx != -1:
            return json.loads(content[start_idx:end_idx+1])
    except:
        return None

def suggest_task_organization(tasks):
    """
    Asks the AI to categorize a list of tasks and suggest optimal dates.
    """
    model_to_use = get_routing("scheduling")
    current_time = datetime.datetime.now().astimezone().isoformat()
    
    prompt = f"""
    Current Date: {current_time}
    You are an expert productivity consultant. Organize the following tasks:
    {json.dumps(tasks)}
    
    INSTRUCTIONS:
    1. Categorize each task into one of these: {", ".join(VALID_CATEGORIES)}.
    2. Suggest a 'target_date' (YYYY-MM-DD) for each task, distributing them logically across the next 7 days.
    
    OUTPUT FORMAT:
    Return a JSON object with a "suggestions" array. Each item MUST have:
    "task", "category", "target_date", "reason".
    
    Do not include any other text.
    """
    
    response_text = ""
    if model_to_use == "ollama":
        response_text = ollama_generate(prompt)
    elif model_to_use == "openclaw":
        response_text = openclaw_generate(prompt)
    else:
        if not api_key or "your_gemini_api_key" in api_key:
            response_text = ollama_generate(prompt)
        else:
            try:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(model='gemini-flash-latest', contents=prompt)
                response_text = response.text
            except Exception:
                response_text = ollama_generate(prompt)

    try:
        content = response_text.strip()
        start_idx = content.find('{')
        end_idx = content.rfind('}')
        if start_idx != -1 and end_idx != -1:
            return json.loads(content[start_idx:end_idx+1])
    except:
        return None

if __name__ == "__main__":
    test_tasks = [{"task": "Review WineDragons wireframes", "source": "Obsidian"}]
    test_busy = []
    print(generate_schedule(test_tasks, test_busy))
