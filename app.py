import streamlit as st
import os
import json
import calendar_manager
from ai_orchestration import generate_schedule

st.set_page_config(page_title="AI Agent Assistant", layout="wide")

st.title("🤖 AI Agent Assistant Dashboard")

# Sidebar - Settings and Configuration
st.sidebar.header("Settings")
if os.path.exists(".config"):
    with open(".config", "r") as f:
        st.sidebar.text_area(".config Content", f.read(), height=200)

# Main Dashboard - Task Backlog
st.header("📋 Unified Task Backlog")
st.info("Retrieve tasks from Obsidian and Apple Reminders to see your current backlog.")

# Mock Backlog (to be replaced with real retrieval logic in Phase 7/8)
backlog = {
    "Ref.team Book editing": ["Finish Chapter 3 proofreading", "Email the editor"],
    "winedragons": ["Review wireframes for homepage"],
    "Learning Thai": ["Study 10 new vocabulary words"],
    "Personal": ["30 mins morning exercise", "Rest and meditate"]
}

for category, tasks in backlog.items():
    with st.expander(f"**{category}** ({len(tasks)} tasks)"):
        for task in tasks:
            st.checkbox(task, key=f"{category}_{task}")

# Scheduler Suggestion
st.header("🗓️ AI Schedule Suggestion")
if st.button("Generate Today's Suggested Schedule"):
    st.write("Fetching busy slots and generating schedule...")
    # This will be fully integrated in Phase 8
    st.success("The AI suggests the following additions to your calendar:")
    st.table([
        {"Time": "09:00 - 10:00", "Task": "Finish Chapter 3 proofreading", "Category": "Ref.team Book editing"},
        {"Time": "10:30 - 11:00", "Task": "30 mins morning exercise", "Category": "Personal"},
        {"Time": "14:00 - 15:00", "Task": "Review wireframes for homepage", "Category": "winedragons"}
    ])

# Footer
st.divider()
st.caption("AI Agent Assistant - Built with Streamlit, Gemini, and Google Calendar.")
