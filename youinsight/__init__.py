import os
import time
from flask import Flask
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_caching import Cache
from sqlalchemy import exc

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
# Use threading mode instead of eventlet to be compatible with Python 3.12
socketio = SocketIO(async_mode='eventlet')
login_manager = LoginManager()
cache = Cache()

def create_app(testing=False):
    """Application factory function."""
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    
    # Load config
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    
    # PostgreSQL configuration for Supabase
    # Format: 'postgresql://[user]:[password]@[host]:[port]/[dbname]'
    # Example: postgresql://postgres:password@db.xyzcompany.supabase.co:5432/postgres
    # Note: Use DATABASE_URL for compatibility with existing code
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/youinsight')
    
    # Configure SQLAlchemy connection pooling for PostgreSQL
    # These settings are optimized for Supabase connections
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 5,  # Default number of connections to keep open
        'max_overflow': 10,  # Max extra connections when pool is fully used
        'pool_timeout': 30,  # Seconds to wait before giving up on getting a connection
        'pool_recycle': 1800,  # Recycle connections after 30 minutes (prevents stale connections)
    }
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize cache
    cache.init_app(app, config={
        'CACHE_TYPE': 'simple',
        'CACHE_DEFAULT_TIMEOUT': 3600  # 1 hour
    })
    
    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app, cors_allowed_origins="*")
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    
    with app.app_context():
        # Import models
        from . import models
        
        # Import and register blueprints
        from .routes import main
        app.register_blueprint(main)
        
        # Create database tables with retry logic for connection issues
        max_retries = 5
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                db.create_all()
                break
            except exc.OperationalError as e:
                if attempt < max_retries - 1:
                    print(f"Database connection failed. Retrying in {retry_delay} seconds... ({attempt+1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                else:
                    print(f"Failed to connect to database after {max_retries} attempts: {e}")
                    # In production, consider proper error logging here
                    # Don't raise here to allow app to start without DB in emergency situations
        
        # Register socket events
        from .socket_events import register_socket_events
        register_socket_events()
        
    return app
