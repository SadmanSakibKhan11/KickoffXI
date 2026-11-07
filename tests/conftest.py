"""
Pytest Configuration and Test Fixtures
======================================
Provides test fixtures with in-memory stores and mocked external services
so the entire test suite runs offline without Firebase credentials or .env.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

# Ensure test environment
os.environ['FLASK_CONFIG'] = 'development'
os.environ['SECRET_KEY'] = 'test-secret-key-for-unit-testing'
os.environ['FIREBASE_WEB_API_KEY'] = 'test-mock-api-key'

from app import create_app
from app.user_store import InMemoryUserStore, set_user_store
from app.squad_store import InMemorySquadStore, set_squad_store


@pytest.fixture(autouse=True)
def in_memory_user_store():
    store = InMemoryUserStore()
    set_user_store(store)
    return store


@pytest.fixture(autouse=True)
def in_memory_squad_store():
    store = InMemorySquadStore()
    set_squad_store(store)
    return store


@pytest.fixture(autouse=True)
def mock_firebase_auth():
    """Auto-use fixture that provides an offline mock auth module."""
    mock_auth = MagicMock()
    mock_user = MagicMock()
    mock_user.uid = "mock-uid-default"
    mock_user.display_name = "MockUser"
    mock_auth.create_user.return_value = mock_user
    mock_auth.get_user_by_email.return_value = mock_user
    mock_auth.create_session_cookie.return_value = "mock_session_cookie_default"
    mock_auth.verify_session_cookie.return_value = {
        'uid': 'mock-uid-default',
        'sub': 'mock-uid-default',
        'name': 'MockUser',
        'email': 'mock@example.com'
    }
    mock_auth.verify_id_token.return_value = {
        'uid': 'mock-uid-default',
        'auth_time': 10000000000
    }
    mock_auth.generate_password_reset_link.return_value = "https://mock.firebase.app/__/auth/action?mode=resetPassword&oobCode=mock_oob_code"

    with patch('app.firebase_client.get_auth_module', return_value=mock_auth):
        with patch('app.auth_routes.get_auth_module', return_value=mock_auth):
            with patch('app.session_auth.get_auth_module', return_value=mock_auth):
                yield mock_auth


@pytest.fixture
def app():
    app = create_app('development')
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    return app


@pytest.fixture
def client(app):
    with app.test_client() as client:
        yield client
