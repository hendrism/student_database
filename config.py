import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).parent.absolute()

class Config:
    """Enhanced security configuration for local-only deployment."""
    
    # Generate secure secret key if not provided
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    
    # Database configuration - ensure it's in instance folder
    INSTANCE_FOLDER = BASE_DIR / "instance"
    INSTANCE_FOLDER.mkdir(exist_ok=True)
    
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{INSTANCE_FOLDER}/student_database.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Security headers
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    }
    
    # Development settings
    DEBUG = os.environ.get("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"}
    TESTING = False
    
    # Session configuration for better security
    SESSION_COOKIE_SECURE = not DEBUG  # Only over HTTPS in production
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour
    
    # File upload limits (if you add file upload later)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Backup configuration
    BACKUP_FOLDER = BASE_DIR / "backups"
    BACKUP_FOLDER.mkdir(exist_ok=True)
    
    @staticmethod
    def init_app(app):
        """Initialize app with security settings."""
        # Add security headers to all responses
        @app.after_request
        def add_security_headers(response):
            for header, value in Config.SECURITY_HEADERS.items():
                response.headers[header] = value
            return response
        
        # Ensure instance folder permissions are restrictive (Mac/Unix)
        if hasattr(os, 'chmod'):
            try:
                os.chmod(Config.INSTANCE_FOLDER, 0o700)  # Owner read/write/execute only
                db_path = Config.INSTANCE_FOLDER / "student_database.db"
                if db_path.exists():
                    os.chmod(db_path, 0o600)  # Owner read/write only
            except OSError:
                pass

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True

class ProductionConfig(Config):
    """Production configuration for local deployment."""
    DEBUG = False
    
    # Additional production security
    SESSION_COOKIE_SECURE = True
    
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}