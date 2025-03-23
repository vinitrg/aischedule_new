import streamlit as st
import requests
import json
from typing import Tuple, Dict, Any
from src.database.connection import get_db_connection


class SQLQueryGenerator:
    """
    Class to generate SQL queries from natural language using Azure OpenAI API
    """
    
    def __init__(self):
        """Initialize the SQL Query Generator with Azure OpenAI credentials"""
        self.api_key = st.secrets.get("AZURE_OPENAI_API_KEY", "")
        self.api_endpoint = st.secrets.get("AZURE_OPENAI_API_ENDPOINT", "")
        
        # Load database schema information
        self.schema_info = self._load_schema_info()
    
    def _load_schema_info(self) -> Dict[str, Any]:
        """
        Load database schema information from session state or directly from the database
        """
        # If schema is already in session state, use it
        if "schema_info" in st.session_state:
            return st.session_state.schema_info
        
        # Otherwise get schema directly from the database
        try:
            db = get_db_connection()
            
            if not db.is_connected():
                db.connect()
            
            if db.is_connected():
                # Get tables from database
                tables = db.get_tables()
                
                schema_info = {
                    "tables": {},
                    "relationships": []
                }
                
                # For each table, get its schema
                for table in tables:
                    table_schema = db.get_table_schema(table)
                    if table_schema:
                        schema_info["tables"][table] = {
                            "columns": table_schema
                        }
                
                # Get relationships
                relationships = db.get_table_relationships()
                schema_info["relationships"] = relationships
                
                # Store in session state for future use
                st.session_state.schema_info = schema_info
                
                return schema_info
            else:
                # If not connected, return a placeholder schema
                return self._get_fallback_schema()
        except Exception as e:
            print(f"Error loading schema from database: {str(e)}")
            return self._get_fallback_schema()
    
    # def _get_fallback_schema(self) -> Dict[str, Any]:
    #     """
    #     Provide a fallback schema if unable to connect to the database
    #     """
    #     # This is used only if we can't get the actual schema
    #     return {
    #         "tables": {
    #             "activities": {
    #                 "columns": [
    #                     {"name": "Activity Id", "type": "nvarchar"},
    #                     {"name": "WBS1", "type": "nvarchar"},
    #                     {"name": "WBS2", "type": "nvarchar"},
    #                     {"name": "WBS3", "type": "nvarchar"},
    #                     {"name": "WBS4", "type": "nvarchar"},
    #                     {"name": "WBS5", "type": "nvarchar"},
    #                     {"name": "WBS6", "type": "nvarchar"},
    #                     {"name": "WBS7", "type": "nvarchar"},
    #                     {"name": "WBS8", "type": "nvarchar"},
    #                     {"name": "WBS9", "type": "varchar"},
    #                     {"name": "Status", "type": "nvarchar"},
    #                     {"name": "StartDate", "type": "datetime2"},
    #                     {"name": "EndDate", "type": "datetime2"},
    #                     {"name": "Duration", "type": "int"},
    #                     {"name": "Progress", "type": "int"},
    #                     {"name": "Total_Float", "type": "nvarchar"},
    #                     {"name": "Manpower", "type": "int"},
    #                     {"name": "Trade_Partners", "type": "nvarchar"},
    #                     {"name": "VDC", "type": "nvarchar"}
    #                 ]
    #             }
    #         }
    #     }
    
    def refresh_schema(self):
        """
        Force a refresh of the schema information from the database
        """
        if "schema_info" in st.session_state:
            del st.session_state.schema_info
        self.schema_info = self._load_schema_info()
    
    def _format_system_prompt(self) -> str:
        """
        Format the system prompt with database schema information
        """
        # Convert schema info to a formatted string
        schema_str = json.dumps(self.schema_info, indent=2)
        
        return f"""You are an expert SQL query generator for a construction project management database.
Your task is to convert natural language questions into valid SQL queries.

DATABASE SCHEMA:
{schema_str}

IMPORTANT GUIDELINES:
1. Focus primarily on the 'activities' table as requested by the user.
2. Generate only the SQL query without explanations.
3. Use proper SQL syntax for SQL Server.
4. Distinguish between WBS parent items (no Status) and actual activities (with Status), strictly avoid printing them.
5. Ensure column names are enclosed in square brackets when they contain spaces or special characters.
6. For date operations, use proper SQL Server date functions.
8. If the query involves filtering by WBS levels, make appropriate comparisons considering data types.
9. Return only the SQL query, nothing else.
"""
    
    def generate_sql_query(self, natural_language_query: str) -> Tuple[bool, str]:
        """
        Generate a SQL query from natural language using Azure OpenAI
        
        Args:
            natural_language_query: The natural language query to convert to SQL
            
        Returns:
            Tuple of (success, result)
            - success: Boolean indicating if the query generation was successful
            - result: Either the generated SQL query or an error message
        """
        try:
            # Validate inputs
            if not self.api_key or not self.api_endpoint:
                return False, "Azure OpenAI API credentials are missing."
            
            if not natural_language_query:
                return False, "Please provide a natural language query."
            
            # Set up the headers for the API request
            headers = {
                "Content-Type": "application/json",
                "api-key": self.api_key,
            }
            
            # Create the prompt with the system message and user query
            data = {
                "messages": [
                    {"role": "system", "content": self._format_system_prompt()},
                    {"role": "user", "content": f"Generate a SQL query for: {natural_language_query}"}
                ],
                "max_tokens": 500,
                "temperature": 0.1,  # Lower temperature for more deterministic output
                "top_p": 0.95
            }
            
            # Make the API request
            with st.spinner("Generating SQL query..."):
                response = requests.post(
                    self.api_endpoint,
                    headers=headers,
                    json=data,
                    timeout=30
                )
                
                # Check if the request was successful
                response.raise_for_status()
                
                # Parse the response
                response_data = response.json()
                
                if 'choices' in response_data and len(response_data['choices']) > 0:
                    generated_sql = response_data['choices'][0]['message']['content'].strip()
                    
                    # Clean up the response - sometimes the model adds ```sql and ``` markers
                    if generated_sql.startswith("```sql"):
                        generated_sql = generated_sql[7:]
                    if generated_sql.endswith("```"):
                        generated_sql = generated_sql[:-3]
                    
                    return True, generated_sql.strip()
                else:
                    return False, "Received unexpected response format from Azure OpenAI API."
                
        except Exception as e:
            return False, f"Error generating SQL query: {str(e)}"


def get_query_generator() -> SQLQueryGenerator:
    """Get or create the SQL Query Generator singleton"""
    if "query_generator" not in st.session_state:
        st.session_state.query_generator = SQLQueryGenerator()
    
    return st.session_state.query_generator