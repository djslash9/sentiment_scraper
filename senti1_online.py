import streamlit as st
import pandas as pd
from senti_scraper import SentiScraper
import os

st.set_page_config(page_title="SentiOne Scraper", layout="wide")
st.title("SentiOne Batch Scraper")

# State Management
if 'queue' not in st.session_state:
    st.session_state.queue = []
if 'logs' not in st.session_state:
    st.session_state.logs = []

# Credentials (Loaded from Secrets)
email = st.secrets.get("EMAIL", "")
password = st.secrets.get("PASSWORD", "")

if not email or not password:
    st.error("Credentials not found in secrets. Please configure secrets.toml or Streamlit Cloud secrets.")

st.divider()

# Callback to Add and Clear
def add_topic():
    # Access values from state
    t_id = st.session_state.get("t_id", "")
    t_title = st.session_state.get("t_title", "")
    s_date = st.session_state.get("s_date")
    e_date = st.session_state.get("e_date")
    
    if t_id and t_title:
        # Format dates
        start_str = s_date.strftime("%d.%m.%Y")
        end_str = e_date.strftime("%d.%m.%Y")
        
        st.session_state.queue.append({
            "Topic ID": t_id,
            "Title": t_title,
            "Start Date": start_str,
            "End Date": end_str
        })
        st.toast(f"Added {t_title} to queue.")
        
        # Clear inputs
        st.session_state["t_id"] = ""
        st.session_state["t_title"] = ""
        # We leave dates as is for convenience
    else:
        st.error("Please provide both Topic ID and Title.")

# Main Input Area
st.subheader("Add Topic to Queue")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.text_input("Topic ID", placeholder="e.g., 1171861", key="t_id")
with col2:
    st.text_input("Topic Title", placeholder="Client_Project", key="t_title")
with col3:
    st.date_input("Start Date", key="s_date")
with col4:
    st.date_input("End Date", key="e_date")

st.button("Add to Queue", on_click=add_topic)

# Queue Display
st.divider()
st.subheader("Processing Queue")

if st.session_state.queue:
    df = pd.DataFrame(st.session_state.queue)
    st.dataframe(df, use_container_width=True)
    
    # Process Button
    if st.button("Start Batch Processing", type="primary"):
        st.info("Starting browser... Please wait.")
        
        scraper = SentiScraper()
        
        try:
            scraper.setup_driver()
            # Use credentials from top inputs
            login_success = scraper.login(email, password)
            
            if login_success:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                total_items = len(st.session_state.queue)
                
                for i, item in enumerate(st.session_state.queue):
                    current_title = item['Title']
                    status_text.text(f"Processing {i+1}/{total_items}: {current_title}...")
                    
                    success = scraper.scrape_topic(item['Topic ID'], item['Start Date'], item['End Date'])
                    
                    if success:
                        new_path = scraper.process_latest_file(current_title)
                        msg = f"✅ {current_title}: Successfully saved to {new_path}"
                        st.session_state.logs.append(msg)
                        st.toast(msg)
                    else:
                        msg = f"❌ {current_title}: Failed to download."
                        st.session_state.logs.append(msg)
                        st.error(msg)
                    
                    progress_bar.progress((i + 1) / total_items)
                
                status_text.text("Batch processing completed!")
                st.success("All tasks finished.")
            else:
                st.error("Login failed. Please check credentials.")
                
        except Exception as e:
            st.error(f"Critical error occurred: {e}")
        finally:
            if scraper:
                scraper.close()
            st.info("Browser closed.")
else:
    st.info("Queue is empty. Add topics above to get started.")

# Logs Section
if st.session_state.logs:
    st.divider()
    st.subheader("Activity Log")
    for log in st.session_state.logs:
        st.text(log)

# Data Viewer
st.divider()
st.subheader("Data Viewer")
st.write("Browse processed files in the workspace (showing latest created files):")

processed_files = []
root_dir = os.path.dirname(os.path.abspath(__file__)) # Current script dir
for dirpath, dirnames, filenames in os.walk(root_dir):
    # Skip hidden git/env dirs
    if any(p.startswith('.') for p in dirpath.split(os.sep)):
        continue
    for f in filenames:
        if f.endswith(".csv"): 
            full_path = os.path.join(dirpath, f)
            processed_files.append(full_path)

# Sort by modification time to show new ones first
processed_files.sort(key=os.path.getmtime, reverse=True)

if processed_files:
    # Use basename for display
    file_options = {os.path.basename(f) + " (" + os.path.dirname(f).split(os.sep)[-1] + ")": f for f in processed_files}
    selected_name = st.selectbox("Select a file to view", list(file_options.keys()))
    
    if selected_name:
        selected_file = file_options[selected_name]
        
        # Prepare file for download
        with open(selected_file, "rb") as f:
            file_data = f.read()
            
        col_actions1, col_actions2 = st.columns([1, 4])
        with col_actions1:
            # Callback to delete file after download
            def delete_current_file():
                try:
                    os.remove(selected_file)
                    st.toast(f"Deleted {selected_name}")
                except Exception as e:
                    st.error(f"Failed to delete: {e}")
            
            st.download_button(
                label="Download CSV",
                data=file_data,
                file_name=os.path.basename(selected_file),
                mime="text/csv",
                on_click=delete_current_file,
                type="primary"
            )

        try:
            # Robust CSV reading
            df_view = pd.read_csv(selected_file, on_bad_lines='skip', engine='python')
            
            st.write(f"**Preview of {selected_name}**")
            st.dataframe(df_view.head(50))
            st.write(f"Total Rows: {len(df_view)}")
            
        except Exception as e:
            st.error(f"Error reading file: {e}")
            st.warning("Ensure the file structure is correct. SentiOne CSVs might be semicolon separated or contain metadata headers.")
else:
    st.info("No CSV files found.")
