#!/usr/bin/env python3
import os
from dotenv import load_dotenv

# Load environment variables before importing app
load_dotenv()

# Make sure environment variables are set
if not os.getenv('YOUTUBE_API_KEY'):
    print('Warning: YOUTUBE_API_KEY environment variable not set')
if not os.getenv('SECRET_KEY'):
    print('Warning: SECRET_KEY environment variable not set, using development key')

# Import application parts - we do this after loading environment variables
from youinsight import create_app, socketio

# Create the Flask application
app = create_app()

import eventlet
import eventlet.wsgi

if __name__ == '__main__':
    # Run the application with eventlet
    print('Starting YouInsight server with Eventlet...') 
    # Set Flask app debug mode explicitly if needed, e.g., app.debug = True, if not already set in create_app()
    # Note: Eventlet doesn't use Werkzeug's reloader, so debug=True from socketio.run is not directly applicable for auto-reloading.
    eventlet.wsgi.server(eventlet.listen(('0.0.0.0', 5001)), app)
