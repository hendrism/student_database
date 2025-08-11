"""Flask application entry point for the Student Database app."""

import os
import logging
from datetime import datetime
from pathlib import Path

from flask import Flask, request, session, g
from flask_migrate import Migrate

from routes import routes_bp
from models import db
from config import config

def create_app(config_name=None):
    """Application factory pattern for better organization."""
    
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__, instance_relative_config=True)
    
    # Load configuration
    app.config.from_object(config.get(config_name, config['default']))
    config[config_name].init_app(app)
    
    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)
    
    # Register blueprints
    app.register_blueprint(routes_bp)
    
    # Setup logging for production
    if not app.debug:
        setup_logging(app)
    
    # Add security middleware
    setup_security_middleware(app)
    
    # Error handlers
    setup_error_handlers(app)
    
    # Create database tables and instance folder
    with app.app_context():
        db.create_all()
    
    return app

def setup_logging(app):
    """Configure logging for production use."""
    log_dir = Path(app.instance_path) / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    # Restrict log file permissions
    log_file = log_dir / 'app.log'
    
    # Configure file handler
    handler = logging.FileHandler(log_file)
    handler.setLevel(logging.INFO)
    
    # Format logs
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    )
    handler.setFormatter(formatter)
    
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)
    
    # Restrict log file permissions (Mac/Unix)
    if hasattr(os, 'chmod') and log_file.exists():
        os.chmod(log_file, 0o600)

def setup_security_middleware(app):
    """Add security middleware."""
    
    @app.before_request
    def security_checks():
        """Perform security checks before each request."""
        # Ensure session is fresh (extend timeout on activity)
        session.permanent = True
        
        # Log sensitive operations
        if request.method in ['POST', 'PUT', 'DELETE']:
            app.logger.info(f"Sensitive operation: {request.method} {request.path}")

def setup_error_handlers(app):
    """Setup comprehensive error handling."""
    
    @app.errorhandler(404)
    def not_found(error):
        app.logger.warning(f"404 error for {request.method} {request.path}")
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"500 error for {request.method} {request.path}: {str(error)}")
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(413)
    def file_too_large(error):
        app.logger.warning(f"File too large: {request.path}")
        return "File too large. Maximum size is 16MB.", 413

# Create app instance
app = create_app()

if __name__ == '__main__':
    # Only run in development
    if app.config.get('DEBUG', False):
        app.run(host='127.0.0.1', port=5000, debug=True)
    else:
        print("For production use, please use a proper WSGI server like gunicorn")
        print("Example: gunicorn -w 1 -b 127.0.0.1:5000 app:app")