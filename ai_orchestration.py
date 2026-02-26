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

def generate_schedule(tasks, busy_slots, morning_mode=False):
    """
    Sends tasks and busy slots to the AI to generate a daily schedule or suggestion.
    """
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
        You are a professional personal assistant and scheduler.
        Current Date/Time: {current_time}
        {mode_instruction}

        TASKS BACKLOG (with categories and due dates):
        {json.dumps(tasks, indent=2)}
        
        EXISTING CALENDAR COMMITMENTS (BUSY SLOTS):
        {json.dumps(busy_slots, indent=2)}
        
        VALID CATEGORIES:
        {", ".join(VALID_CATEGORIES)}

        GOAL:
        1. Fit tasks into available free slots today.
        2. MANDATORY: Include at least 30-60 minutes for 'exercise' and 30 minutes for 'rest'.
        3. CATEGORIZATION: If a task has no category or an invalid one, suggest a new category or map it to the closest valid one.
        4. SCHEDULING: 
           - prioritize tasks with today's due date.
           - Allocate 30-90 minutes per task.
        
        OUTPUT FORMAT:
        Return a JSON object with:
        - "schedule": Array of {{"task": str, "category": str, "start": ISO8601, "end": ISO8601}}
        - "suggestions": Array of {{"task": str, "suggested_category": str, "reason": str}} for uncategorized items.
        
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
