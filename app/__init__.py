from flask import Flask
from dotenv import load_dotenv
import os

def create_app():
    # Load environment variables from .env file
    load_dotenv()
    app = Flask(__name__)
    
    # Register blueprints
    from app.routes.main import main_bp
    app.register_blueprint(main_bp)
    
    return app
