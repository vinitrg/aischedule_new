import streamlit as st
import requests
from typing import Tuple

class AzureOpenAIService:
    """Simple service to test connection to Azure OpenAI API"""
    
    def __init__(self):
        """Initialize Azure OpenAI service using Streamlit secrets"""
        # Get configuration from Streamlit secrets
        self.api_key = st.secrets.get("AZURE_OPENAI_API_KEY", "")
        self.api_endpoint = st.secrets.get("AZURE_OPENAI_API_ENDPOINT", "")
    
    def test_connection(self) -> Tuple[bool, str]:
        """Test the connection to Azure OpenAI API"""
        try:
            # Set up the headers for the API request
            headers = {
                "Content-Type": "application/json",
                "api-key": self.api_key,
            }
            
            # Simple test request
            data = {
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Hello, are you working?"}
                ],
                "max_tokens": 50,
                "temperature": 0.7
            }
            
            # Make the API request
            response = requests.post(
                self.api_endpoint,
                headers=headers,
                json=data,
                timeout=10
            )
            
            # Check if the request was successful
            response.raise_for_status()
            
            return True, "Successfully connected to Azure OpenAI API."
            
        except Exception as e:
            return False, f"Failed to connect to Azure OpenAI API: {str(e)}"

def get_openai_service() -> AzureOpenAIService:
    """Get or create the Azure OpenAI service singleton"""
    if "openai_service" not in st.session_state:
        st.session_state.openai_service = AzureOpenAIService()
    
    return st.session_state.openai_service