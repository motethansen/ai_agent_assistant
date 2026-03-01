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
    "gemini": get_config_value("ENABLE_GEMINI", "true").lower() == "true",
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
    # 1. Get requested model for this task type from config
    config_key = f"ROUTING_{task_type.upper()}"
    requested_model = get_config_value(config_key, "gemini").lower()
    
    # 2. Check if requested model is enabled and available
    if requested_model == "gemini" and MODELS_ENABLED["gemini"] and api_key and "your_gemini_api_key" not in api_key:
        return "gemini"
    
    if requested_model == "ollama" and MODELS_ENABLED["ollama"] and is_ollama_running():
        return "ollama"
        
    # 3. FALLBACK LOGIC
    # If requested was ollama but it's down, try Gemini
    if requested_model == "ollama" and MODELS_ENABLED["gemini"] and api_key and "your_gemini_api_key" not in api_key:
        print(f"⚠️ Warning: Ollama is requested for {task_type} but not running. Falling back to Gemini.")
        return "gemini"
        
    # If requested was gemini but it's disabled/missing key, try Ollama
    if requested_model == "gemini" and MODELS_ENABLED["ollama"] and is_ollama_running():
        return "ollama"
        
    # Last resort
    if MODELS_ENABLED["openclaw"]:
        return "openclaw"
        
    return "gemini" # Final default


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
        return f"Error calling local Ollama: {e}. Please ensure Ollama is running (try opening the Ollama app)."

def generate_schedule(tasks, busy_slots, morning_mode=False, workspace_dir=None, logseq_dir=None):
    """
    Sends tasks and busy slots to the AI to generate a daily schedule.
    Includes RAG-based context from the user's notes for each task.
    """
    model_to_use = get_routing("scheduling")
    
    # --- RAG Integration: Enhance tasks with context ---
    rag_context = ""
    if workspace_dir or logseq_dir:
        try:
            rag_agent = RAGAgent(workspace_dir, logseq_dir)
            # We don't want to index EVERY time for performance, 
            # but for simplicity in this turn we will ensure it's at least once.
            if rag_agent.collection.count() == 0:
                rag_agent.index_vault()
            
            # For each major task, try to find context
            unique_contexts = []
            # Only pull context for the first 5 tasks to avoid prompt bloat
            for t in tasks[:5]:
                task_name = t['task'] if isinstance(t, dict) else t
                ctx = rag_agent.query_context(task_name, n_results=1)
                if ctx and ctx not in unique_contexts:
                    unique_contexts.append(ctx)
            
            rag_context = "\n".join(unique_contexts)
        except Exception as e:
            print(f"⚠️ RAG Agent error: {e}")

    if model_to_use == "ollama":
        print("Using local Ollama for scheduling...")
        current_time = datetime.datetime.now().astimezone().isoformat()
        prompt = f"Current Time: {current_time}. Schedule these tasks: {json.dumps(tasks)} avoiding these busy slots: {json.dumps(busy_slots)}. Return JSON with 'schedule' array containing 'task', 'start' (ISO8601 with timezone), and 'end' (ISO8601 with timezone)."
        if rag_context:
            prompt += f"\n\nContext for tasks: {rag_context}"
        response_text = ollama_generate(prompt)
        # (Ollama response would need careful JSON parsing here)
        try:
            return json.loads(response_text)
        except:
            return None

    # Default to Gemini logic...
    if not api_key:

        print("Error: GEMINI_API_KEY not found in .env file.")
        return None

    try:
        client = genai.Client(api_key=api_key)
        current_time = datetime.datetime.now().astimezone().isoformat()
        
        # --- User Preference Integration ---
        # Fetch preferences from .config (helper imports or local)
        from config_utils import get_config_value
        chronotype = get_config_value("CHRONOTYPE", "balanced")
        dw_start = get_config_value("DEEP_WORK_START", "09:00")
        dw_end = get_config_value("DEEP_WORK_END", "12:00")
        focus_cats = get_config_value("FOCUS_CATEGORIES", "")

        mode_instruction = ""
        if morning_mode:
            mode_instruction = f"This is a MORNING PLANNING session. Suggest which tasks from the backlog should be done today based on their due dates and categories. Chronotype: {chronotype}. Deep Work Window: {dw_start}-{dw_end}."
        
        prompt = f"""
        You are a professional personal assistant and scheduler with FILE SYSTEM ACCESS.
        Current Date/Time: {current_time}
        {mode_instruction}

        USER PRODUCTIVITY PROFILE:
        - Chronotype: {chronotype}
        - Deep Work Window (High-Focus tasks only): {dw_start} to {dw_end}
        - Focus Categories (Require Deep Work): {focus_cats}
        - Task Logic: Schedule Focus Categories during the Deep Work Window. Schedule administrative/low-energy tasks outside this window or during the afternoon.

        TASKS BACKLOG:
        {json.dumps(tasks, indent=2)}
        
        EXISTING CALENDAR COMMITMENTS:
        {json.dumps(busy_slots, indent=2)}
        
        CONTEXTUAL BACKGROUND (USE THIS TO DECIDE PRIORITY AND DURATION):
        {rag_context}
        
        CAPABILITIES:
        1. SCHEDULING: Fit tasks into free slots according to the Productivity Profile.
        2. FILE SYSTEM: You have DIRECT access to create folders and files in the user's Obsidian vault.
        3. BOOK ANALYSIS: You can analyze books in the library. 
           - To read first pages: {{"type": "read_book", "path": "path"}}.
           - To SEARCH deep into all indexed books: {{"type": "search_books", "query": "your query"}}.
           - To INDEX a book for deep search (if not already indexed): {{"type": "index_book", "path": "path"}}.
        4. TRAVEL PLANNING: You can browse the internet for flights, holiday plans, and travel details.
           - To plan travel: {{"type": "plan_travel", "query": "your travel query"}}.
        
        GOAL:
        - MANDATORY: Include 30-60m for 'exercise' and 30m for 'rest'.
        - ACTION PROPOSALS: If the user asks to "add", "create", "migrate", or "save" something to Obsidian, YOU MUST use the "actions" field.
        - DEEP RESEARCH: If a user asks for specific details from a large book, first check if it is indexed in 'books_library'. If not, propose "index_book". If indexed, use "search_books".
        - TRAVEL RESEARCH: If a user asks about flights or holiday plans, use the "plan_travel" action.

        
        OUTPUT FORMAT:
        Return a JSON object with:
        - "response": A brief text message to the user.
        - "schedule": Array of {{"task": str, "category": str, "start": ISO8601, "end": ISO8601}}
          IMPORTANT: Use ISO8601 format WITH timezone offset (e.g., "2026-03-01T09:00:00-07:00") for all start and end times.
        - "suggestions": Array of {{"task": str, "suggested_category": str, "reason": str}}
        - "actions": Array of {{"type": "create_folder"|"write_file", "path": str, "content": str (optional), "reason": str}}
        
        Example for migrating reminders to a new file:
        {{"actions": [{{"type": "create_folder", "path": "AI_Agent", "reason": "Grouping AI tasks"}}, {{"type": "write_file", "path": "AI_Agent/Backlog.md", "content": "# Backlog...", "reason": "Migrating reminders"}}]}}

        Do not include any other text. Just the JSON.
        """



        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt
        )

        content = response.text.strip()
        if content.startswith("```json"):
            content = content[7:].rsplit("```", 1)[0].strip()
        elif content.startswith("```"):
            content = content[3:].rsplit("```", 1)[0].strip()
            
        return json.loads(content)
    except Exception as e:
        print(f"Error calling AI API: {e}")
        return None


if __name__ == "__main__":
    # Test Data
    test_tasks = ["Review WineDragons wireframes", "Draft Chiang Mai University curriculum"]
    test_busy = [
        {"summary": "Team Meeting", "start": "2026-02-24T11:00:00Z", "end": "2026-02-24T12:00:00Z"}
    ]
    
    schedule = generate_schedule(test_tasks, test_busy)
    if schedule:
        print("Generated Schedule:")
        print(json.dumps(schedule, indent=2))
