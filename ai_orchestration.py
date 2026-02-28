from google import genai
import os
import json
import datetime
from dotenv import load_dotenv

# Load API key from .env file
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Allowed categories for the backlog
VALID_CATEGORIES = [
    "Ref.team Book editing", "Ref.team Degree planning", "Ref.team innovation workshop",
    "winedragons", "urbanlife works", "cheers", "personal and vizneo website",
    "learning Thai", "writing academic papers", "budgeting app", "Personal"
]

import requests
from rag_agent import RAGAgent

# Default model settings (can be overridden by .config)
MODELS_ENABLED = {
    "gemini": True,
    "ollama": True,
    "openclaw": True
}

def get_routing(task_type="scheduling"):
    """
    Determines which model should handle the given task type.
    Pulls from MODELS_ENABLED and defaults to Ollama if Gemini is disabled.
    """
    # 1. Check if Gemini is enabled and we have an API key
    if MODELS_ENABLED.get("gemini") and api_key:
        # Check if specific task routing is set to gemini
        return "gemini"
        
    # 2. Fallback to Ollama if enabled
    if MODELS_ENABLED.get("ollama"):
        return "ollama"
        
    # 3. Last resort - OpenClaw
    if MODELS_ENABLED.get("openclaw"):
        return "openclaw"
        
    return "ollama" # Default fallback


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
        prompt = f"Schedule these tasks: {json.dumps(tasks)} avoiding these busy slots: {json.dumps(busy_slots)}. Return JSON."
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
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        
        mode_instruction = ""
        if morning_mode:
            mode_instruction = "This is a MORNING PLANNING session. Suggest which tasks from the backlog should be done today based on their due dates and categories."
        
        prompt = f"""
        You are a professional personal assistant and scheduler with FILE SYSTEM ACCESS.
        Current Date/Time: {current_time}
        {mode_instruction}

        TASKS BACKLOG:
        {json.dumps(tasks, indent=2)}
        
        EXISTING CALENDAR COMMITMENTS:
        {json.dumps(busy_slots, indent=2)}
        
        CONTEXTUAL BACKGROUND (USE THIS TO DECIDE PRIORITY AND DURATION):
        {rag_context}
        
        CAPABILITIES:
        1. SCHEDULING: Fit tasks into free slots.
        2. FILE SYSTEM: You have DIRECT access to create folders and files in the user's Obsidian vault.
        
        GOAL:
        - MANDATORY: Include 30-60m for 'exercise' and 30m for 'rest'.
        - ACTION PROPOSALS: If the user asks to "add", "create", "migrate", or "save" something to Obsidian, YOU MUST use the "actions" field.
        - NO COPY-PASTE: Never ask the user to copy and paste text. Instead, propose a "write_file" action to do it for them.

        
        OUTPUT FORMAT:
        Return a JSON object with:
        - "response": A brief text message to the user.
        - "schedule": Array of {{"task": str, "category": str, "start": ISO8601, "end": ISO8601}}
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
