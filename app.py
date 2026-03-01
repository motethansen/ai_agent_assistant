import streamlit as st
import os
import json
import datetime
import calendar_manager
import ai_orchestration
import pandas as pd
from main import get_unified_tasks, sync_calendar_to_markdown
from observer import update_markdown_plan
from config_utils import get_config_value
from calendar_agent import CalendarAgent
from planning_agent import PlanningAgent

# Load HF_TOKEN into environment if present
get_config_value("HF_TOKEN", None)

# --- Page Configuration ---
st.set_page_config(
    page_title="AI Agent Assistant | Mission Control",
    layout="wide",
    page_icon="🤖",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for Styling ---
st.markdown("""
    <style>
    .main {
        background-color: #f5f7f9;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #4CAF50;
        color: white;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .status-active { color: #2ecc71; font-weight: bold; }
    .status-inactive { color: #e74c3c; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- State Management ---
if 'backlog' not in st.session_state:
    st.session_state.backlog = []
if 'suggested_schedule' not in st.session_state:
    st.session_state.suggested_schedule = []
if 'selected_tasks' not in st.session_state:
    st.session_state.selected_tasks = []
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'pending_booking' not in st.session_state:
    st.session_state.pending_booking = None

# --- Sidebar: System Health & Settings ---
with st.sidebar:
    st.title("⚙️ System Control")
    
    st.subheader("🌐 Service Status")
    gemini_ok = "✅" if get_config_value("GEMINI_API_KEY", None) else "❌"
    cal_id = get_config_value("CALENDAR_ID", "primary")
    st.write(f"Gemini AI: {gemini_ok}")
    st.write(f"Google Calendar: ✅ ({cal_id})")
    
    st.divider()
    st.subheader("⚡ Productivity Profile")
    chronotype = get_config_value("CHRONOTYPE", "balanced")
    dw_start = get_config_value("DEEP_WORK_START", "09:00")
    dw_end = get_config_value("DEEP_WORK_END", "12:00")
    st.write(f"Chronotype: **{chronotype.replace('_', ' ').title()}**")
    st.write(f"Deep Work: **{dw_start} - {dw_end}**")
    
    st.divider()
    obsidian_file = st.text_input("Daily Note Path", value="daily_note.md")
    logseq_dir = get_config_value("LOGSEQ_DIR", "Not Set")
    
    if st.button("🔄 Pull from Calendar (Reverse Sync)"):
        with st.spinner("Syncing..."):
            sync_calendar_to_markdown(obsidian_file)
            st.success("Reconciled!")
            st.rerun()

    if st.button("🔍 Index Vault for AI (RAG)"):
        from rag_agent import RAGAgent
        with st.spinner("Indexing..."):
            agent = RAGAgent(obsidian_file, logseq_dir)
            agent.index_vault()
            st.success("Vault indexed!")

    st.divider()
    with st.expander("❓ Help & Guide"):
        st.markdown("""
        **Getting Started:**
        1. **Sync Backlog:** Use 'Pull from Calendar' to get latest events.
        2. **Generate Plan:** Go to 'Schedule Manager' and click 'Generate Plan'.
        3. **Refine:** Edit the times in the table if needed.
        4. **Push:** Click 'Push to Calendar' to save.
        
        **Chat Agent:**
        Ask questions like "What are my snoozed emails?" or "Find flights to Paris".
        
        **Missing Keys?**
        Run `make setup` in your terminal to re-run the wizard.
        """)

# --- Header ---
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.title("🤖 AI Agent Assistant")
    st.markdown(f"**Mission Control Dashboard** | {datetime.datetime.now().strftime('%A, %B %d, %Y')}")

with col_h2:
    if st.button("🚀 Run Full Sync Loop"):
        with st.spinner("Syncing..."):
            tasks = get_unified_tasks(obsidian_file)
            service = calendar_manager.get_calendar_service()
            calendar_agent = CalendarAgent()
            busy_slots = calendar_agent.get_busy_slots_from_yml()
            result = ai_orchestration.generate_schedule(tasks, busy_slots, workspace_dir=obsidian_file, logseq_dir=logseq_dir)
            if result and "schedule" in result:
                planning_agent = PlanningAgent(service, cal_id)
                planning_agent.execute_plan(result["schedule"], obsidian_file)
                st.success("Sync complete!")
                st.rerun()

# --- Analytics Section ---
st.header("📊 Focus Analytics")
service = calendar_manager.get_calendar_service()
if service:
    managed_events = calendar_manager.get_managed_events(service, calendar_id=cal_id)
    if managed_events:
        # Calculate time per category (dummy logic for categories if not in managed_events)
        # In a real app, we'd pull category from extendedProperties or similar
        cat_data = {}
        for event in managed_events:
            start = datetime.datetime.fromisoformat(event['start'].replace('Z', ''))
            end = datetime.datetime.fromisoformat(event['end'].replace('Z', ''))
            duration = (end - start).total_seconds() / 3600
            cat = "General" # Default
            # Attempt to guess category from title
            for c in ["winedragons", "dev", "writing", "learning"]:
                if c in event['task'].lower(): cat = c.title()
            
            cat_data[cat] = cat_data.get(cat, 0) + duration
        
        df_chart = pd.DataFrame(list(cat_data.items()), columns=['Category', 'Hours'])
        st.bar_chart(df_chart, x='Category', y='Hours', color="#4CAF50")
    else:
        st.info("No AI-managed events found for analytics yet.")

st.divider()

# --- Main Columns ---
left_col, right_col = st.columns([1, 1])

with left_col:
    st.header("📋 Unified Backlog")
    if st.button("🔍 Scan Backlog"):
        st.session_state.backlog = get_unified_tasks(obsidian_file)
    
    if st.session_state.backlog:
        task_names = [f"[{t['source'][0]}] {t['task']}" for t in st.session_state.backlog]
        st.session_state.selected_tasks = st.multiselect("Select tasks to schedule specifically:", task_names)
        
        df_backlog = pd.DataFrame(st.session_state.backlog)
        st.dataframe(df_backlog[["source", "category", "task", "due_date"]], width="stretch", hide_index=True)
    else:
        st.info("Backlog is empty.")

with right_col:
    st.header("📅 Schedule Manager")
    tab1, tab2 = st.tabs(["AI Brainstorm", "Manual Edit"])
    
    with tab1:
        if st.button("🧠 Generate Plan"):
            with st.spinner("AI is thinking..."):
                tasks_to_send = st.session_state.backlog
                # If user selected specific tasks, prioritize them
                if st.session_state.selected_tasks:
                    # Filter backlog to only include selected tasks
                    selected_names = [t.split("] ", 1)[1] for t in st.session_state.selected_tasks]
                    tasks_to_send = [t for t in st.session_state.backlog if t['task'] in selected_names]
                
                service = calendar_manager.get_calendar_service()
                calendar_agent = CalendarAgent()
                busy_slots = calendar_agent.get_busy_slots_from_yml()
                result = ai_orchestration.generate_schedule(tasks_to_send, busy_slots, morning_mode=True, workspace_dir=obsidian_file, logseq_dir=logseq_dir)
                if result:
                    st.session_state.suggested_schedule = result.get("schedule", [])
        
        if st.session_state.suggested_schedule:
            # Display as editable dataframe
            df_sched = pd.DataFrame(st.session_state.suggested_schedule)
            # Clean up times for display
            df_sched['start_display'] = df_sched['start'].apply(lambda x: x.split('T')[1][:5])
            df_sched['end_display'] = df_sched['end'].apply(lambda x: x.split('T')[1][:5])
            
            edited_df = st.data_editor(df_sched[["start_display", "end_display", "task", "category"]], width="stretch")
            if st.button("🚀 Push to Calendar"):
                # For now, we push the original suggestion
                service = calendar_manager.get_calendar_service()
                if service:
                    planning_agent = PlanningAgent(service, cal_id)
                    planning_agent.execute_plan(st.session_state.suggested_schedule, obsidian_file)
                    st.success("Plan pushed to calendar and markdown!")

                st.session_state.suggested_schedule = []

    with tab2:
        st.subheader("Live Calendar Sync")
        if service:
            managed = calendar_manager.get_managed_events(service, calendar_id=cal_id)
            if managed:
                for m in managed:
                    time_range = f"{m['start'].split('T')[1][:5]} - {m['end'].split('T')[1][:5]}"
                    st.success(f"**{time_range}**: {m['task']}")
            else:
                st.write("No AI events today.")

st.divider()

# --- Chat Interface ---
st.header("🤖 AI Agent Chat")
chat_container = st.container(height=300)

with chat_container:
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

if prompt := st.chat_input("Ask me about your emails, calendar, or books..."):
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.chat_history.append({"role": "user", "content": prompt})

    # Get AI response
    with st.chat_message("assistant"):
        with st.spinner("Consulting agents..."):
            try:
                import gmail_agent
                from book_agent import BookAgent
                from travel_agent import TravelAgent
                
                # Gather context
                service = calendar_manager.get_calendar_service()
                calendar_agent = CalendarAgent()
                busy_slots = calendar_agent.get_busy_slots_from_yml()
                backlog = get_unified_tasks(obsidian_file)
                
                gmail_service = gmail_agent.get_gmail_service()
                snoozed = []
                filtered = []
                if gmail_service:
                    snoozed = gmail_agent.get_snoozed_emails(gmail_service)
                    filters = gmail_agent.load_filters()
                    if filters:
                        filtered = gmail_agent.get_filtered_emails(gmail_service, filters)
                
                book_agent = BookAgent()
                books_summary = book_agent.get_summary()

                context_payload = {
                    "backlog": backlog,
                    "calendar_busy_slots": busy_slots,
                    "gmail_snoozed": snoozed,
                    "gmail_filtered": filtered,
                    "books_library": books_summary,
                    "current_time": datetime.datetime.now().astimezone().isoformat()
                }

                ai_prompt = f"""
                User Question: '{prompt}'
                
                CONTEXT:
                {json.dumps(context_payload)}
                
                INSTRUCTIONS:
                You are a professional AI Assistant with access to the user's calendar, emails, and files.
                
                1. If the user wants to book an event, you MUST include a "schedule" array in your JSON.
                2. If the user asks a question, answer it in the "response" field.
                3. Use the "actions" field for system tasks (read_book, search_books, index_book, plan_travel).
                
                OUTPUT FORMAT:
                You MUST return a JSON object (optionally wrapped in markdown code blocks) with:
                - "response": "Your conversational answer here"
                - "schedule": [{{ "task": "Event Name", "start": "ISO8601", "end": "ISO8601", "category": "Category" }}]
                - "actions": [{{ "type": "action_type", ... }}]
                
                Ensure all dates use the correct year (2026) and include the timezone offset provided in 'current_time'.
                """
                model_to_use = ai_orchestration.get_routing("chat")
                
                if model_to_use == "ollama":
                    response_text = ai_orchestration.ollama_generate(ai_prompt)
                else:
                    import google.genai as genai
                    client = genai.Client(api_key=ai_orchestration.api_key)
                    response = client.models.generate_content(
                        model='gemini-flash-latest',
                        contents=ai_prompt
                    )
                    response_text = response.text

                # Try to extract JSON for actions (like read_book)
                try:
                    start_idx = response_text.find('{')
                    end_idx = response_text.rfind('}')
                    if start_idx != -1 and end_idx != -1:
                        data = json.loads(response_text[start_idx:end_idx+1])
                        if "response" in data:
                            st.markdown(data["response"])
                            response_text = data["response"]
                        
                        # Process Schedule (Calendar)
                        if "schedule" in data and data["schedule"]:
                            st.session_state.pending_booking = data["schedule"]
                        
                        if "actions" in data:
                            for action in data["actions"]:
                                if action["type"] == "read_book":
                                    with st.status(f"Reading {os.path.basename(action['path'])}..."):
                                        content = book_agent.read_book_content(action["path"])
                                        st.write(f"**Findings from {os.path.basename(action['path'])}:**")
                                        st.info(content)
                                        # Provide a clickable link (local file link might be blocked by browser, so we show the path clearly)
                                        st.code(f"File Path: {action['path']}")
                                        # Append to response text for history
                                        response_text += f"\n\nFindings: {content}\nPath: {action['path']}"
                                elif action["type"] == "index_book":
                                    with st.status(f"Indexing {os.path.basename(action['path'])}..."):
                                        msg = book_agent.index_book(action["path"])
                                        st.success(msg)
                                        response_text += f"\n\nSystem: {msg}"
                                elif action["type"] == "search_books":
                                    with st.status(f"Searching library for '{action['query']}'..."):
                                        results = book_agent.search_books(action["query"])
                                        st.markdown(results)
                                        response_text += f"\n\nSearch Results: {results}"
                                elif action["type"] == "plan_travel":
                                    with st.status(f"Searching flights and travel for '{action['query']}'..."):
                                        travel_agent = TravelAgent()
                                        result = travel_agent.plan_travel(action["query"])
                                        st.markdown(result)
                                        response_text += f"\n\nTravel Plan: {result}"
                        else:
                            st.markdown(response_text)
                    else:
                        st.markdown(response_text)
                except:
                    st.markdown(response_text)

                st.session_state.chat_history.append({"role": "assistant", "content": response_text})
            except Exception as e:
                st.error(f"Error: {e}")

# --- Pending Booking Confirmation ---
if st.session_state.pending_booking:
    with st.chat_message("assistant"):
        st.write("📅 I'm ready to book these events:")
        for item in st.session_state.pending_booking:
            st.write(f"- **{item['task']}**: {item['start'].split('T')[1][:5]} to {item['end'].split('T')[1][:5]}")
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("✅ Confirm"):
                with st.spinner("Booking..."):
                    service = calendar_manager.get_calendar_service()
                    planning_agent = PlanningAgent(service, cal_id)
                    planning_agent.execute_plan(st.session_state.pending_booking, obsidian_file)
                    st.success("Events booked!")
                    st.session_state.pending_booking = None
                    st.rerun()
        with col2:
            if st.button("❌ Cancel"):
                st.session_state.pending_booking = None
                st.rerun()

st.divider()
st.caption(f"AI Agent Assistant v1.1 | Mission Control")
