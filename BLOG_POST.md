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

## Phase 4: The AI Orchestration (The Scheduler Brain)

Now for the "magic." I have my tasks (from markdown) and my availability (from Google Calendar). I need an orchestrator to sit in the middle and make smart decisions.

### The Strategy
We chose the Gemini 1.5 Flash model for its speed and its ability to follow strict formatting instructions. I'm feeding it a "Context Payload":
- **Current Tasks:** A list of what I need to do.
- **Busy Slots:** A list of when I'm already booked.
- **The Prompt:** Explicit instructions to fit tasks into free slots and return the result *only* as a JSON array.

### 💡 Lesson Learned: The "Deprecated Package" Pivot
Software moves fast, and AI software moves at lightspeed. Halfway through my Phase 4 development, I ran into a 404 error and a warning that the `google-generativeai` package had been deprecated in favor of a new, cleaner SDK: `google-genai`.

**Hint for others:** If you see "models/gemini-1.5-flash not found" or package warnings, it’s time to pivot. I had to:
1.  Update my `requirements.txt` to `google-genai`.
2.  Rewrite the AI script to use the new `genai.Client` class.
3.  The result? A cleaner API and more reliable responses. Don’t be afraid to refactor when the tech shifts underneath you.

### 💡 Lesson Learned: The "Model Name" Rabbit Hole
Even after switching to the new SDK, I hit a wall with a `404 Not Found` error for the model name. It turns out that depending on your specific API key and region, the model you expect (like `gemini-1.5-flash`) might be named differently (like `gemini-flash-latest`).

**Hint for others:** If you're getting 404 errors, don't guess the model name. Write a tiny diagnostic script using `client.models.list()` to see exactly what your API key is allowed to use. It saved me hours of frustration.

### 💡 Lesson Learned: The JSON "Sanity Check"
One common failure with AI is "hallucination"—sometimes it adds conversational filler like "Sure! Here is your schedule:". 

**Hint for others:** I implemented a simple cleanup function in Python to strip away any markdown code blocks (like ```json) that the AI might wrap around its response. This ensures the JSON is always "parse-able" and won't crash the script.

### 🛡️ Security First: Use a `.env` and `.config` File
Never hard-code your API keys or local paths directly into your scripts. I created a `.config` file (and a `.env`) to keep sensitive data separate from the code.

**Key Configuration:**
- **`GEMINI_API_KEY`**: Your brain's fuel.
- **`WORKSPACE_DIR`**: This is critical! It tells the AI exactly where your Obsidian vault lives. By setting this to your local vault path (e.g., `/Users/michael/Obsidian/SecondBrain`), the assistant gains the ability to organize your files and create new notes exactly where you need them.
- **`CALENDAR_ID`**: Point the assistant to a specific Google Calendar if you don't want to use your primary one.

### Current Status
- [x] Environment Foundation
- [x] Local Observer Layer
- [x] Calendar & Appointments Layer
- [x] AI Orchestration (Prompt & Logic)
- [x] The Sync & Write-Back Loop

---

## Phase 5: The Sync & Write-Back Loop (Closing the Circle)

The final step was making the AI's decisions visible and actionable. It's one thing for a script to *calculate* a schedule; it's another for that schedule to magically appear in your calendar and your notes.

### The Strategy
We created a final `main.py` that orchestrates the entire lifecycle:
1.  **Watchdog** triggers when I save my daily note.
2.  **Parser** extracts my `## Tasks`.
3.  **Calendar Manager** fetches my current `Busy` blocks.
4.  **AI Orchestration** builds a JSON-formatted plan.
5.  **Sync Back:** The script creates actual events in Google Calendar and then overwrites the `## Today's Plan` section in my markdown file with the finalized times.

### 💡 Lesson Learned: The "Visual Feedback" Loop
I discovered that having the script write back to the markdown file is the most satisfying part. Seeing a bulleted list of times appear in your notes seconds after you save is the "Aha!" moment where the AI truly feels like a helpful assistant.

### Conclusion: My AI Agent is Alive
This project taught me that "AI agents" aren't just large language models; they are the glue between those models and our everyday tools. By bridging local markdown files with cloud APIs, I've built a system that manages the logistics so I can focus on the creative work.

---

## Final Challenges and Outcomes: Toward Full Agency

The final stretch of this experiment was about pushing the boundaries of what a "local assistant" can actually do. It wasn't just about scheduling anymore; it was about **agency**.

### 💡 Lesson Learned: The "Reminders" Permission Wall
One of the most frustrating challenges was integrating **Apple Reminders**. macOS has strict privacy silos. My first attempt using the `EventKit` framework hit a "Permission Denied" wall that even system-level resets couldn't consistently bridge for a CLI tool.
**The Outcome:** I pivoted to a **Local JSON Buffer** strategy. I wrote a dedicated extraction script using AppleScript (which macOS treats as "Automation" rather than "Data Access") to pull reminders into a local `datainput/reminders.json` file. This decoupled the AI from the OS's slow permission loops and made the assistant lightning-fast.

### 💡 Lesson Learned: The Multi-LLM Routing Engine
As I added more tasks, I realized that using a top-tier cloud model like Gemini for *everything* was overkill and occasionally hit rate limits. 
**The Outcome:** I implemented a **Multi-LLM Routing Engine**. The assistant can now toggle between Gemini (for complex scheduling), Ollama (for local, private chat), and OpenClaw. This means I can run my daily "Morning Planning" on a local Llama 3 model without ever sending my private data to the cloud.

### 💡 Lesson Learned: Bridging the "Write Access" Gap
The "Aha!" moment came when I realized the AI could do more than just talk; it could **act**. Initially, the AI would say, "I can't create folders for you."
**The Outcome:** I built a **File System Agent**. By giving the AI a structured way to propose "Actions" (like `create_folder` or `write_file`), the assistant can now manage my Obsidian vault directly. If I ask it to organize my reminders into a new project folder, it generates the plan, asks for my confirmation (`y/n`), and then physically creates the directory and the `.md` notes.

### Conclusion: The Birth of a Modular Platform
What started as a simple sync script has evolved into a **modular agentic platform**. 
- It handles **Multi-Source Backlogs** (Obsidian + Apple Reminders).
- It manages **Multi-LLM Routing** (Gemini + Ollama + OpenClaw).
- It possesses **File System Agency** (Safely managing your local files).
- It is **Extensible** (Users can scaffold their own agents with `/create-agent`).

The journey from a "script" to an "agent" is about trust and feedback loops. By keeping the human in the loop for file operations and calendar syncs, I've built a system that feels like a powerful extension of my own productivity workflow.

**What's next?** I'm opening up the framework for custom agents. The assistant now supports isolated Git repositories for user-defined agents, encouraging a community of "specialist" agents that can be shared and forked.

---


