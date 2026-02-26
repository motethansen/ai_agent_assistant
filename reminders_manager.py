import os
from EventKit import EKEventStore, EKEntityTypeReminder
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load configuration (optional)
load_dotenv()

def get_apple_reminders(list_name="Reminders", incomplete_only=True):
    """
    Fetches reminders from a specific Apple Reminders list on macOS.
    Note: Requires 'Full Disk Access' or 'Reminders' permission for the terminal/IDE.
    """
    try:
        store = EKEventStore.alloc().initWithAccessToEntityTypes_(EKEntityTypeReminder)
        
        # We need to fetch synchronously or handle the async callback
        # For simplicity in a CLI script, we'll use a predicate
        
        # Get all calendars/lists that contain reminders
        calendars = store.calendarsForEntityType_(EKEntityTypeReminder)
        target_calendar = None
        for calendar in calendars:
            if calendar.title() == list_name:
                target_calendar = calendar
                break
        
        if not target_calendar:
            print(f"Warning: Apple Reminders list '{list_name}' not found.")
            return []

        # Create a predicate for incomplete reminders
        predicate = store.predicateForIncompleteRemindersWithDueDateStarting_ending_calendars_(
            None, None, [target_calendar]
        )
        
        reminders_list = []
        
        # Since fetchRemindersMatchingPredicate_ is asynchronous, we'll use a semaphore or wait
        # A simpler way for a one-off fetch is to use the store's synchronous methods if available, 
        # but EKEventStore usually requires a callback.
        
        import threading
        event = threading.Event()
        
        def callback(reminders):
            if reminders:
                for r in reminders:
                    reminder_data = {
                        "task": r.title(),
                        "notes": r.notes() if r.notes() else "",
                        "completed": r.isCompleted(),
                        "priority": r.priority(),
                        "source": "Apple Reminders"
                    }
                    # Get due date if available
                    if r.dueDateComponents():
                        components = r.dueDateComponents()
                        reminder_data["due_date"] = f"{components.year()}-{components.month():02d}-{components.day():02d}"
                    
                    reminders_list.append(reminder_data)
            event.set()

        store.fetchRemindersMatchingPredicate_completion_(predicate, callback)
        
        # Wait up to 5 seconds for the async fetch
        event.wait(timeout=5)
        
        return reminders_list

    except Exception as e:
        print(f"Error accessing Apple Reminders: {e}")
        return []

if __name__ == "__main__":
    # Test fetch
    print("Fetching Apple Reminders...")
    tasks = get_apple_reminders("Reminders")
    for t in tasks:
        print(f"- {t['task']} (Due: {t.get('due_date', 'None')})")
