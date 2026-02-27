import json
import os

DATA_FILE = "datainput/reminders.json"

def get_apple_reminders(list_name="Reminders", incomplete_only=True):
    """
    Retrieves reminders from the local JSON storage.
    The local storage is populated by running debug_reminders.py.
    """
    if not os.path.exists(DATA_FILE):
        print(f"Warning: Local reminders file '{DATA_FILE}' not found.")
        print("💡 TIP: Run 'python3 debug_reminders.py' to extract reminders from your Mac.")
        return []

    try:
        with open(DATA_FILE, "r") as f:
            reminders = json.load(f)
        
        # Add category for consistency with AI assistant
        for r in reminders:
            if "category" not in r:
                r["category"] = "Personal"
                
        return reminders
    except Exception as e:
        print(f"Error reading local reminders file: {e}")
        return []

if __name__ == "__main__":
    print(f"Reading local reminders from {DATA_FILE}...")
    tasks = get_apple_reminders()
    for t in tasks[:5]:
        print(f"- {t['task']} (Due: {t.get('due_date')})")
