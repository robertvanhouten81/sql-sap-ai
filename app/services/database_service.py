import sqlite3
import pandas as pd
import os
from typing import Dict, Any

class DatabaseService:
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    def get_db_connection(self):
        """Create a database connection."""
        return sqlite3.connect(self.db_path)

    def process_excel_file(self, file_path: str, file_type: str) -> Dict[str, Any]:
        """Process Excel file and insert data into database."""
        try:
            # Read Excel file
            df = pd.read_excel(file_path)
            
            # Convert all datetime columns to string format
            for column in df.select_dtypes(include=['datetime64[ns]']).columns:
                df[column] = df[column].dt.strftime('%Y-%m-%d %H:%M:%S')
            if df.empty:
                return {"success": False, "error": "No data found in file"}

            # Insert data into database
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Process each row
                for _, row in df.iterrows():
                    # First, insert common fields
                    common_query = """
                        INSERT INTO common_fields (
                            file_type, order_number, notification_number,
                            breakdown, functional_location
                        ) VALUES (?, ?, ?, ?, ?)
                    """
                    common_values = [
                        file_type,
                        row.get('Order', ''),
                        row.get('Notification', ''),
                        row.get('Breakdown', ''),
                        row.get('Functional Loc.', '')
                    ]
                    cursor.execute(common_query, common_values)
                    common_id = cursor.lastrowid
                    
                    # Then insert type-specific fields
                    if file_type == 'IW38':
                        specific_query = """
                            INSERT INTO IW38 (
                                common_id, created_on, basic_start_date,
                                equipment, description, plant_section,
                                total_actual_costs, order_type, main_workcenter,
                                maintenance_plan, actual_finish, cost_center,
                                basic_finish_date, breakdown_duration
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """
                        specific_values = [
                            common_id,
                            row.get('Created on', ''),
                            row.get('Bas. start date', ''),
                            row.get('Equipment', ''),
                            row.get('Description', ''),
                            row.get('Plant section', ''),
                            row.get('Total act.costs', ''),
                            row.get('Order Type', ''),
                            row.get('Main WorkCtr', ''),
                            row.get('MaintenancePlan', ''),
                            row.get('Actual finish', ''),
                            row.get('Cost Center', ''),
                            row.get('Basic fin. date', ''),
                            row.get('Breakdown dur.', '')
                        ]
                        cursor.execute(specific_query, specific_values)
                        
                    elif file_type == 'IW68':
                        specific_query = """
                            INSERT INTO IW68 (
                                common_id, code_group, problem_group_text,
                                damage_code, problem_code_text, item_text,
                                cause_code, cause_group_text, cause_text,
                                effect, reported_by
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """
                        specific_values = [
                            common_id,
                            row.get('Code group', ''),
                            row.get('Prob. grp. text', ''),
                            row.get('Damage Code', ''),
                            row.get('Prob. code text', ''),
                            row.get('Text', ''),
                            row.get('Cause code', ''),
                            row.get('Cause grp. text', ''),
                            row.get('Cause text', ''),
                            row.get('Effect', ''),
                            row.get('Reported by', '')
                        ]
                        cursor.execute(specific_query, specific_values)
                        
                    elif file_type == 'IW47':
                        specific_query = """
                            INSERT INTO IW47 (
                                common_id, created_on, created_by,
                                actual_finish_date, confirmation_number,
                                employees, personnel_number, confirmation_text,
                                planned_work, actual_work, system_status,
                                work_center, actual_start_time
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """
                        specific_values = [
                            common_id,
                            row.get('Created On', ''),
                            row.get('Created By', ''),
                            row.get('Act.finish date', ''),
                            row.get('Confirmation', ''),
                            row.get('Employee(s)', ''),
                            row.get('Personnel no.', ''),
                            row.get('Confirm. text', ''),
                            row.get('Work (planned)', ''),
                            row.get('Actual work', ''),
                            row.get('System Status', ''),
                            row.get('Work ctr (act.)', ''),
                            row.get('Act. start time', '')
                        ]
                        cursor.execute(specific_query, specific_values)
                
                conn.commit()
            
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    def execute_query(self, query: str) -> Dict[str, Any]:
        """Execute a SQL query and return the results."""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                
                # Get column names
                columns = [description[0] for description in cursor.description] if cursor.description else []
                
                # Fetch results
                results = cursor.fetchall()
                
                # Convert results to list of dictionaries
                formatted_results = []
                for row in results:
                    formatted_results.append(dict(zip(columns, row)))
                
                return {
                    "success": True,
                    "columns": columns,
                    "results": formatted_results
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_table_info(self) -> Dict[str, Any]:
        """Get information about database tables and their structure."""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get list of tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                
                info = {}
                for (table_name,) in tables:
                    # Get table columns
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = cursor.fetchall()
                    info[table_name] = {
                        "columns": [col[1] for col in columns],
                        "types": [col[2] for col in columns]
                    }
                
                return {"success": True, "tables": info}
                
        except Exception as e:
            return {"success": False, "error": str(e)}

    def initialize_database(self):
        """Initialize database with predefined structure based on Excel headers."""
        try:
            with self.get_db_connection() as conn:
                # Create common fields table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS common_fields (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_type TEXT,
                        order_number TEXT,
                        notification_number TEXT,
                        breakdown TEXT,
                        functional_location TEXT
                    )
                """)
                
                # Create IW38 Orders table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS IW38 (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        common_id INTEGER,
                        created_on TEXT,
                        basic_start_date TEXT,
                        equipment TEXT,
                        description TEXT,
                        plant_section TEXT,
                        total_actual_costs TEXT,
                        order_type TEXT,
                        main_workcenter TEXT,
                        maintenance_plan TEXT,
                        actual_finish TEXT,
                        cost_center TEXT,
                        basic_finish_date TEXT,
                        breakdown_duration TEXT,
                        FOREIGN KEY (common_id) REFERENCES common_fields(id)
                    )
                """)
                
                # Create IW68 Notification Items table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS IW68 (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        common_id INTEGER,
                        code_group TEXT,
                        problem_group_text TEXT,
                        damage_code TEXT,
                        problem_code_text TEXT,
                        item_text TEXT,
                        cause_code TEXT,
                        cause_group_text TEXT,
                        cause_text TEXT,
                        effect TEXT,
                        reported_by TEXT,
                        FOREIGN KEY (common_id) REFERENCES common_fields(id)
                    )
                """)
                
                # Create IW47 Confirmations table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS IW47 (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        common_id INTEGER,
                        created_on TEXT,
                        created_by TEXT,
                        actual_finish_date TEXT,
                        confirmation_number TEXT,
                        employees TEXT,
                        personnel_number TEXT,
                        confirmation_text TEXT,
                        planned_work TEXT,
                        actual_work TEXT,
                        system_status TEXT,
                        work_center TEXT,
                        actual_start_time TEXT,
                        FOREIGN KEY (common_id) REFERENCES common_fields(id)
                    )
                """)
                
            return {"success": True}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
