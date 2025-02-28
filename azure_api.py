# azure_api.py
import streamlit as st
import requests
import json
from typing import Iterator
import pandas as pd

class AzureOpenAIChat:
    def __init__(self):
        self.API_ENDPOINT = st.secrets.get("AZURE_OPENAI_API_ENDPOINT", "")
        self.API_KEY = st.secrets.get("AZURE_OPENAI_API_KEY", "")
        
        if not self.API_KEY or not self.API_ENDPOINT:
            raise ValueError("Azure OpenAI API credentials are missing.")

    def generate_response_stream(self, query: str) -> Iterator[str]:
        headers = {
            "Content-Type": "application/json",
            "api-key": self.API_KEY,
        }

        # Create comprehensive system prompt with Excel data
        system_prompt = self._create_system_prompt()
        
        # Combine the user's query with Excel data context
        enhanced_query = self._enhance_query_with_context(query)

        data = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": enhanced_query}
            ],
            "temperature": 0.7,
            "stream": True
        }

        try:
            response = requests.post(
                self.API_ENDPOINT,
                headers=headers,
                json=data,
                stream=True,
                timeout=30
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if not line or line.strip() == b'data: [DONE]':
                    continue
                if line.startswith(b'data: '):
                    try:
                        json_str = line[6:].decode('utf-8')
                        json_data = json.loads(json_str)
                        if 'choices' in json_data and json_data['choices']:
                            delta = json_data['choices'][0].get('delta', {})
                            if 'content' in delta:
                                yield delta['content']
                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            raise RuntimeError(f"API error: {str(e)}")

    def _create_system_prompt(self) -> str:
        """Create a detailed system prompt including Excel data context."""
        if 'uploaded_data' not in st.session_state:
            return "You are a project management assistant. No data is currently loaded."

        df = st.session_state.uploaded_data
        
        # Get all unique activities
        activities = df[['Activity Id', 'Status', 'Progress']].to_dict('records')
        activities_str = "\n".join([
            f"Activity {a['Activity Id']}: Status={a['Status']}, Progress={a['Progress']}%"
            for a in activities
        ])

        prompt = f"""You are analyzing a construction project management sheet with the following data:

Excel Data Context:
{activities_str}

Guidelines:
1. Always refer to specific Activity IDs in your responses
2. Each activity has Status, Progress, and Duration
3. WBS1 to WBS9 represent the hierarchy
4. Activities with non-empty Status and Activity Id are valid tasks
5. Include exact values from the data in your responses

Please provide specific, data-driven responses based on this Excel data."""

        return prompt

    def _enhance_query_with_context(self, query: str) -> str:
        """Enhance the user query with relevant data context."""
        if 'uploaded_data' not in st.session_state:
            return query

        df = st.session_state.uploaded_data
        relevant_context = ""

        # Add activity IDs context if query mentions specific activities
        if any(id_ref in query.lower() for id_ref in ['activity', 'task', 'id', 'a10']):
            activity_ids = df['Activity Id'].unique()
            relevant_context += f"\nAvailable Activity IDs: {', '.join(activity_ids)}"

        # Add status context if query mentions status
        if 'status' in query.lower():
            status_summary = df['Status'].value_counts().to_dict()
            relevant_context += f"\nStatus Summary: {status_summary}"

        # Add progress context if query mentions progress
        if 'progress' in query.lower():
            progress_avg = df['Progress'].mean()
            relevant_context += f"\nAverage Progress: {progress_avg:.1f}%"

        # Combine original query with context
        enhanced_query = f"{query}\n\nRelevant Data Context:{relevant_context}"
        return enhanced_query