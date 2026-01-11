import streamlit as st
import pandas as pd
from senti_scraper import SentiScraper
import os

st.set_page_config(page_title="SentiOne Scraper", layout="wide")
st.title("SentiOne Batch Scraper")

if 'queue' not in st.session_state:
    st.session_state.queue = []
if 'logs' not in st.session_state:
    st.session_state.logs = []

with st.sidebar:
    st.header("Credentials")
    # Try to load from secrets, otherwise default to empty
    default_email = st.secrets.get("EMAIL", "")
    default_password = st.secrets.get("PASSWORD", "")

    email = st.text_input("Email", value=default_email)
    password = st.text_input("Password", value=default_password, type="password")
    
    if st.button("Clear Queue"):
        st.session_state.queue = []
        st.session_state.logs = []
        st.rerun()

def clear_inputs():
    st.session_state["t_id"] = ""
    st.session_state["t_title"] = ""

st.subheader("Add Topic to Queue")
col1, col2, col3, col4 = st.columns(4)

with col1:
    topic_id = st.text_input("Topic ID", placeholder="e.g., 1171861", key="t_id")
with col2:
    topic_title = st.text_input("Topic Title", placeholder="Client_Project", key="t_title")
with col3:
    start_date = st.date_input("Start Date")
with col4:
    end_date = st.date_input("End Date")

if st.button("Add to Queue", on_click=clear_inputs):
    if topic_id and topic_title:
        start_str = start_date.strftime("%d.%m.%Y")
        end_str = end_date.strftime("%d.%m.%Y")
        
        st.session_state.queue.append({
            "Topic ID": topic_id,
            "Title": topic_title,
            "Start Date": start_str,
            "End Date": end_str
        })
        st.success(f"Added {topic_title} to queue.")
    else:
        st.error("Please provide both Topic ID and Title.")

st.divider()
st.subheader("Processing Queue")

if st.session_state.queue:
    df = pd.DataFrame(st.session_state.queue)
    st.dataframe(df, use_container_width=True)
    
    if st.button("Start Batch Processing", type="primary"):
        st.info("Starting browser... Please wait.")
        
        scraper = SentiScraper()
        
        try:
            scraper.setup_driver()
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

if st.session_state.logs:
    st.divider()
    st.subheader("Activity Log")
    for log in st.session_state.logs:
        st.text(log)

st.divider()
st.subheader("Data Viewer")
st.write("Browse processed files in the workspace (showing latest created files):")

processed_files = []
root_dir = os.path.dirname(os.path.abspath(__file__))
for dirpath, dirnames, filenames in os.walk(root_dir):
    if any(p.startswith('.') for p in dirpath.split(os.sep)):
        continue
    for f in filenames:
        if f.endswith(".csv"): 
            full_path = os.path.join(dirpath, f)
            processed_files.append(full_path)

processed_files.sort(key=os.path.getmtime, reverse=True)

if processed_files:
    file_options = {os.path.basename(f) + " (" + os.path.dirname(f).split(os.sep)[-1] + ")": f for f in processed_files}
    selected_name = st.selectbox("Select a file to view", list(file_options.keys()))
    
    if selected_name:
        selected_file = file_options[selected_name]
        
        with open(selected_file, "rb") as f:
            file_data = f.read()
            
        col_actions1, col_actions2 = st.columns([1, 4])
        with col_actions1:
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
            df_view = pd.read_csv(selected_file, on_bad_lines='skip', engine='python')
            
            st.write(f"**Preview of {selected_name}**")
            st.dataframe(df_view.head(50))
            st.write(f"Total Rows: {len(df_view)}")
            
        except Exception as e:
            st.error(f"Error reading file: {e}")
            st.warning("Ensure the file structure is correct. SentiOne CSVs might be semicolon separated or contain metadata headers.")
else:
    st.info("No CSV files found.")
