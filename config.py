"""
Flask Application Configuration
================================
Centralized configuration for the World Cup 2026 Player Database.
Supports development and production environments.

Usage:
    from config import config
    app.config.from_object(config['development'])
"""

import os
from dotenv import load_dotenv

# Base directory of the project (used for resolving relative paths)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Load .env file from project root if present
dotenv_path = os.path.join(BASE_DIR, '.env')
load_dotenv(dotenv_path)


class Config:
    """
    Base configuration shared across all environments.
    """
    # Security key — override via environment variable in production
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Application metadata
    APP_NAME = 'KickoffXI'
    APP_DESCRIPTION = 'Player Database — Browse and search every player in the tournament.'
    DEFAULT_PLAYER_IMAGE = 'players/default.png'
    DEFAULT_FRAME_IMAGE = 'teams/default_frame.png'

    # Session security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Gmail SMTP configuration (for password reset OTP emails)
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').strip().lower() in ('true', '1', 'yes')
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '').strip()
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '').strip()


class DevelopmentConfig(Config):
    """
    Development environment configuration.
    """
    DEBUG = True


class ProductionConfig(Config):
    """
    Production environment configuration.
    """
    DEBUG = False
    SESSION_COOKIE_SECURE = True


# Configuration dictionary — select by name
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
