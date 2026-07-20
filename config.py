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

# Base directory of the project (used for resolving relative paths)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


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


# Configuration dictionary — select by name
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
