# Building an AI-Powered Markdown-to-Calendar Sync: My Journey into Agentic Workflows

## The Vision: A Seamless Bridge Between My Notes and My Life

I’ve always found a friction point between my local markdown notes (my "second brain" in Obsidian and Logseq) and my actual schedule in Google Calendar. My tasks live in text files, while my time lives in a calendar. Managing a complex workload across devices (my MacBook and Ubuntu machine) often felt like a manual logistics puzzle.

What if my notes could talk to my calendar? What if an AI could look at my tasks, see when I’m *actually* free, and intelligently slot them into my day?

In this project, I’m exploring the world of **AI agents as assistants**. I’m not just writing code; I’m collaborating with AI tools (like Gemini CLI) to architect and build this bridge. This post documents the process—the successes, the frustrating "gotchas," and the technical architecture of a system that manages my time so I can focus on my work.

---

## Phase 1: Setting the Foundation (and Avoiding Dependency Hell)

The first step in any multi-device project is standardization. If it doesn't run on both my Mac and my Linux box, it's not a solution; it's a headache.

### The Strategy
We decided on a Python-based stack for its portability and rich ecosystem:
- **`watchdog`**: To listen for real-time file changes without polling.
- **`google-api-python-client`**: To interface with Google Calendar.
- **`google-generativeai` (or OpenAI)**: The "brain" that will handle the scheduling logic.

### 🛠️ The Setup (MacBook & Ubuntu)
To keep the environment identical across both machines, I followed this ritual:

```bash
# Create the isolated sandbox
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install the dependencies from our blueprint
pip install -r requirements.txt
```

### 💡 Lesson Learned: The Virtual Environment is Not Optional
When you’re building something that interacts with local files and cloud APIs, keep your environment clean. I set up a dedicated `venv` inside the project folder. 

**Hint for others:** If you're syncing your vault across devices (e.g., via iCloud or Syncthing), don't sync the `venv` folder! Keep it local to each machine or use a `requirements.txt` to recreate it.

### Current Status
We've mapped out the five-phase plan:
1. **Environment Foundation** (Current)
2. **The Local Observer Layer** (Monitoring `.md` files)
3. **Calendar & Appointments Layer** (Google API integration)
4. **AI Orchestration** (The scheduling brain)
5. **The Sync & Write-Back Loop** (Final integration)

---

## Phase 2: The Local Observer Layer (Turning Static Notes Into Active Triggers)

The heart of the bridge is knowing *when* to cross it. I didn’t want to run a manual script every time I updated my notes; I wanted the system to feel invisible.

### The Strategy
We used the `watchdog` library in Python to monitor my `.md` files. This is where the **PatternMatchingEventHandler** came in handy. It listens specifically for modifications to markdown files and ignores everything else.

### 💡 Lesson Learned: The "Double Trigger" Gotcha
One interesting thing I discovered is that many modern text editors (like Obsidian or VS Code) often trigger *multiple* save events for a single user action. This can cause the script to fire twice in rapid succession.

**Hint for others:** I implemented a simple `time.time()` check in the event handler to debounce these triggers, ensuring the AI is only called once per save.

### The Parsing Logic
Instead of over-engineering a complex markdown AST parser, we used a simple but robust Regex approach to target a specific header: `## Tasks`. This keeps the script lightweight and focused.

```python
# A snippet of our simple but effective parsing logic
pattern = r"## Tasks\s*(.*?)(?=\n##|$)"
match = re.search(pattern, content, re.DOTALL)
```

### Current Status
- [x] Environment Foundation
- [x] Local Observer Layer (Monitoring & Parsing)
- [ ] Calendar & Appointments Layer (Next)
- [ ] AI Orchestration
- [ ] The Sync & Write-Back Loop

---
