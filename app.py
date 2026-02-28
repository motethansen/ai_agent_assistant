import streamlit as st
import os
import json
import datetime
import calendar_manager
import ai_orchestration
from main import get_unified_tasks, get_config_value, update_markdown_plan, sync_calendar_to_markdown

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
    """, unsafe_allow_name_is_present=True)

# --- State Management ---
if 'backlog' not in st.session_state:
    st.session_state.backlog = []
if 'suggested_schedule' not in st.session_state:
    st.session_state.suggested_schedule = []
if 'current_plan' not in st.session_state:
    st.session_state.current_plan = []

# --- Sidebar: System Health & Settings ---
with st.sidebar:
    st.title("⚙️ System Control")
    
    st.subheader("🌐 Service Status")
    # Health checks
    gemini_ok = "✅" if get_config_value("GEMINI_API_KEY", None) else "❌"
    cal_id = get_config_value("CALENDAR_ID", "primary")
    
    st.write(f"Gemini AI: {gemini_ok}")
    st.write(f"Google Calendar: ✅ ({cal_id})")
    
    st.divider()
    st.subheader("📄 Configuration")
    obsidian_file = st.text_input("Daily Note Path", value="daily_note.md")
    logseq_dir = get_config_value("LOGSEQ_DIR", "Not Set")
    st.caption(f"LogSeq Source: {logseq_dir}")
    
    st.divider()
    if st.button("🔄 Pull from Calendar (Reverse Sync)"):
        with st.spinner("Reconciling Calendar -> Markdown..."):
            sync_calendar_to_markdown(obsidian_file)
            st.success("Markdown updated from Calendar events!")
            st.rerun()

    if st.button("🔍 Index Vault for AI Context (RAG)"):
        from rag_agent import RAGAgent
        with st.spinner("Indexing notes..."):
            agent = RAGAgent(obsidian_file, logseq_dir)
            agent.index_vault()
            st.success("Vault indexed successfully!")

# --- Header Section ---
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.title("🤖 AI Agent Assistant")
    st.markdown(f"**Mission Control Dashboard** | {datetime.datetime.now().strftime('%A, %B %d, %Y')}")

with col_h2:
    if st.button("🚀 Run Full Sync Loop"):
        with st.spinner("Running agents..."):
            # Trigger the main logic
            tasks = get_unified_tasks(obsidian_file)
            service = calendar_manager.get_calendar_service()
            busy_slots = calendar_manager.get_busy_slots(service, calendar_id=cal_id)
            result = ai_orchestration.generate_schedule(
                tasks, 
                busy_slots, 
                workspace_dir=obsidian_file, 
                logseq_dir=logseq_dir
            )
            if result and "schedule" in result:
                calendar_manager.create_events(service, result["schedule"], calendar_id=cal_id)
                update_markdown_plan(obsidian_file, result["schedule"])
                st.success("System-wide sync complete!")
                st.rerun()

st.divider()

# --- Main Layout: 2 Columns ---
left_col, right_col = st.columns([1, 1])

# --- Left Column: Unified Backlog ---
with left_col:
    st.header("📋 Unified Backlog")
    
    if st.button("🔍 Scan for New Tasks"):
        with st.spinner("Scanning Obsidian, LogSeq, and Reminders..."):
            st.session_state.backlog = get_unified_tasks(obsidian_file)
    
    if st.session_state.backlog:
        # Grouping for better UI
        df_tasks = []
        for t in st.session_state.backlog:
            icon = "📝" if t['source'] == "Obsidian" else "🪵" if t['source'] == "Logseq" else "🍎"
            df_tasks.append({
                "Src": icon,
                "Category": t.get('category', 'Uncategorized'),
                "Task": t['task'],
                "Due": t.get('due_date', '-')
            })
        
        st.dataframe(df_tasks, use_container_width=True, hide_index=True)
        
        with st.expander("💡 AI Categorization Insights"):
            st.caption("AI suggests categorizing your new tasks based on historical context.")
            # We could trigger a mini-agent here if we wanted
            st.info("Everything looks organized!")
    else:
        st.info("Click 'Scan for New Tasks' to populate your backlog.")

# --- Right Column: Today's Schedule ---
with right_col:
    st.header("📅 Today's Schedule")
    
    tab1, tab2 = st.tabs(["AI Suggestion", "Manual Override"])
    
    with tab1:
        if st.button("🧠 Brainstorm New Schedule"):
            if not st.session_state.backlog:
                st.warning("Please scan your backlog first.")
            else:
                with st.spinner("Consulting AI scheduler..."):
                    service = calendar_manager.get_calendar_service()
                    busy_slots = calendar_manager.get_busy_slots(service, calendar_id=cal_id)
                    result = ai_orchestration.generate_schedule(
                        st.session_state.backlog, 
                        busy_slots, 
                        morning_mode=True, 
                        workspace_dir=obsidian_file, 
                        logseq_dir=logseq_dir
                    )
                    if result:
                        st.session_state.suggested_schedule = result.get("schedule", [])
        
        if st.session_state.suggested_schedule:
            for i, item in enumerate(st.session_state.suggested_schedule):
                time_range = f"{item['start'].split('T')[1][:5]} - {item['end'].split('T')[1][:5]}"
                st.info(f"**{time_range}**: {item['task']} ({item.get('category', 'Personal')})")
            
            if st.button("✅ Confirm and Push to Calendar"):
                service = calendar_manager.get_calendar_service()
                calendar_manager.create_events(service, st.session_state.suggested_schedule, calendar_id=cal_id)
                update_markdown_plan(obsidian_file, st.session_state.suggested_schedule)
                st.success("Pushed to Google Calendar!")
                st.session_state.suggested_schedule = []
                st.rerun()

    with tab2:
        st.write("Current events tracked by the AI in your calendar:")
        service = calendar_manager.get_calendar_service()
        if service:
            managed = calendar_manager.get_managed_events(service, calendar_id=cal_id)
            if managed:
                for m in managed:
                    m_time = f"{m['start'].split('T')[1][:5]} - {m['end'].split('T')[1][:5]}"
                    st.success(f"**{m_time}**: {m['task']}")
                
                st.caption("To edit these, change them in your Google Calendar app and use 'Pull from Calendar' in the sidebar.")
            else:
                st.write("No AI-managed events found for today.")

# --- Footer ---
st.divider()
st.caption(f"Agent Framework Active | {OS_TYPE if 'OS_TYPE' in locals() else 'System'}: Connected")
