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

from ..agents import AgentCoordinator

# Initialize agent coordinator
agent_coordinator = AgentCoordinator()

@main_bp.route('/translate_to_sql', methods=['POST'])
def translate_to_sql():
    """First phase: Generate SQL query from natural language prompt."""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'No message provided'}), 400
            
        # Generate SQL query
        result = agent_coordinator.generate_sql_query(data['message'])
        
        if "error" in result:
            return jsonify({'error': result["error"]}), 500
            
        if result.get("type") == "general":
            return jsonify({'message': result["message"]}), 200
            
        return jsonify({
            'query': result["query"],
            'visualization_type': result.get("visualization_type")
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
    """Second phase: Execute approved query and process results."""
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({'error': 'No query provided'}), 400
            
        # Execute the approved query
        query_result = db_service.execute_query(data['query'])
        if not query_result['success']:
            return jsonify({'error': query_result.get('error', 'Unknown error')}), 500
            
        # Process results with visualization and summaries
        visualization_type = data.get('visualization_type')
        process_result = agent_coordinator.process_query_results(
            data['query'],
            query_result,
            visualization_type,
            skip_column_detection=bool(visualization_type)  # Skip if we have a visualization type
        )
        
        if "error" in process_result:
            return jsonify({'error': process_result["error"]}), 500
            
        response = {
            'results': query_result['results'],
            'visualization': None,
            'summaries': process_result.get('summaries_html')
        }
        
        # Add visualization if available
        if process_result.get('visualization_html'):
            response['visualization'] = {
                'type': data.get('visualization_type'),
                'html': process_result['visualization_html']
            }
            
        return jsonify(response)
        
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
