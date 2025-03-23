import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import logging
import traceback
import sys
from typing import Dict, Any, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ResultHumanizer:
    """
    Class to convert SQL query results into human-friendly explanations
    using Azure OpenAI API
    """
    
    def __init__(self):
        """Initialize the Result Humanizer with Azure OpenAI credentials"""
        self.api_key = st.secrets.get("AZURE_OPENAI_API_KEY", "")
        self.api_endpoint = st.secrets.get("AZURE_OPENAI_API_ENDPOINT", "")
        
        # Debug log for initialization
        if not self.api_key or not self.api_endpoint:
            st.warning("Azure OpenAI credentials are missing. Please check your .streamlit/secrets.toml file.")
            logger.warning("Azure OpenAI credentials are missing during ResultHumanizer initialization")
        else:
            logger.info(f"ResultHumanizer initialized with API endpoint: {self.api_endpoint[:20]}...")
        
        # Configuration options
        self.max_rows_for_full_context = 100  # Maximum rows to send to GPT in full
        self.sample_size = 20  # Number of rows to sample for large datasets
    
    def _prepare_result_for_gpt(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Prepare query results for sending to GPT API by summarizing large datasets
        
        Args:
            df: DataFrame containing query results
            
        Returns:
            Dict containing prepared data with appropriate summarization
        """
        try:
            logger.info(f"Preparing data for GPT with DataFrame shape: {df.shape}")
            
            row_count = len(df)
            col_count = len(df.columns)
            
            result = {
                "row_count": row_count,
                "column_count": col_count,
                "columns": list(df.columns),
                "is_summarized": False,
                "summary_stats": {},
                "sample_data": None,
                "full_data": None
            }
            
            # For empty result sets
            if row_count == 0:
                result["full_data"] = "No data found."
                return result
            
            # Calculate summary statistics for numeric columns
            logger.info("Calculating summary statistics")
            summary_stats = {}
            for col in df.columns:
                try:
                    if pd.api.types.is_numeric_dtype(df[col]):
                        summary_stats[col] = {
                            "min": float(df[col].min()) if not pd.isna(df[col].min()) else None,
                            "max": float(df[col].max()) if not pd.isna(df[col].max()) else None,
                            "mean": float(df[col].mean()) if not pd.isna(df[col].mean()) else None,
                            "median": float(df[col].median()) if not pd.isna(df[col].median()) else None
                        }
                    elif pd.api.types.is_datetime64_dtype(df[col]):
                        summary_stats[col] = {
                            "min": str(df[col].min()) if not pd.isna(df[col].min()) else None,
                            "max": str(df[col].max()) if not pd.isna(df[col].max()) else None
                        }
                    elif pd.api.types.is_string_dtype(df[col]):
                        # For string columns, get unique value counts (top 5)
                        value_counts = df[col].value_counts().head(5).to_dict()
                        # Convert values to strings to ensure they're serializable
                        value_counts = {str(k): int(v) for k, v in value_counts.items()}
                        summary_stats[col] = {
                            "unique_values": int(len(df[col].unique())),
                            "most_common": value_counts
                        }
                except Exception as e:
                    logger.warning(f"Error calculating statistics for column {col}: {str(e)}")
                    # Add a simple summary instead
                    summary_stats[col] = {"note": "Could not calculate statistics"}
            
            result["summary_stats"] = summary_stats
            
            # For small result sets, include all data
            if row_count <= self.max_rows_for_full_context:
                logger.info(f"Including full data ({row_count} rows)")
                # Convert DataFrame to list of dicts with proper handling for non-serializable types
                try:
                    # Replace NaN values with None for JSON serialization
                    records = df.replace({np.nan: None}).to_dict(orient="records")
                    # Convert any non-serializable types to strings
                    for i, record in enumerate(records):
                        for key, value in record.items():
                            if not (value is None or isinstance(value, (str, int, float, bool))):
                                records[i][key] = str(value)
                    result["full_data"] = records
                except Exception as e:
                    logger.warning(f"Error converting full data to dict: {str(e)}")
                    # If serialization fails, convert to string representation
                    result["full_data"] = str(df.head(10))
                return result
            
            # For large result sets, include sample and summary
            logger.info(f"Sampling data for large dataset ({row_count} rows)")
            result["is_summarized"] = True
            
            # Take a representative sample
            try:
                # Include first 10 rows, last 5 rows, and 5 random rows from the middle
                first_rows = df.head(10).replace({np.nan: None}).to_dict(orient="records")
                last_rows = df.tail(5).replace({np.nan: None}).to_dict(orient="records")
                
                # Random sample from the middle (excluding first 10 and last 5)
                middle_df = df.iloc[10:-5]
                middle_sample = []
                if len(middle_df) > 0:
                    sample_size = min(5, len(middle_df))
                    if sample_size > 0:
                        middle_sample = middle_df.sample(sample_size).replace({np.nan: None}).to_dict(orient="records")
                
                # Convert any non-serializable types to strings
                for sample_list in [first_rows, middle_sample, last_rows]:
                    for i, record in enumerate(sample_list):
                        for key, value in record.items():
                            if not (value is None or isinstance(value, (str, int, float, bool))):
                                sample_list[i][key] = str(value)
                
                result["sample_data"] = {
                    "first_rows": first_rows,
                    "middle_sample": middle_sample,
                    "last_rows": last_rows
                }
            except Exception as e:
                logger.warning(f"Error preparing sample data: {str(e)}")
                # If sampling fails, use a simple approach
                result["sample_data"] = {
                    "first_rows": str(df.head(10)),
                    "last_rows": str(df.tail(5))
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in _prepare_result_for_gpt: {str(e)}")
            logger.error(traceback.format_exc())
            # Return a minimal result
            return {
                "row_count": len(df) if isinstance(df, pd.DataFrame) else 0,
                "column_count": len(df.columns) if isinstance(df, pd.DataFrame) else 0,
                "columns": list(df.columns) if isinstance(df, pd.DataFrame) else [],
                "full_data": "Error preparing data for analysis."
            }
    
    def _format_system_prompt(self) -> str:
        """Format the system prompt for the GPT model"""
        return """You are an expert data analyst working in the construction industry.
Your task is to analyze SQL query results and provide a clear, concise explanation in natural language.

GUIDELINES:
1. Provide a conversational summary of the data that addresses the original question.
2. Highlight key insights, trends, or patterns in the data.
3. If dealing with a sampled dataset, acknowledge this fact and note that your analysis is based on a sample.
4. Use construction industry terminology appropriately.
5. If the data is empty or shows no results, explain what that might mean.
6. Keep your explanation concise but informative (2-4 paragraphs maximum).
7. Do not include all data values in your explanation, focus on highlights and summaries.
8. If statistical data is available (min, max, average), include relevant statistics that help answer the question.
"""
    
    def _format_query_context(self, nl_query: str, sql_query: str, result_data: Dict[str, Any]) -> str:
        """
        Format the context information about the query and results for GPT
        
        Args:
            nl_query: Original natural language query
            sql_query: SQL query that was executed
            result_data: Prepared result data
            
        Returns:
            Formatted context string
        """
        try:
            logger.info("Formatting query context for GPT")
            
            context = f"ORIGINAL QUESTION: {nl_query}\n\n"
            context += f"SQL QUERY EXECUTED:\n{sql_query}\n\n"
            
            context += f"RESULT SUMMARY:\n"
            context += f"- Total rows: {result_data['row_count']}\n"
            context += f"- Columns: {', '.join(result_data['columns'])}\n\n"
            
            # Add statistics summary if available
            if result_data['summary_stats']:
                context += "STATISTICAL SUMMARY:\n"
                for col, stats in result_data['summary_stats'].items():
                    context += f"- {col}:\n"
                    for stat_name, stat_value in stats.items():
                        if isinstance(stat_value, dict):
                            # Limit the size of dictionary values to prevent context overflow
                            try:
                                context += f"  - {stat_name}: {json.dumps(stat_value)[:500]}\n"
                            except:
                                context += f"  - {stat_name}: [complex value]\n"
                        else:
                            context += f"  - {stat_name}: {stat_value}\n"
                context += "\n"
            
            # Add data - truncate to manageable size
            max_data_size = 2000  # Character limit for data representation
            
            if result_data['is_summarized']:
                context += "DATA SAMPLE (partial dataset - too large to show completely):\n"
                
                if 'sample_data' in result_data and result_data['sample_data']:
                    if isinstance(result_data['sample_data'], str):
                        context += result_data['sample_data'][:max_data_size]
                    else:
                        # First rows
                        context += "First rows:\n"
                        try:
                            first_rows_str = json.dumps(result_data['sample_data']['first_rows'], indent=2)
                            context += first_rows_str[:max_data_size // 2]
                            context += "\n\n"
                            
                            # Last rows
                            context += "Last rows:\n"
                            last_rows_str = json.dumps(result_data['sample_data']['last_rows'], indent=2)
                            context += last_rows_str[:max_data_size // 2]
                        except Exception as e:
                            context += f"Error formatting sample data: {str(e)}\n"
                            if 'first_rows' in result_data['sample_data']:
                                context += f"First rows: {str(result_data['sample_data']['first_rows'])[:500]}\n"
                            if 'last_rows' in result_data['sample_data']:
                                context += f"Last rows: {str(result_data['sample_data']['last_rows'])[:500]}\n"
                else:
                    context += "Sample data not available."
            elif result_data['full_data']:
                if isinstance(result_data['full_data'], str):
                    context += f"DATA: {result_data['full_data'][:max_data_size]}"
                else:
                    context += "COMPLETE DATASET (truncated for API limit):\n"
                    try:
                        full_data_str = json.dumps(result_data['full_data'], indent=2)
                        context += full_data_str[:max_data_size]
                    except Exception as e:
                        context += f"Error formatting data: {str(e)}\n"
                        context += f"Data preview: {str(result_data['full_data'])[:500]}"
            
            # Check if context is too large
            if len(context) > 8000:
                logger.warning(f"Context is very large: {len(context)} characters. Truncating.")
                return context[:8000] + "\n\n[Content truncated due to size limitations]"
            
            return context
            
        except Exception as e:
            logger.error(f"Error in _format_query_context: {str(e)}")
            logger.error(traceback.format_exc())
            # Return a simplified context that won't fail
            simplified = f"ORIGINAL QUESTION: {nl_query}\n\n"
            simplified += f"SQL QUERY EXECUTED:\n{sql_query}\n\n"
            simplified += f"DATA SUMMARY: The query returned {result_data['row_count']} rows with the following columns: {', '.join(result_data['columns'])}\n"
            simplified += "Error creating detailed context. Please analyze based on this basic information."
            return simplified
    
    def humanize_result(self, nl_query: str, sql_query: str, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Convert SQL query results to a human-friendly explanation
        
        Args:
            nl_query: Original natural language query
            sql_query: SQL query that was executed
            df: DataFrame containing query results
            
        Returns:
            Tuple of (success, result)
            - success: Boolean indicating if the humanization was successful
            - result: Either the humanized explanation or an error message
        """
        try:
            # Print debug info to Streamlit
            st.write("Analyzing results, please wait...")
            
            # Debug log
            logger.info(f"Starting humanize_result with query: {nl_query[:50]}...")
            
            # Validate inputs
            if not self.api_key or not self.api_endpoint:
                logger.error("Azure OpenAI credentials are missing")
                return False, "Azure OpenAI API credentials are missing. Please check your .streamlit/secrets.toml file."
            
            if not isinstance(df, pd.DataFrame):
                logger.error(f"Expected DataFrame, got {type(df)}")
                return False, f"Expected DataFrame for results, got {type(df)}."
            
            # Prepare the result data
            prepared_data = self._prepare_result_for_gpt(df)
            
            # Format the context for GPT
            query_context = self._format_query_context(nl_query, sql_query, prepared_data)
            
            # Log context size
            logger.info(f"Context size: {len(query_context)} characters")
            
            # Set up the headers for the API request
            headers = {
                "Content-Type": "application/json",
                "api-key": self.api_key,
            }
            
            # Create the prompt
            data = {
                "messages": [
                    {"role": "system", "content": self._format_system_prompt()},
                    {"role": "user", "content": query_context}
                ],
                "max_tokens": 800,
                "temperature": 0.5,
                "top_p": 0.95
            }
            
            # Make the API request
            logger.info(f"Sending request to Azure OpenAI API: {self.api_endpoint}")
            st.write("Sending request to Azure OpenAI...")
            
            try:
                response = requests.post(
                    self.api_endpoint,
                    headers=headers,
                    json=data,
                    timeout=30
                )
                
                # Check if the request was successful
                response.raise_for_status()
                
                # Log response info
                logger.info(f"API response status: {response.status_code}")
                
                # Parse the response
                response_data = response.json()
                
                if 'choices' in response_data and len(response_data['choices']) > 0:
                    explanation = response_data['choices'][0]['message']['content'].strip()
                    logger.info(f"Successfully generated explanation ({len(explanation)} chars)")
                    return True, explanation
                else:
                    logger.error(f"Unexpected API response format: {response_data}")
                    return False, f"Received unexpected response format from Azure OpenAI API. Please check your API endpoint configuration."
                    
            except requests.exceptions.Timeout:
                logger.error("API request timed out")
                return False, "Azure OpenAI API request timed out after 30 seconds. Please try with a smaller dataset or check your network connection."
                
            except requests.exceptions.RequestException as e:
                logger.error(f"API request failed: {str(e)}")
                return False, f"Azure OpenAI API request failed: {str(e)}"
                
        except Exception as e:
            logger.error(f"Error in humanize_result: {str(e)}")
            logger.error(traceback.format_exc())
            return False, f"Error generating explanation: {str(e)}"


def get_result_humanizer() -> ResultHumanizer:
    """Get or create the Result Humanizer singleton"""
    if "result_humanizer" not in st.session_state:
        logger.info("Creating new ResultHumanizer instance")
        st.session_state.result_humanizer = ResultHumanizer()
    
    return st.session_state.result_humanizer