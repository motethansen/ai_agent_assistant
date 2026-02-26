from google import genai
import os
import json
import datetime
from dotenv import load_dotenv

# Load API key from .env file
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

def generate_schedule(tasks, busy_slots):
    """
    Sends tasks and busy slots to the AI to generate a daily schedule.
    Using the new google-genai SDK.
    """
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env file.")
        return None

    try:
        client = genai.Client(api_key=api_key)
        
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        
        prompt = f"""
        You are a professional personal assistant and scheduler.
        Current Date/Time: {current_time}
        
        TASKS TO SCHEDULE:
        {json.dumps(tasks, indent=2)}
        
        EXISTING CALENDAR COMMITMENTS (BUSY SLOTS):
        {json.dumps(busy_slots, indent=2)}
        
        GOAL:
        Fit the tasks into the available free slots today.
        - Each task should take roughly 30-60 minutes unless specified.
        - Prioritize earlier tasks.
        - Respect the existing busy slots.
        
        OUTPUT FORMAT:
        Return the schedule EXCLUSIVELY as a JSON array of objects.
        Each object must have:
        - "task": The task name
        - "start": ISO 8601 start time (e.g., "2026-02-24T09:00:00Z")
        - "end": ISO 8601 end time (e.g., "2026-02-24T10:00:00Z")
        
        Do not include any other text or explanation. Just the JSON.
        """

        # Use gemini-flash-latest based on your specific API permissions
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt
        )

        content = response.text.strip()
        # Clean up any potential markdown code block wrappers
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
