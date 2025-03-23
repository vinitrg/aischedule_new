import pymssql
import pandas as pd
import streamlit as st
from typing import List, Dict, Any, Tuple, Optional


class DatabaseConnection:
    """Handles connection to Azure SQL Database and query execution"""
    
    def __init__(self):
        """Initialize database connection using Streamlit secrets"""
        try:
            # Get connection parameters from Streamlit secrets
            self.server = st.secrets["azure_sql"]["server"]
            self.database = st.secrets["azure_sql"]["database"]
            self.username = st.secrets["azure_sql"]["username"]
            self.password = st.secrets["azure_sql"]["password"]
            
            # Initialize connection to None
            self.conn = None
            
        except Exception as e:
            st.error(f"Error initializing database connection parameters: {str(e)}")
            raise
    
    def connect(self) -> bool:
        """Establish connection to the database"""
        try:
            self.conn = pymssql.connect(
                server=self.server,
                user=self.username,
                password=self.password,
                database=self.database
            )
            return True
            
        except Exception as e:
            st.error(f"Error connecting to database: {str(e)}")
            self.conn = None
            return False
    
    def disconnect(self) -> None:
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def is_connected(self) -> bool:
        """Check if database connection is active"""
        if self.conn is None:
            return False
        
        try:
            # Try a simple query to check connection
            cursor = self.conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            return True
        except Exception as e:
            st.error(f"Connection check failed: {str(e)}")
            self.conn = None
            return False
    
    def get_tables(self) -> List[str]:
        """Get list of tables in the database"""
        if not self.is_connected():
            if not self.connect():
                return []
        
        try:
            cursor = self.conn.cursor()
            tables = []
            
            # Query for getting all tables
            query = """
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE' 
            ORDER BY TABLE_NAME
            """
            
            cursor.execute(query)
            # pymssql returns results as tuples, not as row objects with attributes
            tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            
            return tables
        
        except Exception as e:
            st.error(f"Error retrieving tables: {str(e)}")
            return []
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Get schema information for a specific table"""
        if not self.is_connected():
            if not self.connect():
                return []
        
        try:
            cursor = self.conn.cursor()
            columns = []
            
            query = f"""
            SELECT 
                COLUMN_NAME, 
                DATA_TYPE, 
                CHARACTER_MAXIMUM_LENGTH,
                IS_NULLABLE, 
                COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """
            
            cursor.execute(query, (table_name,))
            
            for row in cursor.fetchall():
                column_info = {
                    "name": row[0],  # COLUMN_NAME
                    "type": row[1],  # DATA_TYPE
                    "max_length": row[2],  # CHARACTER_MAXIMUM_LENGTH
                    "nullable": row[3],  # IS_NULLABLE
                    "default": row[4]   # COLUMN_DEFAULT
                }
                columns.append(column_info)
            
            cursor.close()
            return columns
        
        except Exception as e:
            st.error(f"Error retrieving schema for table {table_name}: {str(e)}")
            return []
    
    def execute_query(self, query: str, params: Tuple = None) -> Tuple[bool, Any]:
        """Execute a SQL query and return results"""
        if not self.is_connected():
            if not self.connect():
                return False, "Database connection failed"
        
        try:
            cursor = self.conn.cursor()
            
            if params:
                # Replace ? with %s for pymssql compatibility if needed
                query = query.replace('?', '%s')
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Check if query returns results
            if cursor.description:
                # Convert results to DataFrame
                columns = [column[0] for column in cursor.description]
                results = cursor.fetchall()
                
                # Create DataFrame from results
                df = pd.DataFrame.from_records(
                    [list(row) for row in results], 
                    columns=columns
                )
                
                cursor.close()
                return True, df
            else:
                # For queries that don't return results (INSERT, UPDATE, etc.)
                affected_rows = cursor.rowcount
                self.conn.commit()
                cursor.close()
                return True, f"Query executed successfully. Rows affected: {affected_rows}"
        
        except Exception as e:
            error_message = str(e)
            st.error(f"Error executing query: {error_message}")
            return False, error_message
    
    def get_table_relationships(self) -> List[Dict[str, str]]:
        """Get foreign key relationships between tables"""
        if not self.is_connected():
            if not self.connect():
                return []
        
        try:
            query = """
            SELECT 
                fk.name AS FK_NAME,
                tp.name AS PARENT_TABLE,
                cp.name AS PARENT_COLUMN,
                tr.name AS REFERENCED_TABLE,
                cr.name AS REFERENCED_COLUMN
            FROM 
                sys.foreign_keys fk
            INNER JOIN 
                sys.tables tp ON fk.parent_object_id = tp.object_id
            INNER JOIN 
                sys.tables tr ON fk.referenced_object_id = tr.object_id
            INNER JOIN 
                sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
            INNER JOIN 
                sys.columns cp ON fkc.parent_column_id = cp.column_id AND fkc.parent_object_id = cp.object_id
            INNER JOIN 
                sys.columns cr ON fkc.referenced_column_id = cr.column_id AND fkc.referenced_object_id = cr.object_id
            ORDER BY
                tp.name, cp.name
            """
            
            cursor = self.conn.cursor()
            cursor.execute(query)
            
            relationships = []
            for row in cursor.fetchall():
                relationship = {
                    "fk_name": row[0],  # FK_NAME
                    "parent_table": row[1],  # PARENT_TABLE
                    "parent_column": row[2],  # PARENT_COLUMN
                    "referenced_table": row[3],  # REFERENCED_TABLE
                    "referenced_column": row[4]   # REFERENCED_COLUMN
                }
                relationships.append(relationship)
            
            cursor.close()
            return relationships
        
        except Exception as e:
            st.error(f"Error retrieving table relationships: {str(e)}")
            return []
            
    def get_database_schema_info(self) -> Dict[str, Any]:
        """Get comprehensive schema information for the entire database"""
        schema_info = {
            "tables": {},
            "relationships": self.get_table_relationships()
        }
        
        tables = self.get_tables()
        for table in tables:
            schema_info["tables"][table] = {
                "columns": self.get_table_schema(table)
            }
            
        return schema_info

# Singleton instance for use throughout the application
def get_db_connection() -> DatabaseConnection:
    """Get or create the database connection singleton"""
    if "db_connection" not in st.session_state:
        st.session_state.db_connection = DatabaseConnection()
    
    return st.session_state.db_connection