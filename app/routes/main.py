from flask import Blueprint, render_template, request, jsonify, current_app
from werkzeug.utils import secure_filename
from datetime import datetime
import os
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
