import streamlit as st
import requests
import json
import time
from typing import Dict, Any, Iterator
import pandas as pd
import io

class AzureOpenAIChat:
    def __init__(self):
        self.API_ENDPOINT = st.secrets.get("AZURE_OPENAI_API_ENDPOINT", "")
        self.API_KEY = st.secrets.get("AZURE_OPENAI_API_KEY", "")

        if not self.API_KEY:
            raise ValueError("Azure OpenAI API Key is missing.")

    def generate_response_stream(
        self,
        query: str,
        #max_tokens: int = 1000,
        temperature: float = 0.7,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
        processedExcel = ''
    ) -> Iterator[str]:
        """Generate streaming response from Azure OpenAI"""
        headers = {
            "Content-Type": "application/json",
            "api-key": self.API_KEY,
        }
        systemPrompt = "Attached is a sheet from a project management software used in the construction industry. WBS1, WBS2, WBS3, WBS4, WBS5, WBS6, WBS7, WBS8, WBS9 represent the hierarchy followed by the software, a row is deemed as an activity when the row has non empty Status value and a non empty Activity Id. Based on the queries, you are required to respond with the activity name." 
        systemPrompt += "Whenever a query is made, you must always provide the activity name in your response. StartDate: The date when the activity started or is scheduled to start."
        systemPrompt += "EndDate: The date when the activity ended or is expected to end."
        systemPrompt += "Progress: The percentage of overall progress for the activity."
        systemPrompt += "Duration: The remaining number of days required to complete the activity."
        systemPrompt += "Activity Id: Represents the code of activity."
        systemPrompt += "Status: Current state of the activity."
        data = {
            "messages": [
                {"role": "system", "content": systemPrompt},  # Excel data as system context
                {"role": "user", "content": query}  # User query
                ],
            "temperature": temperature,
            "top_p": top_p,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "stream": True  # Enable streaming
        }
        # st.write("Messages being sent to API:")
        # for msg in data["messages"]:
        #     st.write(f"Role: {msg['role']}")
        #     st.write("Content:")
        #     st.text(msg['content'][:1000] + "..." if len(msg['content']) > 1000 else msg['content'])
        #     st.write("---")
        try:
            response = requests.post(
                self.API_ENDPOINT,
                headers=headers,
                json=data,
                stream=True
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if line.strip() == b'data: [DONE]':
                    break
                if line.startswith(b'data: '):
                    json_str = line[6:].decode('utf-8')
                    try:
                        json_data = json.loads(json_str)
                        if 'choices' in json_data and len(json_data['choices']) > 0:
                            delta = json_data['choices'][0].get('delta', {})
                            if 'content' in delta:
                                yield delta['content']
                    except (json.JSONDecodeError, IndexError, KeyError):
                        continue
        except requests.exceptions.RequestException as req_err:
            raise RuntimeError(f"Request error: {req_err}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error: {str(e)}")


def process_excel_file(file):
    try:
        df = pd.read_excel(file)
        # Convert DataFrame to string and store it
        processedExcel = df.to_string()
        st.session_state.uploaded_data = df
        
        with st.chat_message("assistant"):
            st.success(f"Excel file processed successfully! Found {len(df)} rows and {len(df.columns)} columns.")
            st.dataframe(df.head(), use_container_width=True)
        
        # Add system message to chat history about the file upload
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"Excel file processed successfully!\nColumns: {', '.join(df.columns)}\nNumber of rows: {len(df)}"
        })
        
        return processedExcel  # Return the string representation
        
    except Exception as e:
        st.error(f"Error reading the file: {str(e)}")
        return ""


def main():
    st.set_page_config(page_title="OpenAI Playground", page_icon="💬")
    st.title("OpenAI Playground")

    # Initialize session state variables
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "uploaded_data" not in st.session_state:
        st.session_state.uploaded_data = None

    # Add main interface file upload
    col1, col2 = st.columns([3, 1])
    
    with col1:
        main_file_upload = st.file_uploader("Upload Excel File (Main)", type=['xlsx', 'xls'])
    with col2:
        if main_file_upload:
            if st.button("Process File"):
                process_excel_file(main_file_upload)

    # Add after the file upload section
    if st.checkbox("Show Excel Data Debug"):
        if 'processed_excel' in st.session_state:
            st.text("Excel String Preview (first 50000 chars):")
            st.text(st.session_state.processed_excel[:50000] + "..." if len(st.session_state.processed_excel) > 50000 else st.session_state.processed_excel)

    # Display data preview if available
    if st.session_state.uploaded_data is not None:
        st.subheader("Current Data Preview")
        st.dataframe(st.session_state.uploaded_data.head())

    # Add file uploader in the sidebar
    with st.sidebar:
        st.header("Data Import")
        uploaded_file = st.file_uploader("Upload Excel File", type=['xlsx', 'xls'])
        
        if uploaded_file is not None:
            processedExcel = process_excel_file(uploaded_file)  # Capture the return value
            st.session_state.processed_excel = processedExcel  # Store in session state
            
            if st.session_state.uploaded_data is not None:
                # Display basic information about the dataset
                st.subheader("Dataset Info")
                st.write(f"Number of rows: {len(st.session_state.uploaded_data)}")
                st.write(f"Number of columns: {len(st.session_state.uploaded_data.columns)}")
                st.write("Columns:", ", ".join(st.session_state.uploaded_data.columns))

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Enter your message"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate and display streaming response
        chat_client = AzureOpenAIChat()

        # Create a placeholder for the streaming response
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            full_response = ""

            try:
                # If there's uploaded data, include it in the context
                context = ""
                if st.session_state.uploaded_data is not None:
                    df = st.session_state.uploaded_data
                    context = f"\nContext from uploaded Excel file:\n"
                    context += f"- File contains {len(df)} rows and {len(df.columns)} columns\n"
                    context += f"- Columns: {', '.join(df.columns)}\n"
                    context += f"- First few rows:\n{df.head().to_string()}\n\n"
                
                # Combine context with user prompt
                full_prompt = context + prompt if context else prompt

                for text_chunk in chat_client.generate_response_stream(
                    full_prompt,
                    #max_tokens=1000,
                ):
                    full_response += text_chunk
                    # Update response in real-time
                    response_placeholder.markdown(full_response + "▌")
                print(full_prompt)
                
                # Final update without cursor
                response_placeholder.markdown(full_response)

                # Add assistant's message to chat history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": full_response,
                })
            except RuntimeError as err:
                st.error(f"Error generating response: {err}")
                response_placeholder.markdown("Sorry, I couldn't generate a response.")


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