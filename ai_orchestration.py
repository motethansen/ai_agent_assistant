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
    Determines which model should handle the given task type based on config and availability.
    """
    config_key = f"ROUTING_{task_type.upper()}"
    requested_model = get_config_value(config_key, "openclaw").lower()
    
    if requested_model == "gemini" and MODELS_ENABLED["gemini"] and api_key and "your_gemini_api_key" not in api_key:
        return "gemini"
    
    if requested_model == "ollama" and MODELS_ENABLED["ollama"] and is_ollama_running():
        return "ollama"

    if requested_model == "openclaw" and MODELS_ENABLED["openclaw"]:
        return "openclaw"
        
    if is_ollama_running():
        return "ollama"
    if MODELS_ENABLED["openclaw"]:
        return "openclaw"
        
    return "gemini"

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
        response = requests.post(url, json=payload, timeout=30)
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
        if content.startswith("```json"):
            content = content[7:].rsplit("```", 1)[0].strip()
        elif content.startswith("```"):
            content = content[3:].rsplit("```", 1)[0].strip()
        return json.loads(content)
    except Exception:
        return None

if __name__ == "__main__":
    test_tasks = [{"task": "Review WineDragons wireframes", "source": "Obsidian"}]
    test_busy = []
    print(generate_schedule(test_tasks, test_busy))
