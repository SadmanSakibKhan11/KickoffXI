"""
Application Entry Point
========================
Starts the Flask development server.

Usage:
    python main.py
"""

import os
from dotenv import load_dotenv

# Ensure environment variables are loaded from project root .env before initializing app
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

from app import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = app.config.get('DEBUG', False)
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
