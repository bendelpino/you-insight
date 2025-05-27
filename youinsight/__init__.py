import os
from flask import Flask
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_caching import Cache

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
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///youinsight.db')
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
        
        # Create database tables
        db.create_all()
        
        # Register socket events
        from .socket_events import register_socket_events
        register_socket_events()
        
    return app
