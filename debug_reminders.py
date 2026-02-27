import subprocess
import json
import os

DATA_FILE = "datainput/reminders.json"

# Delimiter used between items in AppleScript bulk output
DELIM = "|||~|||" 

def _fetch_bulk_property(list_name, prop_expression, timeout=120):
    """
    Use bulk property access (e.g. 'name of every reminder') which sends
    a single Apple Event instead of one per item. Returns a list of strings.
    """
    script = f'''
    tell application "Reminders"
        set targetList to list "{list_name}"
        set propList to {prop_expression} of every reminder of targetList
        set AppleScript's text item delimiters to "{DELIM}"
        set outStr to propList as string
        set AppleScript's text item delimiters to ""
        return outStr
    end tell
    '''
    result = subprocess.run(
        ['osascript', '-e', script],
        capture_output=True, text=True, timeout=timeout
    )
    raw = result.stdout.strip()
    if not raw:
        return []
    return raw.split(DELIM)


def get_apple_reminders_raw(list_name="Reminders"):
    """
    Fetches ALL reminders using fast bulk property access (one Apple Event
    per property), then filters out completed items in Python.
    """
    print(f"Connecting to Reminders app for list: '{list_name}'...")

    try:
        # Step 1 – bulk-fetch completed flags (fast, single Apple Event)
        print("  Fetching completion status...")
        completed_flags = _fetch_bulk_property(list_name, "completed", timeout=120)
        total = len(completed_flags)
        if total == 0:
            print("ℹ️  No reminders found in list.")
            return ""
        incomplete_count = sum(1 for c in completed_flags if c.strip() == "false")
        print(f"  Found {total} total reminders, {incomplete_count} incomplete.")
        if incomplete_count == 0:
            print("ℹ️  All reminders are completed.")
            return ""

        # Step 2 – bulk-fetch names
        print("  Fetching names...")
        names = _fetch_bulk_property(list_name, "name", timeout=180)

        # Step 3 – bulk-fetch bodies
        print("  Fetching notes/bodies...")
        bodies = _fetch_bulk_property(list_name, "body", timeout=180)

        # Step 4 – bulk-fetch due dates
        print("  Fetching due dates...")
        dates = _fetch_bulk_property(list_name, "due date", timeout=180)

        # Step 5 – combine & filter incomplete only
        out_parts = []
        for i in range(total):
            if completed_flags[i].strip() == "false":
                name = names[i].strip() if i < len(names) else ""
                body = bodies[i].strip() if i < len(bodies) else ""
                date = dates[i].strip() if i < len(dates) else ""
                # Treat AppleScript 'missing value' as empty
                if body == "missing value":
                    body = ""
                if date == "missing value":
                    date = ""
                out_parts.append(f"{name}||{body}||{date}")

        print(f"  ✅ Extracted {len(out_parts)} incomplete reminders.")
        return f"COUNT:{len(out_parts)}###" + "###".join(out_parts)

    except subprocess.TimeoutExpired as e:
        print(f"❌ Timed out during bulk fetch: {e}")
        return ""
    except Exception as e:
        print(f"❌ Error: {e}")
        return ""

def get_all_lists():
    """Fetch all list names from the Reminders app."""
    script = '''
    tell application "Reminders"
        set allLists to name of every list
        set output to ""
        repeat with l in allLists
            set output to output & l & "###"
        end repeat
        return output
    end tell
    '''
    try:
        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=30)
        raw = result.stdout.strip()
        lists = [l.strip() for l in raw.split("###") if l.strip()]
        return lists
    except Exception as e:
        print(f"❌ Error fetching lists: {e}")
        return []

def prompt_list_selection():
    """Display all Reminders lists and prompt the user to select one."""
    print("--- 📋 Apple Reminders Lists ---")
    lists = get_all_lists()
    if not lists:
        print("No lists found.")
        return None

    for i, name in enumerate(lists, 1):
        print(f"  {i}. {name}")

    print()
    while True:
        choice = input("Select a list number to extract from (or 'q' to quit): ").strip()
        if choice.lower() == 'q':
            return None
        try:
            idx = int(choice)
            if 1 <= idx <= len(lists):
                return lists[idx - 1]
            print(f"Please enter a number between 1 and {len(lists)}.")
        except ValueError:
            print("Invalid input. Enter a number or 'q' to quit.")

def sync_reminders(list_name=None):
    if list_name is None:
        list_name = prompt_list_selection()
    if list_name is None:
        print("No list selected. Exiting.")
        return

    print(f"\n--- 🔄 Syncing Apple Reminders from '{list_name}' to Local Storage ---")

    # 1. Fetch current reminders from app
    raw_data = get_apple_reminders_raw(list_name)
    if not raw_data:
        print("No data extracted.")
        return

    new_reminders = []
    records = raw_data.split("###")
    
    # Check for the COUNT prefix
    if records[0].startswith("COUNT:"):
        count = records[0].split(":")[1]
        print(f"Found {count} incomplete reminders. Parsing...")
        records = records[1:] # Skip the count record

    for rec in records:
        if not rec.strip(): continue
        parts = rec.split("||")
        if len(parts) >= 3:
            new_reminders.append({
                "task": parts[0].strip(),
                "notes": parts[1].strip(),
                "due_date": parts[2].strip() if parts[2].strip() else None,
                "source": "Apple Reminders"
            })


    # 2. Load existing data
    existing_reminders = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                existing_reminders = json.load(f)
        except:
            existing_reminders = []

    # 3. Deduplicate (Check by task name and notes)
    # We use a set of keys to track what we already have
    existing_keys = { (r['task'], r['notes']) for r in existing_reminders }
    
    added_count = 0
    for r in new_reminders:
        key = (r['task'], r['notes'])
        if key not in existing_keys:
            existing_reminders.append(r)
            existing_keys.add(key)
            added_count += 1

    # 4. Save back to JSON
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(existing_reminders, f, indent=4)

    print(f"✅ Sync complete. Added {added_count} new reminders. Total stored: {len(existing_reminders)}")

if __name__ == "__main__":
    sync_reminders()
