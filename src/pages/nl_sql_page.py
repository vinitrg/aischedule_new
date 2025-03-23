import streamlit as st
import pandas as pd
from src.nlp.query_generator import get_query_generator
from src.nlp.result_humanizer import get_result_humanizer
from src.database.connection import get_db_connection

# Initialize session state variables if they don't exist
if 'nl_query' not in st.session_state:
    st.session_state.nl_query = ""
    
if 'sql_query' not in st.session_state:
    st.session_state.sql_query = ""
    
if 'query_result' not in st.session_state:
    st.session_state.query_result = None

# Very important - add a flag in session state to track if summary button was clicked
if 'generate_summary' not in st.session_state:
    st.session_state.generate_summary = False

# Add a variable to store the generated summary
if 'summary' not in st.session_state:
    st.session_state.summary = ""

# Define a callback function for the button click
def set_generate_summary():
    st.session_state.generate_summary = True

def nl_sql_page():
    st.header("Natural Language SQL Generator")
    st.markdown("""
    Ask questions about your construction project data in plain English.
    The system will convert your question into a SQL query and return the results.
    """)
    
    # Get SQL query generator
    query_generator = get_query_generator()
    
    # Get database connection
    db = get_db_connection()
    
    # Natural language query input
    nl_query = st.text_area(
        "Enter your question in natural language:",
        placeholder="For example: 'Show me all activities with progress greater than 50%'",
        height=100
    )
    
    # Add some example queries that users can click to populate the text area
    st.subheader("Example questions:")
    example_queries = [
        "Show all activities with progress greater than 75%",
        "Find activities starting in the next month",
        "List activities with duration more than 30 days that are less than 50% complete",
        "What are the activities with the longest duration?",
        "Show me activities related to WBS1 containing 'foundation'"
    ]
    
    col1, col2 = st.columns(2)
    
    for i, example in enumerate(example_queries):
        if i % 2 == 0:
            if col1.button(f"📝 {example}", key=f"example_{i}"):
                # Reset summary state when selecting a new example
                st.session_state.generate_summary = False
                st.session_state.summary = ""
                nl_query = example
                st.rerun()
        else:
            if col2.button(f"📝 {example}", key=f"example_{i}"):
                # Reset summary state when selecting a new example
                st.session_state.generate_summary = False
                st.session_state.summary = ""
                nl_query = example
                st.rerun()
    
    # Process the query
    if st.button("Generate SQL and Execute", type="primary") and nl_query:
        # Reset summary state when running a new query
        st.session_state.generate_summary = False
        st.session_state.summary = ""
        
        # Generate SQL query
        success, result = query_generator.generate_sql_query(nl_query)
        
        if success:
            # Display the generated SQL
            st.subheader("Generated SQL Query:")
            st.code(result, language="sql")
            
            # Store the queries in session state for later use
            st.session_state.nl_query = nl_query
            st.session_state.sql_query = result
            
            # Execute the query
            with st.spinner("Executing query..."):
                try:
                    query_success, query_result = db.execute_query(result)
                    
                    if query_success:
                        if isinstance(query_result, pd.DataFrame):
                            st.subheader("Query Results:")
                            
                            # Store query result in session state
                            st.session_state.query_result = query_result
                            
                            # Check if we got any results
                            if len(query_result) > 0:
                                # Alert if large result set
                                if len(query_result) > 1000:
                                    st.warning(f"Large result set detected: {len(query_result)} rows. Showing first 1000 rows in the table view.")
                                    display_df = query_result.head(1000)
                                else:
                                    display_df = query_result
                                
                                # Display results
                                st.dataframe(display_df, use_container_width=True)
                                
                                # Display result count
                                st.info(f"Query returned {len(query_result)} rows.")
                                
                                # Add download button for the results
                                csv = query_result.to_csv(index=False)
                                st.download_button(
                                    label="Download results as CSV",
                                    data=csv,
                                    file_name="query_results.csv",
                                    mime="text/csv"
                                )
                                
                                # Button that sets the flag, doesn't directly execute code
                                st.button("📊 Summarize Results", on_click=set_generate_summary, key="summarize_btn")
                                
                            else:
                                st.info("The query executed successfully but returned no results.")
                                
                        else:
                            st.success(f"Query executed successfully. Affected rows: {query_result}")
                    else:
                        st.error(f"Error executing query: {query_result}")
                
                except Exception as e:
                    st.error(f"Error executing query: {str(e)}")
                    st.info("You may need to modify the SQL query if it contains errors.")
        else:
            st.error(f"Failed to generate SQL: {result}")
    
    # Check if we should generate a summary (after all UI elements are rendered)
    if st.session_state.generate_summary and st.session_state.query_result is not None:
        # Reset the flag immediately to prevent multiple executions
        st.session_state.generate_summary = False
        
        # Generate the summary
        with st.spinner("Analyzing results..."):
            result_humanizer = get_result_humanizer()
            success, explanation = result_humanizer.humanize_result(
                st.session_state.nl_query,
                st.session_state.sql_query,
                st.session_state.query_result
            )
            
            if success:
                # Store the summary in session state
                st.session_state.summary = explanation
            else:
                st.session_state.summary = f"Error: {explanation}"
    
    # Display the summary if it exists (this will persist across reruns)
    if st.session_state.summary:
        st.subheader("Analysis:")
        st.markdown(st.session_state.summary)
    
    # Add an advanced mode with the ability to edit the generated SQL
    if nl_query:
        st.subheader("Advanced Mode")
        advanced_mode = st.checkbox("Enable SQL editing")
        
        if advanced_mode:
            # Generate SQL first
            success, result = query_generator.generate_sql_query(nl_query)
            
            if success:
                # Allow editing the SQL
                edited_sql = st.text_area("Edit SQL Query:", value=result, height=200)
                
                if st.button("Execute Edited SQL"):
                    # Reset summary state when running a new edited query
                    st.session_state.generate_summary = False
                    st.session_state.summary = ""
                    
                    with st.spinner("Executing custom query..."):
                        try:
                            query_success, query_result = db.execute_query(edited_sql)
                            
                            # Store the queries in session state for later use
                            st.session_state.nl_query = nl_query
                            st.session_state.sql_query = edited_sql
                            
                            if query_success:
                                if isinstance(query_result, pd.DataFrame):
                                    st.subheader("Query Results:")
                                    
                                    # Store query result in session state
                                    st.session_state.query_result = query_result
                                    
                                    # Check if we got any results
                                    if len(query_result) > 0:
                                        # Alert if large result set
                                        if len(query_result) > 1000:
                                            st.warning(f"Large result set detected: {len(query_result)} rows. Showing first 1000 rows in the table view.")
                                            display_df = query_result.head(1000)
                                        else:
                                            display_df = query_result
                                        
                                        # Display results
                                        st.dataframe(display_df, use_container_width=True)
                                        
                                        # Display result count
                                        st.info(f"Query returned {len(query_result)} rows.")
                                        
                                        # Add download button for the results
                                        csv = query_result.to_csv(index=False)
                                        st.download_button(
                                            label="Download results as CSV",
                                            data=csv,
                                            file_name="query_results.csv",
                                            mime="text/csv"
                                        )
                                        
                                        # Button that sets the flag for advanced mode
                                        st.button("📊 Summarize Results", on_click=set_generate_summary, key="adv_summarize_btn")
                                        
                                    else:
                                        st.info("The query executed successfully but returned no results.")
                                        
                                else:
                                    st.success(f"Query executed successfully. Affected rows: {query_result}")
                            else:
                                st.error(f"Error executing query: {query_result}")
                        
                        except Exception as e:
                            st.error(f"Error executing query: {str(e)}")
            else:
                st.error(f"Failed to generate initial SQL: {result}")