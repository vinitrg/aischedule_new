# azure_api.py
import streamlit as st
import requests
import json
from typing import Iterator, Dict, Any, List, Optional
import pandas as pd
from database import get_database_connection

class AzureOpenAIChat:
    def __init__(self):
        self.API_ENDPOINT = st.secrets.get("AZURE_OPENAI_API_ENDPOINT", "")
        self.API_KEY = st.secrets.get("AZURE_OPENAI_API_KEY", "")
        
        if not self.API_KEY or not self.API_ENDPOINT:
            raise ValueError("Azure OpenAI API credentials are missing.")
        
        # Get database connection if using database
        self.db_manager = get_database_connection() if st.session_state.data_source == "database" else None

    def generate_response_stream(self, query: str) -> Iterator[str]:
        headers = {
            "Content-Type": "application/json",
            "api-key": self.API_KEY,
        }

        # Create comprehensive system prompt with data context
        system_prompt = self._create_system_prompt()
        
        # Use agent approach to decide which functions to call
        function_calls, function_responses = self._analyze_query_for_functions(query)
        
        # Combine the user's query with context from function calls
        enhanced_query = self._enhance_query_with_context(query, function_responses)

        # Add function call results to the messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": enhanced_query}
        ]
        st.write(enhanced_query)
        # Add function call results if any
        if function_responses:
            function_context = "I've analyzed the data and found the following information:\n\n"
            for func_name, result in function_responses.items():
                function_context += f"From {func_name}:\n{result}\n\n"
            messages.append({"role": "system", "content": function_context})

        data = {
            "messages": messages,
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
        """Create a detailed system prompt including data context."""
        if st.session_state.data_source == "database" and self.db_manager:
            # Get summary data from database
            try:
                progress_summary = self.db_manager.get_progress_summary()
                progress_summary_str = progress_summary.to_string() if not progress_summary.empty else "No data available"
                
                return f"""You are a construction project management AI assistant analyzing a database of project activities.

Database Context:
- The database contains construction schedule data with activities, their statuses, and progress.
- Each activity has an Activity ID, Status, Progress, StartDate, EndDate, and Duration.
- The project is organized in a WBS (Work Breakdown Structure) hierarchy (WBS1-WBS9) and WBS does not have a Status assigned

IMPORTANT HIERARCHY UNDERSTANDING:
- Activities without a Status assigned are WBS (Work Breakdown Structure) parent items
- WBS parents group and organize actual activities
- Only items with a Status are actual activities that have work associated with them
- Parent WBS items contain child activities and their progress is derived from their children

Project Summary Statistics:
{progress_summary_str}

Guidelines:
1. Always refer to specific Activity IDs in your responses when applicable
2. Distinguish between WBS parent items (no Status) and actual activities (with Status)
3. Use the data from the database to provide accurate, data-driven responses
4. If the user asks about a specific activity or status, I will query the database for that information
5. If you need more specific data than what's in the context, mention that you need to query the database

I can perform database queries to get more detailed information as needed."""
            except Exception as e:
                st.error(f"Error getting database summary: {str(e)}")
                return "You are a construction project management AI assistant. The database connection is currently having issues."
    

    def _analyze_query_for_functions(self, query: str) -> tuple[List[str], Dict[str, Any]]:
        """
        Analyze the query to determine which database functions to call.
        Returns list of function names and their results.
        """
        function_calls = []
        function_results = {}
        
        # Skip if not using database or no DB manager
        if st.session_state.data_source != "database" or not self.db_manager:
            return function_calls, function_results
        
        # Check for activity ID patterns (A123, Task-456, etc.)
        import re
        activity_id_patterns = re.findall(r'([A-Z]-\d+|\b[A-Z]\d+\b|Task-\d+)', query, re.IGNORECASE)
        
        for activity_id in activity_id_patterns:
            function_calls.append("get_activity_by_id")
            try:
                result = self.db_manager.get_activity_by_id(activity_id)
                if not result.empty:
                    function_results["get_activity_by_id"] = f"Activity {activity_id}:\n{result.to_string()}"
            except Exception as e:
                st.warning(f"Failed to get activity {activity_id}: {str(e)}")
        
        # Check for status queries
        status_keywords = {
            "completed": "Completed",
            "in progress": "In Progress",
            "not started": "Not Started",
            "delayed": "Delayed",
            "on hold": "On Hold"
        }
        
        for keyword, status in status_keywords.items():
            if keyword.lower() in query.lower():
                function_calls.append("get_activities_by_status")
                try:
                    result = self.db_manager.get_activities_by_status(status)
                    if not result.empty:
                        count = len(result)
                        function_results["get_activities_by_status"] = f"{count} activities with status '{status}'"
                        # Add sample of activities
                        if count > 0:
                            sample = result.head(3)
                            function_results["get_activities_by_status"] += f"\nSample activities: {sample['Activity Id'].tolist()}"
                except Exception as e:
                    st.warning(f"Failed to get activities with status {status}: {str(e)}")
        
        # Check for timeline/schedule queries
        timeline_keywords = ["timeline", "schedule", "gantt", "when", "start date", "end date", "duration"]
        if any(keyword in query.lower() for keyword in timeline_keywords):
            function_calls.append("get_schedule_timeline")
            try:
                result = self.db_manager.get_schedule_timeline()
                if not result.empty:
                    earliest = result["StartDate"].min() if "StartDate" in result.columns else "Unknown"
                    latest = result["EndDate"].max() if "EndDate" in result.columns else "Unknown"
                    function_results["get_schedule_timeline"] = f"Project timeline: {earliest} to {latest}"
                    # Add activities on critical path or with longest duration
                    if "Duration" in result.columns:
                        longest = result.nlargest(3, "Duration")
                        function_results["get_schedule_timeline"] += f"\nLongest activities: {longest['Activity Id'].tolist()}"
            except Exception as e:
                st.warning(f"Failed to get schedule timeline: {str(e)}")
        
        # Check for progress/status summary
        summary_keywords = ["summary", "overview", "progress", "status summary", "overall"]
        if any(keyword in query.lower() for keyword in summary_keywords):
            function_calls.append("get_progress_summary")
            try:
                result = self.db_manager.get_progress_summary()
                if not result.empty:
                    function_results["get_progress_summary"] = f"Progress summary:\n{result.to_string()}"
            except Exception as e:
                st.warning(f"Failed to get progress summary: {str(e)}")
        
        return function_calls, function_results

    def _enhance_query_with_context(self, query: str, function_results: Dict[str, Any] = None) -> str:
        """Enhance the user query with relevant data context."""
        if st.session_state.data_source == "database":
            # For database mode, we've already fetched function results
            return query
        
        # For file mode, enhance with Excel data context
        if 'uploaded_data' not in st.session_state:
            return query

        df = st.session_state.uploaded_data
        relevant_context = ""

        # Add activity IDs context if query mentions specific activities
        if any(id_ref in query.lower() for id_ref in ['activity', 'task', 'id']):
            if "Activity Id" in df.columns:
                activity_ids = df['Activity Id'].unique()[:10]  # Limit to first 10
                relevant_context += f"\nAvailable Activity IDs: {', '.join(map(str, activity_ids))}"
                if len(df['Activity Id'].unique()) > 10:
                    relevant_context += f" (showing 10 of {len(df['Activity Id'].unique())})"

        # Add status context if query mentions status
        if 'status' in query.lower() and "Status" in df.columns:
            status_summary = df['Status'].value_counts().to_dict()
            relevant_context += f"\nStatus Summary: {status_summary}"

        # Add progress context if query mentions progress
        if 'progress' in query.lower() and "Progress" in df.columns:
            progress_avg = df['Progress'].mean()
            relevant_context += f"\nAverage Progress: {progress_avg:.1f}%"

        # Combine original query with context
        if relevant_context:
            enhanced_query = f"{query}\n\nRelevant Data Context:{relevant_context}"
            return enhanced_query
        return query