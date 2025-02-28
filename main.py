# main.py
import streamlit as st
from streamlit_helpers import (
    initialize_session_state,
    display_sidebar,
    display_main_content
)
from azure_api import AzureOpenAIChat

def main():
    """Main function to run the Streamlit app."""
    st.set_page_config(
        page_title="Azure OpenAI Chat",
        page_icon="💬",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Initialize session state
    initialize_session_state()

    # Display sidebar with file upload
    display_sidebar()

    # Display main content area
    display_main_content()

    # Process user input in chat
    if prompt := st.chat_input("Ask a question about your data..."):
        if 'uploaded_data' in st.session_state and st.session_state.uploaded_data is not None:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Generate streaming response
            chat_client = AzureOpenAIChat()
            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                full_response = ""
                try:
                    for text_chunk in chat_client.generate_response_stream(prompt):
                        full_response += text_chunk
                        response_placeholder.markdown(full_response + "▌")
                    response_placeholder.markdown(full_response)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    st.write("Data sent to Azure and response received.")
                except RuntimeError as err:
                    st.error(f"Error generating response: {err}")
                    response_placeholder.markdown("Sorry, I couldn't generate a response. Please try again.")
                except Exception as e:
                    st.error(f"Unhandled error: {str(e)}")
        else:
            st.warning("No data uploaded. Please upload an Excel file to ask questions about it.")

if __name__ == "__main__":
    main()
