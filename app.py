import streamlit as st
import pandas as pd
import json
import requests
from src.database.connection import get_db_connection
from src.nlp.query_generator import get_query_generator
from src.azure.openai_service import get_openai_service
from src.pages.nl_sql_page import nl_sql_page

# Set page configuration
st.set_page_config(
    page_title="Natural Language SQL Generator",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

def test_openai_connection():
    """Test the connection to Azure OpenAI API"""
    service = get_openai_service()
    return service.test_connection()

def print_database_analysis(db):
    """Print database schema analysis to console for debugging and sharing"""
    schema_info = {
        "tables": {},
        "relationships": []
    }
    
    # Get all tables
    tables = db.get_tables()
    print(f"\n===== DATABASE ANALYSIS =====")
    print(f"Found {len(tables)} tables: {', '.join(tables)}")
    
    # Get schema for each table
    for table in tables:
        schema = db.get_table_schema(table)
        schema_info["tables"][table] = {
            "columns": schema
        }
        
        # Print table schema
        print(f"\n--- TABLE: {table} ---")
        for col in schema:
            print(f"  • {col['name']} ({col['type']}{' NOT NULL' if col['nullable'] == 'NO' else ''})")
    
    # Get relationships
    relationships = db.get_table_relationships()
    schema_info["relationships"] = relationships
    
    # Print relationships
    print("\n--- TABLE RELATIONSHIPS ---")
    for rel in relationships:
        print(f"  • {rel['parent_table']}.{rel['parent_column']} → {rel['referenced_table']}.{rel['referenced_column']}")
    
    # Print JSON version for easy sharing
    print("\n===== DATABASE SCHEMA JSON =====")
    print(json.dumps(schema_info, indent=2))
    print("===== END DATABASE ANALYSIS =====\n")
    
    # Store the schema info in session state for reuse
    st.session_state.schema_info = schema_info
    
    return schema_info

def main():
    # Page title and description
    st.title("Natural Language SQL Generator")
    st.markdown("""
    This application allows you to query your construction project database using natural language.
    Let's start by exploring the database structure.
    """)
    
    # Test Azure OpenAI connection
    openai_success, openai_message = test_openai_connection()
    
    # Check for both database and Azure OpenAI connections in the sidebar
    
    # 1. Azure OpenAI Connection
    st.sidebar.subheader("Azure OpenAI Connection")
    openai_status = st.sidebar.empty()
    
    if openai_success:
        openai_status.success("✅ Connected to Azure OpenAI")
    else:
        openai_status.error(f"❌ Azure OpenAI connection failed")
        st.sidebar.info(f"Error: {openai_message}")
        st.sidebar.info("Please check your AZURE_OPENAI_API_KEY and AZURE_OPENAI_API_ENDPOINT in .streamlit/secrets.toml")
    
    # 2. Database Connection
    st.sidebar.subheader("Database Connection")
    connection_status = st.sidebar.empty()
    
    # Connect to database
    db = get_db_connection()
    
    if db.is_connected():
        connection_status.success("✅ Connected to database")
        # Print database analysis to console
        schema_info = print_database_analysis(db)
    else:
        with st.spinner("Connecting to database..."):
            if db.connect():
                connection_status.success("✅ Connected to database")
                # Print database analysis to console
                schema_info = print_database_analysis(db)
            else:
                connection_status.error("❌ Database connection failed")
                st.sidebar.info("Please check your connection credentials in .streamlit/secrets.toml")
    

    
    # Create tabs for different sections
    tab1, tab2,  = st.tabs(["Natural Language Query", "Database Explorer",])
    
    with tab1:
        # Use the imported nl_sql_page function instead of the inline one
        nl_sql_page()
    
    with tab2:
        st.header("Database Schema Explorer")
        
        # Get list of tables
        tables = db.get_tables()
        
        if not tables:
            st.warning("No tables found in the database or failed to retrieve tables.")
        else:
            st.success(f"Found {len(tables)} tables in the database.")
            
            # Table selection
            selected_table = st.selectbox("Select a table to explore:", tables)
            
            if selected_table:
                # Get schema for selected table
                schema = db.get_table_schema(selected_table)
                
                if schema:
                    # Convert schema to DataFrame for display
                    schema_df = pd.DataFrame(schema)
                    st.subheader(f"Schema for table: {selected_table}")
                    st.dataframe(schema_df, use_container_width=True)
                    
                    # Sample data preview
                    st.subheader(f"Sample data from {selected_table}")
                    # Use square brackets around table name to handle special characters and reserved words
                    success, result = db.execute_query(f"SELECT TOP 5 * FROM [{selected_table}]")
                    
                    if success and isinstance(result, pd.DataFrame):
                        st.dataframe(result, use_container_width=True)
                    else:
                        st.error(f"Failed to retrieve sample data: {result}")
                else:
                    st.warning(f"Could not retrieve schema for table {selected_table}")
            
            # Display table relationships
            st.subheader("Table Relationships")
            relationships = db.get_table_relationships()
            
            if relationships:
                rel_df = pd.DataFrame(relationships)
                st.dataframe(rel_df, use_container_width=True)
            else:
                st.info("No relationships found between tables or failed to retrieve relationships.")
    
    
    
    

if __name__ == "__main__":
    main()