from flask import Flask
from dotenv import load_dotenv
import os
import logging
from pythonjsonlogger import jsonlogger
import sys

def setup_logging():
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Create JSON formatter
    formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler
    file_handler = logging.FileHandler('app.log')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

def create_app():
    # Load environment variables from .env file
    load_dotenv()
    
    # Setup logging
    logger = setup_logging()
    
    app = Flask(__name__)
    
    # Register blueprints
    from app.routes.main import main_bp
    app.register_blueprint(main_bp)
    
    # Log application startup
    logger.info('Application started')
    
    return app
