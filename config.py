"""
Configuration module for the Real-Time Poll Application.

This module handles all environment-based configuration settings,
supporting both development and production environments.
"""

import os
from datetime import timedelta


class Config:
    """Base configuration class with common settings."""

    # Flask Settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = False
    TESTING = False

    # Database Configuration
    # SQLite for development, PostgreSQL for production
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///polls.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # SocketIO Configuration
    SOCKETIO_MESSAGE_QUEUE = os.environ.get('SOCKETIO_MESSAGE_QUEUE', None)
    SOCKETIO_ASYNC_MODE = 'gevent'
    SOCKETIO_CORS_ALLOWED_ORIGINS = "*"
    SOCKETIO_PING_TIMEOUT = 60
    SOCKETIO_PING_INTERVAL = 25

    # Rate Limiting Configuration
    RATE_LIMIT_ENABLED = True
    RATE_LIMIT_REQUESTS = 10  # Maximum requests per window
    RATE_LIMIT_WINDOW = 60  # Time window in seconds

    # Poll Configuration
    POLL_CODE_LENGTH = 8
    MIN_OPTIONS = 2
    MAX_OPTIONS = 10
    MAX_QUESTION_LENGTH = 500
    MAX_OPTION_LENGTH = 200

    # Application URLs
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')


class DevelopmentConfig(Config):
    """Development-specific configuration."""

    DEBUG = True
    SQLALCHEMY_ECHO = False  # Set to True for SQL debugging


class ProductionConfig(Config):
    """Production-specific configuration."""

    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    """Testing-specific configuration."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# Configuration dictionary for easy environment switching
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config():
    """
    Get the appropriate configuration based on environment.

    Returns:
        Config: The configuration object for the current environment.
    """
    env = os.environ.get('FLASK_ENV', 'development')
    return config_by_name.get(env, DevelopmentConfig)
