import pandas as pd
import sqlite3
import os

def analyze_file(file_path):
    """Analyze a single Excel file and print its headers."""
    try:
        df = pd.read_excel(file_path)
        print(f"\nHeaders for {os.path.basename(file_path)}:")
        for col in df.columns:
            print(f"- {col}")
        return list(df.columns)
    except Exception as e:
        print(f"Error reading {file_path}: {str(e)}")
        return []

def create_schema(db_path, headers):
    """Create database schema based on the headers."""
    try:
        with sqlite3.connect(db_path) as conn:
            # Drop existing tables
            conn.execute("DROP TABLE IF EXISTS common_fields")
            conn.execute("DROP TABLE IF EXISTS IW38")
            conn.execute("DROP TABLE IF EXISTS IW68")
            conn.execute("DROP TABLE IF EXISTS IW47")
            
            # Create tables with the correct headers
            iw38_headers, iw68_headers, iw47_headers = headers
            
            # Create common_fields table
            common_fields = set(iw38_headers) & set(iw68_headers) & set(iw47_headers)
            common_fields_sql = ", ".join([f"[{col}] TEXT" for col in common_fields])
            conn.execute(f"""
                CREATE TABLE common_fields (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_type TEXT,
                    {common_fields_sql}
                )
            """)
            
            # Create specific tables
            for table_name, cols in [
                ("IW38", iw38_headers),
                ("IW68", iw68_headers),
                ("IW47", iw47_headers)
            ]:
                specific_cols = set(cols) - common_fields
                specific_cols_sql = ", ".join([f"[{col}] TEXT" for col in specific_cols])
                conn.execute(f"""
                    CREATE TABLE {table_name} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        common_id INTEGER,
                        {specific_cols_sql},
                        FOREIGN KEY (common_id) REFERENCES common_fields(id)
                    )
                """)
            
            print("\nDatabase schema created successfully!")
            
    except Exception as e:
        print(f"Error creating schema: {str(e)}")

if __name__ == "__main__":
    temp_folder = "datalake/temp"
    db_path = "datalake/datalake.db"
    
    # Analyze each file
    headers = []
    for filename in ["iw38.xlsx", "iw68.xlsx", "iw47.xlsx"]:
        file_path = os.path.join(temp_folder, filename)
        file_headers = analyze_file(file_path)
        headers.append(file_headers)
    
    # Create schema
    if all(headers):
        create_schema(db_path, headers)
