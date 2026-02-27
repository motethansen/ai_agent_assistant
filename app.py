import streamlit as st
import os
import json
import datetime
import calendar_manager
import ai_orchestration
from main import get_unified_tasks, get_config_value

st.set_page_config(page_title="AI Agent Assistant", layout="wide", page_icon="🤖")

st.title("🤖 AI Agent Assistant Dashboard")

# Initialize Session State for schedule if it doesn't exist
if 'suggested_schedule' not in st.session_state:
    st.session_state.suggested_schedule = None

# Sidebar - Settings and Configuration
st.sidebar.header("Settings")
obsidian_file = st.sidebar.text_input("Obsidian File to Monitor", value="daily_note.md")

if os.path.exists(".config"):
    with st.sidebar.expander("View .config Settings"):
        with open(".config", "r") as f:
            st.code(f.read(), language="properties")

# Main Dashboard - Task Backlog
st.header("📋 Unified Task Backlog")

if st.button("🔄 Refresh Backlog"):
    if os.path.exists(obsidian_file):
        backlog = get_unified_tasks(obsidian_file)
        st.session_state.backlog = backlog
        st.success(f"Retrieved {len(backlog)} tasks.")
    else:
        st.error(f"File '{obsidian_file}' not found.")

if 'backlog' in st.session_state:
    # Group by category
    categories = {}
    for t in st.session_state.backlog:
        cat = t.get("category", "Uncategorized")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(t)
    
    cols = st.columns(2)
    for idx, (category, tasks) in enumerate(categories.items()):
        with cols[idx % 2]:
            with st.expander(f"**{category}** ({len(tasks)} tasks)"):
                for t in tasks:
                    due = f" (Due: {t['due_date']})" if t.get('due_date') else ""
                    st.write(f"- {t['task']}{due} [{t['source']}]")

# Scheduler Suggestion
st.divider()
st.header("🗓️ AI Schedule Suggestion")

col1, col2 = st.columns(2)

with col1:
    if st.button("🧠 Generate Suggested Schedule"):
        if 'backlog' not in st.session_state:
            st.warning("Please refresh the backlog first.")
        else:
            with st.spinner("Consulting the AI scheduler..."):
                calendar_id = get_config_value("CALENDAR_ID", "primary")
                service = calendar_manager.get_calendar_service()
                if service:
                    busy_slots = calendar_manager.get_busy_slots(service, calendar_id=calendar_id)
                    result = ai_orchestration.generate_schedule(st.session_state.backlog, busy_slots, morning_mode=True)
                    if result:
                        st.session_state.suggested_schedule = result.get("schedule", [])
                        st.session_state.ai_suggestions = result.get("suggestions", [])
                    else:
                        st.error("AI failed to generate a schedule.")
                else:
                    st.error("Could not connect to Google Calendar. Check credentials.json.")

if st.session_state.suggested_schedule:
    if st.session_state.ai_suggestions:
        st.subheader("💡 AI Categorization Suggestions")
        for sug in st.session_state.ai_suggestions:
            st.info(f"**{sug['task']}**: Suggesting category **{sug['suggested_category']}**")

    st.subheader("📅 Proposed Schedule for Today")
    
    # Format for display
    display_data = []
    for item in st.session_state.suggested_schedule:
        display_data.append({
            "Time": f"{item['start'].split('T')[1][:5]} - {item['end'].split('T')[1][:5]}",
            "Task": item['task'],
            "Category": item.get('category', 'Personal')
        })
    st.table(display_data)

    with col2:
        if st.button("✅ Confirm and Sync to Google Calendar"):
            with st.spinner("Syncing..."):
                calendar_id = get_config_value("CALENDAR_ID", "primary")
                service = calendar_manager.get_calendar_service()
                if service:
                    calendar_manager.create_events(service, st.session_state.suggested_schedule, calendar_id=calendar_id)
                    st.success(f"Successfully synced to Google Calendar: {calendar_id}!")
                    # Optional: Update markdown too
                    from main import update_markdown_plan

                    update_markdown_plan(obsidian_file, st.session_state.suggested_schedule)
                    st.session_state.suggested_schedule = None # Clear after sync
                else:
                    st.error("Failed to connect to Calendar for sync.")

# Footer
st.divider()
st.caption(f"AI Agent Assistant v1.0 | Current Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
