import streamlit as st
import os
import json
import datetime
import calendar_manager
import ai_orchestration
import pandas as pd
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
if 'selected_tasks' not in st.session_state:
    st.session_state.selected_tasks = []

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
            busy_slots = calendar_manager.get_busy_slots(service, calendar_id=cal_id)
            result = ai_orchestration.generate_schedule(tasks, busy_slots, workspace_dir=obsidian_file, logseq_dir=logseq_dir)
            if result and "schedule" in result:
                calendar_manager.create_events(service, result["schedule"], calendar_id=cal_id)
                update_markdown_plan(obsidian_file, result["schedule"])
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
        st.dataframe(df_backlog[["source", "category", "task", "due_date"]], use_container_width=True, hide_index=True)
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
                busy_slots = calendar_manager.get_busy_slots(service, calendar_id=cal_id)
                result = ai_orchestration.generate_schedule(tasks_to_send, busy_slots, morning_mode=True, workspace_dir=obsidian_file, logseq_dir=logseq_dir)
                if result:
                    st.session_state.suggested_schedule = result.get("schedule", [])
        
        if st.session_state.suggested_schedule:
            # Display as editable dataframe
            df_sched = pd.DataFrame(st.session_state.suggested_schedule)
            # Clean up times for display
            df_sched['start_display'] = df_sched['start'].apply(lambda x: x.split('T')[1][:5])
            df_sched['end_display'] = df_sched['end'].apply(lambda x: x.split('T')[1][:5])
            
            edited_df = st.data_editor(df_sched[["start_display", "end_display", "task", "category"]], use_container_width=True)
            
            if st.button("🚀 Push to Calendar"):
                # (Logic to convert edited_df back to ISO if user changed times would go here)
                # For now, we push the original suggestion
                service = calendar_manager.get_calendar_service()
                calendar_manager.create_events(service, st.session_state.suggested_schedule, calendar_id=cal_id)
                update_markdown_plan(obsidian_file, st.session_state.suggested_schedule)
                st.success("Synced!")
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
st.caption(f"AI Agent Assistant v1.1 | Mission Control")
