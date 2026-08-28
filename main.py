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
    app.run(debug=True, port=5000)
