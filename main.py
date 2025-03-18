# main.py
import streamlit as st
from streamlit_helpers import (
    initialize_session_state,
    display_sidebar,
    display_main_content
)
from azure_api import AzureOpenAIChat
from database import get_database_connection, DatabaseManager
import os

def setup_database():
    """Setup database connection and create tables if needed."""
    # Check if we're using a custom connection string
    connection_string = st.session_state.get('connection_string', None)
    
    # Create DB manager with connection string if available
    db_manager = DatabaseManager(connection_string)
    
    # Try to connect
    if db_manager.connect():
        st.session_state.db_manager = db_manager
        return True
    else:
        return False

def main():
    """Main function to run the Streamlit app."""
    st.set_page_config(
        page_title="Construction Schedule Assistant",
        page_icon="🏗️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Initialize session state
    initialize_session_state()

    # Add a banner at the top for database status
    if st.session_state.data_source == "database":
        if "db_manager" in st.session_state and st.session_state.db_manager:
            st.success("✅ Connected to database")
        else:
            st.warning("⚠️ Database not connected. Please connect in the sidebar.")
    
    # Display app title and description
    st.title("🏗️ Construction Schedule Assistant")
    st.write("""
    This app helps you analyze and query your construction schedule data using natural language.
    Upload an Excel file or connect to a database to get started.
    """)

    # Display sidebar with file upload or database connection
    display_sidebar()

    # Display main content area
    display_main_content()

    # Process user input in chat
    if prompt := st.chat_input("Ask a question about your schedule data..."):
        # Check if we have data loaded
        if 'uploaded_data' in st.session_state and st.session_state.uploaded_data is not None:
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Generate streaming response
            chat_client = AzureOpenAIChat()
            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                full_response = ""
                try:
                    # Show thinking indicator for database queries
                    if st.session_state.data_source == "database":
                        st.info("Querying database and analyzing data...")
                    
                    # Process streaming response
                    for text_chunk in chat_client.generate_response_stream(prompt):
                        full_response += text_chunk
                        response_placeholder.markdown(full_response + "▌")
                    
                    # Final response without cursor
                    response_placeholder.markdown(full_response)
                    
                    # Add to chat history
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    
                    # Provide debug info if needed
                    if st.session_state.data_source == "database" and st.checkbox("Show query details", key="show_debug"):
                        if "db_manager" in st.session_state:
                            st.text("Database queries executed for this response:")
                            # This would be enhanced with actual query logging in a production system
                            st.code("SELECT * FROM activities WHERE \"Activity Id\" LIKE '%...'")
                except RuntimeError as err:
                    st.error(f"Error generating response: {err}")
                    response_placeholder.markdown("Sorry, I couldn't generate a response. Please try again.")
                except Exception as e:
                    st.error(f"Unhandled error: {str(e)}")
        else:
            st.warning("No data uploaded. Please upload an Excel file or connect to a database to ask questions about your schedule.")
            
    # Add agentic function explanation if database is connected
    if st.session_state.data_source == "database" and "db_manager" in st.session_state:
        with st.expander("💡 How does the AI query your data?"):
            st.write("""
            This app uses an agentic approach to analyze your queries:
            
            1. When you ask a question, the AI first analyzes what type of information you need
            2. It then calls specific database functions to retrieve relevant data
            3. The retrieved data is used to provide an accurate, data-driven response
            
            Available functions include:
            - Getting activity details by ID
            - Retrieving activities by status
            - Generating timeline information
            - Calculating progress summaries
            
            This approach combines the power of natural language processing with precise database queries for optimal results.
            """)


if __name__ == "__main__":
    main()
    
    # Footer with text and link
    st.markdown(
        """
        <style>
        .footer {
            position: fixed;
            bottom: 10px;
            right: 10px;
            font-size: 14px;
            color: #666;
            text-align: right;
            z-index: 1000;
        }
        .footer a {
            color: #007BFF;
            text-decoration: none;
        }
        .footer a:hover {
            text-decoration: underline;
        }
        </style>
        <div class="footer">
            By: <a href="https://www.linkedin.com/in/vinit-gujarathi/" target="_blank">Vinit Gujarathi</a>
        </div>
        """,
        unsafe_allow_html=True,
    )