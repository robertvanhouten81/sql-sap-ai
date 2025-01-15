import pandas as pd
import os
import sqlite3
from typing import Dict, List, Set

def analyze_excel_headers(file_path: str) -> Dict[str, List[str]]:
    """Analyze Excel file headers and return a dictionary of sheet names and their headers."""
    try:
        # Read all sheets
        excel_file = pd.ExcelFile(file_path)
        headers = {}
        
        for sheet_name in excel_file.sheet_names:
            # Read first row of each sheet
            df = pd.read_excel(excel_file, sheet_name=sheet_name, nrows=1)
            headers[sheet_name] = [str(col) for col in df.columns]
            
        return headers
    except Exception as e:
        print(f"Error analyzing {file_path}: {str(e)}")
        return {}

def find_common_headers(headers_dict: Dict[str, Dict[str, List[str]]]) -> Set[str]:
    """Find common headers across all Excel files."""
    all_headers = set()
    common_headers = set()
    first = True
    
    for file_headers in headers_dict.values():
        file_all_headers = set()
        for sheet_headers in file_headers.values():
            file_all_headers.update(sheet_headers)
        
        if first:
            common_headers = file_all_headers
            first = False
        else:
            common_headers &= file_all_headers
        all_headers.update(file_all_headers)
    
    return common_headers

def create_database_schema(db_path: str, headers_dict: Dict[str, Dict[str, List[str]]]):
    """Create SQLite database schema based on Excel headers."""
    common_headers = find_common_headers(headers_dict)
    
    # Create tables for each file type
    with sqlite3.connect(db_path) as conn:
        # Create a table for common fields that can be used for linking
        common_fields = ", ".join([f"[{header}] TEXT" for header in common_headers])
        if common_fields:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS common_fields (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_type TEXT,
                    {common_fields}
                )
            """)
        
        # Create specific tables for each file type
        for file_type, file_headers in headers_dict.items():
            all_headers = set()
            for sheet_headers in file_headers.values():
                all_headers.update(sheet_headers)
            
            # Remove common headers from specific tables to avoid duplication
            specific_headers = all_headers - common_headers
            
            # Create table with specific fields and link to common fields
            specific_fields = ", ".join([f"[{header}] TEXT" for header in specific_headers])
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {file_type} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    common_id INTEGER,
                    {specific_fields},
                    FOREIGN KEY (common_id) REFERENCES common_fields(id)
                )
            """)

def analyze_temp_folder(temp_folder: str, db_path: str):
    """Analyze all Excel files in temp folder and create database schema."""
    headers_dict = {}
    
    # Analyze all Excel files in temp folder
    for filename in os.listdir(temp_folder):
        if filename.endswith(('.xlsx', '.xls', '.xlsm')):
            file_path = os.path.join(temp_folder, filename)
            headers_dict[filename] = analyze_excel_headers(file_path)
    
    # Create database schema if files were found
    if headers_dict:
        create_database_schema(db_path, headers_dict)
        return headers_dict
    return None

if __name__ == "__main__":
    temp_folder = os.path.join("datalake", "temp")
    db_path = os.path.join("datalake", "datalake.db")
    analyze_temp_folder(temp_folder, db_path)
