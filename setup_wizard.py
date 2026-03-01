import streamlit as st
import os
import shutil

# --- Page Configuration ---
st.set_page_config(
    page_title="AI Agent Assistant | Setup Wizard",
    page_icon="🪄",
    layout="centered"
)

# --- Helper Functions ---
def save_config(config_data):
    template_path = "config.template"
    config_path = ".config"
    
    if not os.path.exists(template_path):
        st.error("Missing config.template! Please ensure you are in the project root.")
        return False
    
    with open(template_path, "r") as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        updated = False
        for key, val in config_data.items():
            if line.startswith(f"{key}="):
                new_lines.append(f"{key}={val}
")
                updated = True
                break
        if not updated:
            new_lines.append(line)
            
    with open(config_path, "w") as f:
        f.writelines(new_lines)
    return True

# --- UI Layout ---
st.title("🪄 AI Assistant Setup Wizard")
st.markdown("""
Welcome! This wizard will help you connect your local notes and calendar to the AI Assistant. 
No technical knowledge is required.
""")

# Progress tracking
if 'step' not in st.session_state:
    st.session_state.step = 1

# --- Step 1: API Keys ---
if st.session_state.step == 1:
    st.header("Step 1: Connect to Google Gemini")
    st.markdown("""
    The "brain" of this assistant is Google's Gemini AI. 
    1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey).
    2. Click **Create API Key**.
    3. Copy and paste it below.
    """)
    
    gemini_key = st.text_input("Gemini API Key", type="password", placeholder="Paste your key here...")
    
    if st.button("Next ➡️"):
        if gemini_key:
            st.session_state.gemini_key = gemini_key
            st.session_state.step = 2
            st.rerun()
        else:
            st.warning("Please enter your API key to continue.")

# --- Step 2: Workspace Paths ---
elif st.session_state.step == 2:
    st.header("Step 2: Locate Your Notes")
    st.markdown("""
    Tell the assistant where your Markdown files are stored. 
    *Tip: You can copy the path by right-clicking a folder in Finder (Mac) or Files (Linux) and holding 'Option' or 'Alt'.*
    """)
    
    obsidian_path = st.text_input("Obsidian Vault Path", value=os.path.expanduser("~/Documents/Obsidian"))
    logseq_path = st.text_input("LogSeq Graph Path (Optional)", value=os.path.expanduser("~/Documents/LogSeq"))
    books_path = st.text_input("Books Folder Path (Optional)", value=os.path.expanduser("~/Documents/Books"))
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Back"):
            st.session_state.step = 1
            st.rerun()
    with col2:
        if st.button("Next ➡️"):
            st.session_state.obsidian_path = obsidian_path
            st.session_state.logseq_path = logseq_path
            st.session_state.books_path = books_path
            st.session_state.step = 3
            st.rerun()

# --- Step 3: Productivity Profile ---
elif st.session_state.step == 3:
    st.header("Step 3: Your Productivity Style")
    st.markdown("Help the AI understand when you are most productive.")
    
    chronotype = st.selectbox("When do you focus best?", 
                             ["morning_owl", "night_owl", "balanced"], 
                             format_func=lambda x: x.replace("_", " ").title())
    
    dw_start = st.time_input("Deep Work Starts at", value=None)
    dw_end = st.time_input("Deep Work Ends at", value=None)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Back"):
            st.session_state.step = 2
            st.rerun()
    with col2:
        if st.button("Finish ✨"):
            # Prepare final config
            config_data = {
                "GEMINI_API_KEY": st.session_state.gemini_key,
                "WORKSPACE_DIR": st.session_state.obsidian_path,
                "LOGSEQ_DIR": st.session_state.logseq_path,
                "BOOKS_DIR": st.session_state.books_path,
                "CHRONOTYPE": chronotype,
                "DEEP_WORK_START": dw_start.strftime("%H:%M") if dw_start else "09:00",
                "DEEP_WORK_END": dw_end.strftime("%H:%M") if dw_end else "12:00"
            }
            
            if save_config(config_data):
                st.session_state.step = 4
                st.rerun()

# --- Step 4: Success ---
elif st.session_state.step == 4:
    st.balloons()
    st.success("Configuration Saved Successfully!")
    st.markdown("""
    ### What's Next?
    1. **Calendar Access:** The first time you run the app, your browser will open to ask for Google Calendar permission.
    2. **Run the Dashboard:** Close this window and run `make run-ui` in your terminal.
    3. **Background Sync:** If you enabled 'Cron' in the script, your notes will sync automatically every hour.
    
    You can now close this browser tab.
    """)
    
    if st.button("Launch Dashboard 🚀"):
        st.info("Please run 'make run-ui' in your terminal to start the main application.")
