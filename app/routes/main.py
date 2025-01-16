from flask import Blueprint, render_template, request, jsonify, current_app
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import requests
import glob
from flask import Blueprint, render_template, request, jsonify, current_app
from werkzeug.utils import secure_filename
from ..services.database_service import DatabaseService
import json

main_bp = Blueprint('main', __name__)

UPLOAD_FOLDER = 'datalake'
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'xlsm'}
DB_PATH = os.path.join(UPLOAD_FOLDER, 'datalake.db')

# Initialize database service
db_service = DatabaseService(DB_PATH)
db_service.initialize_database()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@main_bp.route('/')
def home():
    # Get list of uploaded files for each dropzone
    uploads = {}
    for dropzone in ['IW38', 'IW68', 'IW47']:
        folder_path = os.path.join(UPLOAD_FOLDER, dropzone)
        if os.path.exists(folder_path):
            files = []
            for file in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file)
                last_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                files.append({
                    'name': file,
                    'lastUpdated': last_modified.strftime('%Y-%m-%d %H:%M:%S')
                })
            uploads[dropzone] = files
    
    # Get database structure information
    db_info = db_service.get_table_info()
    
    return render_template('index.html', uploads=uploads, db_info=db_info.get('tables', {}))

def generate_visualization_html(data, viz_config):
    """Generate HTML for visualization using Plotly."""
    import plotly.graph_objects as go
    import json
    
    # Convert SQL results to Plotly format
    if not data:
        return "<p>No data available for visualization</p>"
        
    columns = list(data[0].keys())
    if len(columns) < 2:
        return "<p>Need at least two columns for visualization</p>"
    
    # Get x and y columns from visualization config
    x_column = viz_config.get('columns', {}).get('x', columns[0])
    y_column = viz_config.get('columns', {}).get('y', columns[1])
    
    # Validate columns exist in data with detailed error message
    missing_columns = []
    
    # Helper functions for column name normalization and matching
    def normalize_column_name(col):
        # Remove table prefixes, quotes, and normalize case
        col = col.split('.')[-1] if '.' in col else col
        col = col.strip('"\'`[]')
        return col.lower()
    
    def find_matching_column(target, available_columns):
        target_norm = normalize_column_name(target)
        
        # Direct match
        if target in available_columns:
            return target
            
        # Try normalized match
        for col in available_columns:
            if normalize_column_name(col) == target_norm:
                return col
                
        # Try matching aggregated columns
        if 'count' in target_norm or 'sum' in target_norm or 'avg' in target_norm:
            for col in available_columns:
                col_norm = normalize_column_name(col)
                # Match based on the result part of aggregation
                if col_norm == target_norm.split('as')[-1].strip():
                    return col
        
        return None
    
    # Find matching columns
    x_col_match = find_matching_column(x_column, columns)
    y_col_match = find_matching_column(y_column, columns)
    
    if not x_col_match:
        missing_columns.append(f"x-axis column '{x_column}'")
    if not y_col_match:
        missing_columns.append(f"y-axis column '{y_column}'")
        
    # Update column names to use matched versions
    if x_col_match:
        x_column = x_col_match
    if y_col_match:
        y_column = y_col_match
    
    if missing_columns:
        # Try to find alternative columns that could work for visualization
        numeric_columns = []
        categorical_columns = []
        
        # Analyze first row to determine column types
        first_row = data[0]
        for col in columns:
            try:
                # Try to convert to float to identify numeric columns
                if first_row[col] is not None:
                    float(str(first_row[col]).replace(',', ''))
                    numeric_columns.append(col)
            except ValueError:
                categorical_columns.append(col)
        
        if categorical_columns and numeric_columns:
            # Use the first available categorical and numeric columns
            x_column = categorical_columns[0]
            y_column = numeric_columns[0]
        else:
            error_html = f"""
            <div class="visualization-error">
                <h4>Column Selection Error</h4>
                <p>Could not find appropriate columns for visualization.</p>
                <p>Available columns in results:</p>
                <ul>
                    {' '.join(f'<li>{col}</li>' for col in columns)}
                </ul>
                <p>Please modify the query to include both categorical and numeric columns.</p>
            </div>
            """
            return error_html

    # Extract data ensuring consistent format
    x_data = []
    y_data = []
    
    for row in data:
        # Handle x-axis data (categorical)
        x_value = str(row[x_column]) if row[x_column] is not None else ''
        x_data.append(x_value)
        
        # Handle y-axis data (numeric)
        try:
            y_value = str(row[y_column]).replace(',', '') if row[y_column] is not None else '0'
            y_data.append(float(y_value))
        except (ValueError, TypeError):
            y_data.append(0)
    
    # Create figure based on visualization type
    chart_type = viz_config.get('type', 'bar')
    
    if chart_type == 'pie':
        fig = go.Figure(data=[go.Pie(
            labels=x_data,
            values=y_data
        )])
    elif chart_type == 'bar':
        fig = go.Figure(data=[go.Bar(
            x=x_data,
            y=y_data
        )])
    elif chart_type == 'line':
        fig = go.Figure(data=[go.Scatter(
            x=x_data,
            y=y_data,
            mode='lines+markers'
        )])
    elif chart_type == 'table':
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=[x_column, y_column],
                fill_color='rgba(102, 153, 204, 0.5)',
                align='left',
                font=dict(color='white')
            ),
            cells=dict(
                values=[x_data, y_data],
                fill_color='rgba(102, 153, 204, 0.1)',
                align='left',
                font=dict(color='white')
            )
        )])
        # Adjust layout for table
        fig.update_layout(
            margin=dict(t=0, l=0, r=0, b=0),
            height=min(400, len(x_data) * 30 + 40)  # Dynamic height based on rows
        )
    else:
        return "<p>Unsupported visualization type</p>"
    
    # Update layout for non-table visualizations
    if chart_type != 'table':
        fig.update_layout(
            margin=dict(t=30, l=30, r=30, b=30),
            paper_bgcolor='rgba(102, 153, 204, 0.1)',
            plot_bgcolor='rgba(102, 153, 204, 0.1)',
            font=dict(color='#FFFFFF'),
            showlegend=True,
            height=400
        )
    
    # Generate HTML with explicit Plotly CDN
    html = fig.to_html(
        full_html=True,
        include_plotlyjs='https://cdn.plot.ly/plotly-latest.min.js',
        config={'responsive': True, 'displayModeBar': True}
    )
    
    # Add required meta tags and viewport settings
    html = html.replace('<head>', '''<head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    ''')
    
    # Add debug logging
    print("Generated visualization HTML:", html[:500] + "...")  # Print first 500 chars for debugging
    
    return html

def extract_visualization_types(message):
    """Extract words starting with @ from the message."""
    import re
    return re.findall(r'@\w+', message)

@main_bp.route('/translate_to_sql', methods=['POST'])
def translate_to_sql():
    """Translate a natural language message to SQL using Claude API."""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'No message provided'}), 400
            
        # Call Claude API to translate message to SQL
        claude_api_url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": os.environ.get('CLAUDE_API_KEY'),
            "anthropic-version": "2023-06-01"
        }
        
        db_structure = """
Database Structure:
CREATE TABLE common_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_type TEXT,
    order_number TEXT,
    notification_number TEXT,
    breakdown TEXT,
    functional_location TEXT
);

CREATE TABLE IW38 (
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
);

CREATE TABLE IW68 (
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
);

CREATE TABLE IW47 (
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
);"""

        # Extract visualization type from message
        viz_types = extract_visualization_types(data['message'])
        viz_type = None
        if viz_types:
            viz_type = viz_types[0].replace('@', '')  # Get first visualization type
            # Remove visualization type from message
            message = data['message'].replace(viz_types[0], '').strip()
        else:
            message = data['message']

        # First API call to get SQL query
        payload = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 1000,
            "messages": [{
                "role": "user",
                "content": f"""Using the following database structure:

                {db_structure}

                Convert this message to a SQL query. The query should:
                1. Join tables when needed using common_id
                2. Cast numeric columns to FLOAT when they're used in calculations or aggregations:
                - total_actual_costs should be CAST(total_actual_costs AS FLOAT)
                - breakdown_duration should be CAST(breakdown_duration AS FLOAT)
                - Any COUNT, SUM, or AVG operations should be explicit
                3. Use appropriate aliases for computed columns

                Only return the SQL code, nothing else: {message}"""
                            }]
                        }

        response = requests.post(claude_api_url, json=payload, headers=headers)
        response.raise_for_status()
        sql_query = response.json()['content'][0]['text']

        # If visualization type is specified, make second API call to determine required columns
        viz_config = None
        if viz_type in ['pie', 'line', 'bar', 'table']:
            payload = {
                "model": "claude-3-haiku-20240307",
                "max_tokens": 1000,
                "messages": [{
                    "role": "user",
                    "content": f"""Given this SQL query and database structure:

                    SQL Query:
                    {sql_query}

                    Database Structure:
                    {db_structure}

                    For a {viz_type} visualization, I need you to:

                    1. First, analyze the SQL query to identify which columns will be in the result set
                    2. Then, select TWO columns from these results:
                    - For x-axis/labels: A categorical column (text-based data like names, types, or categories)
                    - For y-axis/values: A numerical column that can be aggregated (costs, durations, counts)

                    IMPORTANT:
                    - Only select columns that will actually appear in the query results
                    - The columns must be exactly as they appear in the query (including table prefixes if used)
                    - For numerical columns:
                    * Must be explicitly cast as numbers (e.g., CAST(column AS FLOAT))
                    * Must be used in aggregations (SUM, COUNT, AVG)
                    * Must use the exact alias if one is defined in the query
                    - For categorical columns:
                    * Must be a text column or a column aliased as a label
                    * Must exist in the SELECT statement
                    - Ensure the columns make logical sense for a {viz_type} chart

                    Return only a JSON object with this exact format:
                    {{"x": "column_name", "y": "column_name"}}

                    Do not include any explanation or additional text."""
                                    }]
                                }

            # Try up to 5 times to get valid column configuration
            max_attempts = 5
            attempts = 0
            error_responses = []
            
            while attempts < max_attempts:
                try:
                    viz_response = requests.post(claude_api_url, json=payload, headers=headers)
                    viz_response.raise_for_status()
                    response_text = viz_response.json()['content'][0]['text']
                    
                    try:
                        columns = json.loads(response_text)
                        # Validate response format
                        if (isinstance(columns, dict) and 
                            'x' in columns and 
                            'y' in columns and 
                            isinstance(columns['x'], str) and 
                            isinstance(columns['y'], str)):
                            
                            viz_config = {
                                "type": viz_type,
                                "columns": columns
                            }
                            return jsonify({
                                'query': sql_query,
                                'visualization': viz_config
                            })
                    except json.JSONDecodeError:
                        pass
                    
                    # If we get here, the response wasn't valid
                    error_responses.append(f"Attempt {attempts + 1}: {response_text}")
                    attempts += 1
                    
                    # Modify the prompt to be more explicit for the next attempt
                    payload['messages'][0]['content'] = f"""Given this SQL query and database structure:

                        SQL Query:
                        {sql_query}

                        Database Structure:
                        {db_structure}

                        STRICT REQUIREMENTS for {viz_type} visualization:

                        1. First, list out ALL columns that will be in the query results by analyzing the SELECT statement
                        2. From these columns ONLY, select:
                        - For x-axis/labels: A categorical column (text data)
                        - For y-axis/values: A numerical column (must be a number or numeric aggregate)

                        Rules:
                        - Columns MUST exist in the SELECT statement results
                        - Column names must match EXACTLY as they appear in the final SELECT statement
                        - Do NOT include table prefixes unless they are explicitly part of a column alias
                        - The y-axis column MUST be numeric (check if it's used in SUM, COUNT, AVG, or other numeric operations)
                        - Do not suggest columns from tables unless they appear in the query joins

                        Return ONLY a JSON object:
                        {{"x": "column_name", "y": "column_name"}}

                        No other text allowed."""
                                        
                except Exception as e:
                    error_responses.append(f"Attempt {attempts + 1}: API error - {str(e)}")
                    attempts += 1
            
            # If we get here, all attempts failed, let's execute the query and try to determine columns from results
            result = db_service.execute_query(sql_query)
            if not result['success']:
                return jsonify({
                    'error': f"Query execution failed: {result.get('error', 'Unknown error')}",
                    'attempts': error_responses,
                    'query': sql_query
                }), 500

            # Get actual columns from query results
            if result['results']:
                available_columns = list(result['results'][0].keys())
                
                # Try to find appropriate columns for visualization
                numeric_columns = []
                categorical_columns = []
                
                # Analyze first row to determine column types
                first_row = result['results'][0]
                for col in available_columns:
                    try:
                        # Try to convert to float to identify numeric columns
                        if first_row[col] is not None:
                            float(str(first_row[col]).replace(',', ''))
                            numeric_columns.append(col)
                    except ValueError:
                        categorical_columns.append(col)
                
                if categorical_columns and numeric_columns:
                    # Select first categorical column for x and first numeric column for y
                    viz_config = {
                        "type": viz_type,
                        "columns": {
                            "x": categorical_columns[0],
                            "y": numeric_columns[0]
                        }
                    }
                    return jsonify({
                        'query': sql_query,
                        'visualization': viz_config
                    })
            
            # If we still can't determine columns, return error
            return jsonify({
                'error': 'Could not determine appropriate columns for visualization',
                'attempts': error_responses,
                'query': sql_query
            }), 500

        return jsonify({
            'query': sql_query,
            'visualization': None
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/upload/<dropzone_type>', methods=['POST', 'OPTIONS'])
def upload_file(dropzone_type):
    if request.method == 'OPTIONS':
        response = current_app.make_default_options_response()
        response.headers['Access-Control-Allow-Methods'] = 'POST'
        response.headers['Access-Control-Allow-Headers'] = 'content-type'
        return response

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    current_app.logger.info(f'Received file: {file.filename} for {dropzone_type}')
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        try:
            # Create folder if it doesn't exist
            folder_path = os.path.join(UPLOAD_FOLDER, dropzone_type)
            os.makedirs(folder_path, exist_ok=True)
            
            # Save file with timestamp and secure filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{secure_filename(file.filename)}"
            file_path = os.path.join(folder_path, filename)
            file.save(file_path)
            
            # Process file and update database
            result = db_service.process_excel_file(file_path, dropzone_type)
            
            if not result['success']:
                return jsonify({
                    'error': f"Database error: {result.get('error', 'Unknown error')}"
                }), 500
            
            return jsonify({
                'success': True,
                'filename': filename,
                'lastUpdated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'File type not allowed'}), 400

@main_bp.route('/execute_query', methods=['POST'])
def execute_sql_query():
    """Execute a SQL query and return results."""
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({'error': 'No query provided'}), 400
            
        result = db_service.execute_query(data['query'])
        if not result['success']:
            return jsonify({'error': result.get('error', 'Unknown error')}), 500
        
        # Check if visualization is requested
        if data.get('visualization'):
            viz_html = generate_visualization_html(result['results'], data['visualization'])
            result['visualization_html'] = viz_html
            
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# @main_bp.route('/test_visualization')
# def test_visualization():
#     """Test route to verify visualization generation."""
#     # Sample data matching your example
#     data = [
#         {"order_type": "PM01", "order_count": 150, "order_percentage": 60}
            
#         return jsonify(result)
        
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500

@main_bp.route('/get_oldest_file', methods=['GET'])
def get_oldest_file():
    """Get information about the oldest file in the datalake."""
    try:
        oldest_file = None
        oldest_time = None
        folder_types = ['IW38', 'IW47', 'IW68']
        
        for folder in folder_types:
            folder_path = os.path.join(UPLOAD_FOLDER, folder)
            if os.path.exists(folder_path):
                files = glob.glob(os.path.join(folder_path, '*.xlsx'))
                for file in files:
                    mod_time = os.path.getmtime(file)
                    if oldest_time is None or mod_time < oldest_time:
                        oldest_time = mod_time
                        oldest_file = {
                            'name': os.path.basename(file),
                            'type': folder,
                            'last_modified': datetime.fromtimestamp(mod_time).strftime('%Y-%m-%d %H:%M:%S'),
                            'days_old': (datetime.now() - datetime.fromtimestamp(mod_time)).days
                        }
        
        if oldest_file:
            return jsonify(oldest_file)
        return jsonify({'error': 'No files found'}), 404
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/refresh_sap_data', methods=['POST'])
def refresh_sap_data():
    """Endpoint to trigger SAP data refresh."""
    try:
        # This is a placeholder. In a real implementation, 
        # you would add the logic to refresh SAP data here.
        return jsonify({
            'message': 'SAP data refresh triggered successfully',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
