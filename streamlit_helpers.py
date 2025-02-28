# streamlit_helpers.py
import streamlit as st
import pandas as pd
from typing import Optional
import time

def initialize_session_state():
    """Initialize all session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "uploaded_data" not in st.session_state:
        st.session_state.uploaded_data = None
    if "processed_excel" not in st.session_state:
        st.session_state.processed_excel = ""
    if "file_status" not in st.session_state:
        st.session_state.file_status = None

def process_excel_file(file) -> Optional[pd.DataFrame]:
    """
    Process uploaded Excel file with proper error handling and progress indication.
    Returns DataFrame if successful, None otherwise.
    """
    if file is None:
        return None

    try:
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Update status
        status_text.text("Reading Excel file...")
        progress_bar.progress(25)
        time.sleep(0.5)  # Add slight delay for UX

        # Read the Excel file
        df = pd.read_excel(file)
        progress_bar.progress(50)
        status_text.text("Processing data...")
        time.sleep(0.5)

        # Basic data validation
        if df.empty:
            raise ValueError("The uploaded Excel file is empty.")

        # Store the entire DataFrame
        st.session_state.uploaded_data = df
        st.session_state.processed_excel = df.to_string()
        progress_bar.progress(75)
        status_text.text("Finalizing...")
        time.sleep(0.5)

        # Complete the progress bar
        progress_bar.progress(100)
        status_text.text("Processing complete!")
        time.sleep(0.5)

        # Clear the progress indicators
        progress_bar.empty()
        status_text.empty()

        st.success(f"File processed successfully! Found {len(df)} rows and {len(df.columns)} columns.")
        return df

    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        st.session_state.file_status = "error"
        return None

def display_sidebar():
    """Display sidebar with file upload."""
    with st.sidebar:
        st.title("File Upload")
        
        uploaded_file = st.file_uploader(
            "Upload Excel File",
            type=['xlsx', 'xls'],
            help="Upload your Excel file containing the project data"
        )

        if uploaded_file:
            if st.button("Process File", type="primary"):
                st.session_state.uploaded_data = process_excel_file(uploaded_file)

        # Clear Chat Button
        if st.button("Clear Chat History", type="secondary"):
            st.session_state.messages = []
            st.rerun()

def display_main_content():
    """Display the main content area with data preview and chat."""
    # Data Preview Section
    if st.session_state.uploaded_data is not None:
        st.header("Data Preview")
        
        # Add tabs for different views of the data
        tab1, tab2, tab3 = st.tabs(["Preview", "Statistics", "Column Info"])
        
        with tab1:
            st.dataframe(
                st.session_state.uploaded_data,
                use_container_width=True,
                height=300
            )
            
        with tab2:
            st.write("Basic Statistics")
            st.dataframe(
                st.session_state.uploaded_data.describe(),
                use_container_width=True
            )
            
        with tab3:
            col_info = pd.DataFrame({
                'Column': st.session_state.uploaded_data.columns,
                'Type': st.session_state.uploaded_data.dtypes,
                'Non-Null Count': st.session_state.uploaded_data.count(),
                'Null Count': st.session_state.uploaded_data.isna().sum()
            })
            st.dataframe(col_info, use_container_width=True)

    # Chat History Section
    st.header("Chat")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
