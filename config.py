"""
Flask Application Configuration
================================
Centralized configuration for KickoffXI.
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

    # Optional base URL for absolute links (e.g. password reset emails)
    APP_BASE_URL = os.getenv('APP_BASE_URL', '').rstrip('/')

    # Session security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # By default in development, cookies are sent over HTTP; in production SECURE is enabled.
    SESSION_COOKIE_SECURE = False

    # Firebase Session Cookie configuration
    AUTH_SESSION_COOKIE_NAME = os.getenv('AUTH_SESSION_COOKIE_NAME', 'kxi_session')
    # Clamped to maximum 14 days per Firebase Auth requirements (never exceed 14)
    AUTH_REMEMBER_DAYS = min(14, max(1, int(os.getenv('AUTH_REMEMBER_DAYS', '14') or 14)))
    AUTH_SHORT_SESSION_HOURS = max(1, int(os.getenv('AUTH_SHORT_SESSION_HOURS', '12') or 12))

    # Firebase Admin SDK & Identity Toolkit REST configuration
    FIREBASE_SERVICE_ACCOUNT_JSON = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    FIREBASE_WEB_API_KEY = os.getenv('FIREBASE_WEB_API_KEY')

    # Optional Firebase Emulator configuration
    FIRESTORE_EMULATOR_HOST = os.getenv('FIRESTORE_EMULATOR_HOST')
    FIREBASE_AUTH_EMULATOR_HOST = os.getenv('FIREBASE_AUTH_EMULATOR_HOST')

    # Gmail SMTP configuration (for password reset emails)
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').strip().lower() in ('true', '1', 'yes')
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '').strip()
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '').replace(' ', '').strip()
    MAIL_TIMEOUT_SECONDS = float(os.getenv('MAIL_TIMEOUT_SECONDS', '10.0'))


class DevelopmentConfig(Config):
    """
    Development environment configuration.
    """
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """
    Production environment configuration.
    """
    DEBUG = False
    SESSION_COOKIE_SECURE = True

    @classmethod
    def validate_production(cls):
        """
        Production guard: validates that production secrets are properly configured
        and that emulator environment variables are not set.
        """
        secret = os.environ.get('SECRET_KEY')
        if not secret or secret == 'dev-secret-key-change-in-production':
            raise RuntimeError(
                "SECRET_KEY must be set to a secure, random value in production. "
                "Do not use the default development key."
            )

        # Enforce no emulators in production
        firestore_emu = os.environ.get('FIRESTORE_EMULATOR_HOST')
        auth_emu = os.environ.get('FIREBASE_AUTH_EMULATOR_HOST')
        if firestore_emu or auth_emu:
            raise RuntimeError(
                "Firebase emulator environment variables (FIRESTORE_EMULATOR_HOST, FIREBASE_AUTH_EMULATOR_HOST) "
                "must NOT be configured in production."
            )

        # Enforce FIREBASE_WEB_API_KEY in production
        api_key = os.environ.get('FIREBASE_WEB_API_KEY')
        if not api_key or not api_key.strip():
            raise RuntimeError(
                "FIREBASE_WEB_API_KEY must be configured in production for user authentication and password reset."
            )


# Configuration dictionary — select by name
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
