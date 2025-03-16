# database.py
import streamlit as st
import pandas as pd
import sqlite3
from sqlalchemy import create_engine
from sqlalchemy import inspect
import os
from typing import Optional, Dict, List, Any

class DatabaseManager:
    """
    Handles database connections and operations for the construction schedule app.
    Supports SQLite for local development and can be extended to other databases.
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize the database manager.
        
        Args:
            connection_string: Database connection string from environment or secrets.
                              If None, uses a local SQLite database.
        """
        self.connection_string = connection_string or st.secrets.get(
            "DATABASE_URL", "sqlite:///construction_schedule.db"
        )
        self.engine = None
        self.connection = None
    
    def connect(self) -> bool:
        """
        Establish connection to the database.
        
        Returns:
            bool: True if connection was successful, False otherwise.
        """
        try:
            if self.connection_string.startswith("sqlite:"):
                # SQLite connection
                db_path = self.connection_string.replace("sqlite:///", "")
                self.connection = sqlite3.connect(db_path)
                self.engine = create_engine(self.connection_string)
                return True
            else:
                # Other database connections (PostgreSQL, MySQL, etc.)
                self.engine = create_engine(self.connection_string)
                self.connection = self.engine.connect()
                return True
        except Exception as e:
            st.error(f"Database connection error: {str(e)}")
            return False
    
    def disconnect(self) -> None:
        """Close the database connection."""
        if self.connection is not None:
            self.connection.close()
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        Execute a SQL query and return results as DataFrame.
        
        Args:
            query: SQL query string
            params: Parameters for query (for parameterized queries)
            
        Returns:
            DataFrame with query results
        """
        try:
            if self.connection is None:
                self.connect()
            
            if params:
                return pd.read_sql(query, self.connection, params=params)
            else:
                return pd.read_sql(query, self.connection)
        except Exception as e:
            st.error(f"Query execution error: {str(e)}")
            return pd.DataFrame()
    
    def import_excel_to_db(self, df: pd.DataFrame, table_name: str) -> bool:
        """
        Import data from DataFrame to database table.
        
        Args:
            df: DataFrame containing the data
            table_name: Name of the table to create/update
            
        Returns:
            bool: True if import was successful, False otherwise
        """
        try:
            if self.engine is None:
                self.connect()
                
            # Convert DataFrame to SQL table
            df.to_sql(table_name, self.engine, if_exists='replace', index=False)
            st.success(f"Data successfully imported to '{table_name}' table")
            return True
        except Exception as e:
            st.error(f"Error importing data to database: {str(e)}")
            return False
    
    def get_activities(self, filters: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        Get activities from the database with optional filters.
        
        Args:
            filters: Dictionary of column:value pairs to filter by
            
        Returns:
            DataFrame of activities
        """
        base_query = "SELECT * FROM activities"
        
        if filters:
            where_clauses = []
            params = {}
            
            for col, value in filters.items():
                where_clauses.append(f"{col} = :{col}")
                params[col] = value
                
            if where_clauses:
                base_query += " WHERE " + " AND ".join(where_clauses)
                
            return self.execute_query(base_query, params)
        else:
            return self.execute_query(base_query)
    
    def get_activity_by_id(self, activity_id: str) -> pd.DataFrame:
        """
        Get a specific activity by ID.
        
        Args:
            activity_id: The activity ID to retrieve
            
        Returns:
            DataFrame containing the activity data
        """
        query = "SELECT * FROM activities WHERE \"Activity Id\" = :activity_id"
        return self.execute_query(query, {"activity_id": activity_id})
    
    def get_activities_by_status(self, status: str) -> pd.DataFrame:
        """
        Get activities filtered by status.
        
        Args:
            status: Status value to filter by
            
        Returns:
            DataFrame of activities with the specified status
        """
        query = "SELECT * FROM activities WHERE Status = :status"
        return self.execute_query(query, {"status": status})
    
    def get_progress_summary(self) -> pd.DataFrame:
        """
        Get a summary of project progress.
        
        Returns:
            DataFrame with progress statistics
        """
        query = """
        SELECT 
            Status,
            COUNT(*) as ActivityCount,
            AVG(Progress) as AvgProgress,
            MIN(Progress) as MinProgress,
            MAX(Progress) as MaxProgress
        FROM activities
        GROUP BY Status
        """
        return self.execute_query(query)
    
    def get_schedule_timeline(self) -> pd.DataFrame:
        """
        Get schedule timeline data for visualization.
        
        Returns:
            DataFrame with timeline data
        """
        query = """
        SELECT 
            "Activity Id",
            "WBS1",
            "StartDate",
            "EndDate",
            "Progress",
            "Duration"
        FROM activities
        WHERE "StartDate" IS NOT NULL AND "EndDate" IS NOT NULL
        ORDER BY "StartDate"
        """
        return self.execute_query(query)
    
    def diagnose_database(self):
        try:
            # Import necessary libraries
            import sqlalchemy as sa
            from sqlalchemy import inspect, text
            
            # Create connection using your existing engine
            inspector = inspect(self.engine)
            
            # Get table list
            tables = inspector.get_table_names()
            st.write(f"Tables in database: {tables}")
            
            # For each table, check row count
            with self.engine.connect() as conn:
                for table in tables:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    st.write(f"Table '{table}' has {count} rows")
                    
                    # If table has data, show sample
                    if count > 0:
                        sample = conn.execute(text(f"SELECT * FROM {table} LIMIT 5"))
                        st.write(f"Sample data from '{table}':")
                        st.dataframe([dict(row) for row in sample])
            
            # Check connection string (hide sensitive parts)
            conn_str = self.connection_string
            if "://" in conn_str:
                parts = conn_str.split("://")
                if "@" in parts[1]:
                    # For URLs with credentials, mask them
                    userpass, hostdbname = parts[1].split("@", 1)
                    conn_str = f"{parts[0]}://****:****@{hostdbname}"
            st.write(f"Using connection: {conn_str}")
            
        except Exception as e:
            st.error(f"Diagnostic error: {str(e)}")


# Helper function to initialize database connection
def get_database_connection() -> DatabaseManager:
    """
    Get or create a database connection using session state.
    
    Returns:
        DatabaseManager instance
    """
    # Create an instance of your database manager
    db_manager = DatabaseManager()
    db_manager.connect()
    # Create an inspector using sqlalchemy's inspect function
    inspector = inspect(db_manager.engine)
    
    # Get database name (extract from the URL)
    db_url = str(db_manager.engine.url)
    db_name = db_url.split("/")[-1].split("?")[0]
    
    # Get table names
    tables = inspector.get_table_names()
    
    # Display information
    st.write(f"Database: {db_name}")
    st.write("Tables:")
    for table in tables:
        st.write(f"- {table}")
    for table in tables:
        st.write(f"- {table}")
    st.write("I've given you tables")
    if "db_manager" not in st.session_state:
        # Initialize DB connection
        st.write("I've given you tables 1")
        db_manager = DatabaseManager()
        if db_manager.connect():
            st.session_state.db_manager = db_manager
            st.write("I'm in connect")
        else:
            st.write("I'm not in connect")
            st.error("Failed to connect to database. Check your connection settings.")
            return None
    st.write("I've given you tables3")
    return st.session_state.db_manager