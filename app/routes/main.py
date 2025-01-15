from flask import Blueprint, render_template, request, jsonify, current_app
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import requests
from ..services.database_service import DatabaseService

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

        payload = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 1000,
            "messages": [{
                "role": "user",
                "content": f"""Using the following database structure:

{db_structure}

Convert this message to a SQL query. The query should join tables when needed using common_id. Only return the SQL code, nothing else: {data['message']}"""
            }]
        }

        response = requests.post(claude_api_url, json=payload, headers=headers)
        response.raise_for_status()
        
        sql_query = response.json()['content'][0]['text']
        return jsonify({'query': sql_query})
        
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
            
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/db_info', methods=['GET'])
def get_db_info():
    """Get database structure information."""
    try:
        result = db_service.get_table_info()
        if not result['success']:
            return jsonify({'error': result.get('error', 'Unknown error')}), 500
            
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
