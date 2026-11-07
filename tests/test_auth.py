"""
Authentication and Session Tests
================================
Tests signup, login, session cookies, remember me, logout, forgot-password,
reset-password, and security headers.
"""

import pytest
from unittest.mock import patch, MagicMock
from flask import session
from firebase_admin import auth, exceptions as fb_exceptions

from app.user_store import validate_username, validate_document_id_rules, UsernameAlreadyTakenError
from app.identity_rest import IdentityApiError
from app.email_sender import send_password_reset_email


def test_username_validation():
    # Valid usernames
    assert validate_username("valid_user")[0] is True
    assert validate_username("user.name")[0] is True
    assert validate_username("user-123")[0] is True
    assert validate_username("abc")[0] is True

    # Invalid usernames for signups
    assert validate_username("")[0] is False
    assert validate_username("ab")[0] is False  # Too short (<3)
    assert validate_username("a" * 21)[0] is False  # Too long (>20)
    assert validate_username("user with spaces")[0] is False
    assert validate_username("user@name")[0] is False
    assert validate_username("user/name")[0] is False

    # Document ID rules
    assert validate_document_id_rules("seth rollins")[0] is True
    assert validate_document_id_rules("user/name")[0] is False
    assert validate_document_id_rules(".")[0] is False
    assert validate_document_id_rules("..")[0] is False
    assert validate_document_id_rules("__init__")[0] is False


def test_signup_validation_errors(client):
    # Empty fields
    res = client.post('/signup', data={})
    assert res.status_code == 400
    assert b"Username is required" in res.data
    assert b"Email is required" in res.data

    # Short password
    res = client.post('/signup', data={
        'username': 'validuser',
        'email': 'valid@example.com',
        'password': '123',
        'confirm_password': '123'
    })
    assert res.status_code == 400
    assert b"at least 6 characters" in res.data

    # Mismatched passwords
    res = client.post('/signup', data={
        'username': 'validuser',
        'email': 'valid@example.com',
        'password': 'password123',
        'confirm_password': 'mismatch123'
    })
    assert res.status_code == 400
    assert b"Passwords do not match" in res.data


@patch('app.auth_routes.IdentityClient')
def test_signup_success_and_cookie(mock_id_client_class, client, in_memory_user_store, mock_firebase_auth):
    mock_auth_user = MagicMock()
    mock_auth_user.uid = "test-uid-123"
    mock_firebase_auth.create_user.return_value = mock_auth_user
    mock_firebase_auth.create_session_cookie.return_value = "mock_session_cookie_signup"

    mock_id_client = MagicMock()
    mock_id_client_class.return_value = mock_id_client
    mock_id_client.sign_in_with_password.return_value = {
        'idToken': 'mock-id-token',
        'localId': 'test-uid-123'
    }

    res = client.post('/signup', data={
        'username': 'newuser',
        'email': 'newuser@example.com',
        'password': 'password123',
        'confirm_password': 'password123'
    })

    assert res.status_code == 302
    assert res.headers['Location'] == '/'

    # Verify user profile in store
    profile = in_memory_user_store.get_user_by_uid("test-uid-123")
    assert profile is not None
    assert profile['username'] == 'newuser'
    assert profile['email'] == 'newuser@example.com'

    # Check cookie attributes: signup auto-login must NOT be persistent (max_age is None)
    cookie_header = res.headers.get('Set-Cookie', '')
    assert 'kxi_session=mock_session_cookie_signup' in cookie_header
    assert 'HttpOnly' in cookie_header
    assert 'SameSite=Lax' in cookie_header
    assert 'Max-Age=' not in cookie_header


def test_signup_compensating_rollback_on_firestore_failure(client, in_memory_user_store, mock_firebase_auth):
    mock_auth_user = MagicMock()
    mock_auth_user.uid = "orphan-uid-999"
    mock_firebase_auth.create_user.return_value = mock_auth_user

    # Simulate transactional failure during username reservation
    with patch.object(in_memory_user_store, 'create_user_profile', side_effect=UsernameAlreadyTakenError("Taken")):
        res = client.post('/signup', data={
            'username': 'racename',
            'email': 'unique@example.com',
            'password': 'password123',
            'confirm_password': 'password123'
        })

        assert res.status_code == 400
        assert b"Username already exists" in res.data
        # Compensating delete was triggered
        mock_firebase_auth.delete_user.assert_called_once_with("orphan-uid-999")


@patch('app.auth_routes.IdentityClient')
def test_signin_by_email_and_remember_me(mock_id_client_class, client, in_memory_user_store, mock_firebase_auth):
    in_memory_user_store.create_user_profile("user-uid-1", "myuser", "myuser@example.com")

    mock_firebase_auth.verify_id_token.return_value = {'auth_time': 10000000000}
    mock_firebase_auth.create_session_cookie.return_value = "session_cookie_remember"

    mock_id_client = MagicMock()
    mock_id_client_class.return_value = mock_id_client
    mock_id_client.sign_in_with_password.return_value = {'idToken': 'token123'}

    with patch('time.time', return_value=10000000010):
        # 1. Login with Remember Me = True
        res = client.post('/signin', data={
            'identifier': 'myuser@example.com',
            'password': 'password123',
            'remember': 'true'
        })

        assert res.status_code == 302
        cookie_header = res.headers.get('Set-Cookie', '')
        assert 'kxi_session=session_cookie_remember' in cookie_header
        assert 'Max-Age=1209600' in cookie_header  # 14 days in seconds
        assert 'HttpOnly' in cookie_header

        # Clear session before part 2
        client.delete_cookie('kxi_session')

        # 2. Login with Remember Me = False
        mock_firebase_auth.create_session_cookie.return_value = "session_cookie_short"
        res_no_rem = client.post('/signin', data={
            'identifier': 'myuser@example.com',
            'password': 'password123'
        })
        cookie_header_short = res_no_rem.headers.get('Set-Cookie', '')
        assert 'kxi_session=session_cookie_short' in cookie_header_short
        assert 'Max-Age=' not in cookie_header_short  # Session cookie


@patch('app.auth_routes.IdentityClient')
def test_signin_by_username_resolution(mock_id_client_class, client, in_memory_user_store, mock_firebase_auth):
    in_memory_user_store.create_user_profile("uid-uname", "CoolPlayer", "cool@example.com")

    mock_firebase_auth.verify_id_token.return_value = {'auth_time': 10000000000}
    mock_firebase_auth.create_session_cookie.return_value = "session_cookie_cool"

    mock_id_client = MagicMock()
    mock_id_client_class.return_value = mock_id_client
    mock_id_client.sign_in_with_password.return_value = {'idToken': 'token_cool'}

    with patch('time.time', return_value=10000000010):
        res = client.post('/signin', data={
            'identifier': 'CoolPlayer',
            'password': 'password123'
        })

        assert res.status_code == 302
        mock_id_client.sign_in_with_password.assert_called_once_with('cool@example.com', 'password123')


@patch('app.auth_routes.IdentityClient')
def test_signin_generic_failure_anti_enumeration(mock_id_client_class, client, in_memory_user_store):
    mock_id_client = MagicMock()
    mock_id_client_class.return_value = mock_id_client
    mock_id_client.sign_in_with_password.side_effect = IdentityApiError('INVALID_CREDENTIALS', 'Incorrect username/email or password.')

    # Unknown username
    res1 = client.post('/signin', data={
        'identifier': 'nonexistent_user',
        'password': 'wrongpassword'
    })
    assert res1.status_code == 401
    assert b"Incorrect username/email or password." in res1.data

    # Unknown email
    res2 = client.post('/signin', data={
        'identifier': 'unknown@example.com',
        'password': 'wrongpassword'
    })
    assert res2.status_code == 401
    assert b"Incorrect username/email or password." in res2.data


def test_logout_clears_cookie(client):
    res = client.post('/logout')
    assert res.status_code == 302
    cookie_header = res.headers.get('Set-Cookie', '')
    assert 'kxi_session=;' in cookie_header or 'Expires=' in cookie_header or 'Max-Age=0' in cookie_header


def test_login_required_page_redirect_and_api_401(client, mock_firebase_auth):
    mock_firebase_auth.verify_session_cookie.side_effect = Exception("Invalid session")
    client.set_cookie('kxi_session', 'invalid_cookie')

    # Protected page redirect
    res_page = client.get('/profile')
    assert res_page.status_code == 302
    assert '/signin' in res_page.headers['Location']

    # Protected API 401 JSON
    res_api = client.get('/api/saved-squads')
    assert res_api.status_code == 401
    json_data = res_api.get_json()
    assert json_data['error'] == 'Login required.'
    assert json_data['login_required'] is True


@patch('app.auth_routes.send_password_reset_email')
def test_forgot_password_generic_confirmation_and_throttle(mock_send_email, client, in_memory_user_store, mock_firebase_auth):
    in_memory_user_store.create_user_profile("user-reset-uid", "resetuser", "reset@example.com")

    mock_user_rec = MagicMock()
    mock_user_rec.uid = "user-reset-uid"
    mock_user_rec.display_name = "resetuser"
    mock_firebase_auth.get_user_by_email.return_value = mock_user_rec
    mock_firebase_auth.generate_password_reset_link.return_value = "https://kickoffxi.firebaseapp.com/__/auth/action?mode=resetPassword&oobCode=oob12345"

    # 1. Registered email
    res1 = client.post('/forgot-password', data={'email': 'reset@example.com'})
    assert res1.status_code == 200
    assert b"If an account exists for this email" in res1.data
    mock_send_email.assert_called_once()

    # 2. Second request within 60s is throttled
    mock_send_email.reset_mock()
    res2 = client.post('/forgot-password', data={'email': 'reset@example.com'})
    assert res2.status_code == 200
    assert b"If an account exists for this email" in res2.data
    mock_send_email.assert_not_called()

    # 3. Unregistered email
    mock_firebase_auth.get_user_by_email.side_effect = fb_exceptions.NotFoundError("Not found")
    res3 = client.post('/forgot-password', data={'email': 'unknown@example.com'})
    assert res3.status_code == 200
    assert b"If an account exists for this email" in res3.data


@patch('app.auth_routes.IdentityClient')
def test_reset_password_page_states_and_headers(mock_id_client_class, client):
    mock_id_client = MagicMock()
    mock_id_client_class.return_value = mock_id_client

    # State A: Valid oobCode
    mock_id_client.verify_password_reset_code.return_value = {'email': 'user@example.com'}
    res_valid = client.get('/reset-password?oobCode=valid_code_123')
    assert res_valid.status_code == 200
    assert b"Set New Password" in res_valid.data
    assert res_valid.headers['Cache-Control'] == 'no-store, no-cache, must-revalidate, max-age=0'
    assert res_valid.headers['Referrer-Policy'] == 'no-referrer'

    # State B: Expired oobCode
    mock_id_client.verify_password_reset_code.side_effect = IdentityApiError('EXPIRED_OOB_CODE', 'This password reset link has expired.')
    res_expired = client.get('/reset-password?oobCode=expired_code')
    assert res_expired.status_code == 400
    assert b"expired" in res_expired.data
    assert res_expired.headers['Referrer-Policy'] == 'no-referrer'

    # State C: Confirm reset success
    mock_id_client.confirm_password_reset.return_value = {'email': 'user@example.com'}
    res_confirm = client.post('/reset-password', data={
        'oobCode': 'valid_code_123',
        'new_password': 'newsecretpassword123',
        'confirm_password': 'newsecretpassword123'
    })
    assert res_confirm.status_code == 302
    assert '/signin' in res_confirm.headers['Location']


@patch('smtplib.SMTP')
def test_reset_email_escaping(mock_smtp, app):
    with app.app_context():
        app.config['MAIL_USERNAME'] = 'mailer@example.com'
        app.config['MAIL_PASSWORD'] = 'password'

        malicious_username = '<script>alert("xss")</script>'
        reset_url = "http://localhost:5000/reset-password?oobCode=abc123xyz"

        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        send_password_reset_email("user@example.com", reset_url, malicious_username)

        send_args = mock_server.sendmail.call_args[0]
        raw_msg = send_args[2]

        assert '<script>' not in raw_msg
        assert '&lt;script&gt;' in raw_msg


@patch('smtplib.SMTP')
def test_send_password_reset_email_timeout_applied(mock_smtp, app):
    """Verify that SMTP client enforces the 10-second timeout."""
    with app.app_context():
        app.config['MAIL_USERNAME'] = 'mailer@example.com'
        app.config['MAIL_PASSWORD'] = 'password'
        app.config['MAIL_TIMEOUT_SECONDS'] = 10.0

        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        send_password_reset_email("user@example.com", "http://localhost/reset", "TestUser")

        # Verify SMTP was instantiated with 10.0s timeout
        mock_smtp.assert_called_once_with('smtp.gmail.com', 587, timeout=10.0)
        # Verify TLS socket timeout was also set
        mock_server.sock.settimeout.assert_called_with(10.0)


@patch('smtplib.SMTP')
def test_send_password_reset_email_timeout_raises_delivery_error(mock_smtp, app):
    """Verify that an SMTP socket timeout raises a clean EmailDeliveryError."""
    import socket
    from app.email_sender import EmailDeliveryError

    with app.app_context():
        app.config['MAIL_USERNAME'] = 'mailer@example.com'
        app.config['MAIL_PASSWORD'] = 'password'

        mock_smtp.side_effect = socket.timeout("Connection timed out")

        with pytest.raises(EmailDeliveryError) as exc_info:
            send_password_reset_email("user@example.com", "http://localhost/reset", "TestUser")

        assert "timed out" in str(exc_info.value).lower()


@patch('app.auth_routes.send_password_reset_email')
def test_forgot_password_email_delivery_failure_shows_safe_error(mock_send_email, client, in_memory_user_store, mock_firebase_auth):
    """Verify that email delivery failure returns a safe 500 error page without leaking sensitive data."""
    from app.email_sender import EmailDeliveryError

    in_memory_user_store.create_user_profile("user-reset-uid", "resetuser", "reset@example.com")
    mock_user_rec = MagicMock()
    mock_user_rec.uid = "user-reset-uid"
    mock_user_rec.display_name = "resetuser"
    mock_firebase_auth.get_user_by_email.return_value = mock_user_rec
    mock_firebase_auth.generate_password_reset_link.return_value = "https://kickoffxi.firebaseapp.com/__/auth/action?mode=resetPassword&oobCode=oob12345"

    mock_send_email.side_effect = EmailDeliveryError("Email delivery timed out. Please try again.")

    res = client.post('/forgot-password', data={'email': 'reset@example.com'})
    assert res.status_code == 500
    assert b"Unable to send password reset email at this time" in res.data
    # Ensure raw tokens or internal details are not exposed
    assert b"oob12345" not in res.data


def test_session_verification_cache_check_revoked_enforcement(app, mock_firebase_auth):
    """
    Concern 1: Verify that a session verified with check_revoked=False CANNOT bypass
    a subsequent check_revoked=True verification within the same request.
    """
    from app.session_auth import get_current_user_from_request

    mock_firebase_auth.verify_session_cookie.side_effect = [
        {'uid': 'uid-123', 'name': 'User123', 'email': 'u1@example.com'},  # first call: check_revoked=False succeeds
        auth.RevokedSessionCookieError('Session cookie has been revoked.')  # second call: check_revoked=True raises
    ]

    with app.test_request_context('/', headers={'Cookie': 'kxi_session=valid_test_cookie'}):
        # 1. First verification with check_revoked=False succeeds and caches
        user_unrevoked = get_current_user_from_request(check_revoked=False)
        assert user_unrevoked is not None
        assert user_unrevoked['uid'] == 'uid-123'
        assert mock_firebase_auth.verify_session_cookie.call_count == 1
        assert mock_firebase_auth.verify_session_cookie.call_args[1]['check_revoked'] is False

        # 2. Second verification with check_revoked=True MUST NOT reuse the cached result;
        # it must re-verify with check_revoked=True and detect revocation.
        user_revoked = get_current_user_from_request(check_revoked=True)
        assert user_revoked is None
        assert mock_firebase_auth.verify_session_cookie.call_count == 2
        assert mock_firebase_auth.verify_session_cookie.call_args[1]['check_revoked'] is True


def test_test_auth_shortcut_prohibited_outside_testing(app):
    """
    Concern 7: Ensure test mock user shortcut cannot be enabled when TESTING is False.
    """
    from app.session_auth import get_current_user_from_request

    with app.test_request_context('/'):
        # Force TESTING=False
        app.config['TESTING'] = False
        session['test_uid'] = 'attacker-forged-uid'

        user = get_current_user_from_request()
        assert user is None

        # Re-enable TESTING
        app.config['TESTING'] = True
        user_in_testing = get_current_user_from_request()
        assert user_in_testing is not None
        assert user_in_testing['uid'] == 'attacker-forged-uid'


def test_is_safe_url_strictness(app):
    """
    Concern 6: Validate open redirect defenses.
    """
    from app.session_auth import is_safe_url

    with app.test_request_context('http://localhost:5000/signin'):
        # Safe relative URLs
        assert is_safe_url('/match-simulator') is True
        assert is_safe_url('/profile') is True
        assert is_safe_url('/teams?sort=name') is True

        # Safe same-host absolute URL
        assert is_safe_url('http://localhost:5000/profile') is True

        # Unsafe protocol-relative / malformed bypasses
        assert is_safe_url('//evil.com') is False
        assert is_safe_url('///evil.com') is False
        assert is_safe_url('/\\evil.com') is False
        assert is_safe_url('\\evil.com') is False
        assert is_safe_url('http://evil.com') is False
        assert is_safe_url('https://evil.com/signin') is False
        assert is_safe_url('javascript:alert(1)') is False
        assert is_safe_url('/evil\n.com') is False
        assert is_safe_url('') is False


def test_emulator_split_brain_configuration_check(monkeypatch):
    """
    Concern 3: Ensure Firebase Auth and Firestore emulator configuration
    cannot accidentally connect to different environments.
    """
    from app.firebase_client import get_firebase_app, reset_firebase_client_for_testing

    reset_firebase_client_for_testing()

    # Case A: Only FIRESTORE_EMULATOR_HOST is set
    monkeypatch.setenv('FIRESTORE_EMULATOR_HOST', 'localhost:8080')
    monkeypatch.delenv('FIREBASE_AUTH_EMULATOR_HOST', raising=False)
    monkeypatch.delenv('FIREBASE_SERVICE_ACCOUNT_JSON', raising=False)
    monkeypatch.delenv('GOOGLE_APPLICATION_CREDENTIALS', raising=False)

    import pytest
    with pytest.raises(RuntimeError) as exc_a:
        get_firebase_app()
    assert "Mismatched Firebase emulator configuration" in str(exc_a.value)

    reset_firebase_client_for_testing()

    # Case B: Only FIREBASE_AUTH_EMULATOR_HOST is set
    monkeypatch.delenv('FIRESTORE_EMULATOR_HOST', raising=False)
    monkeypatch.setenv('FIREBASE_AUTH_EMULATOR_HOST', 'localhost:9099')

    with pytest.raises(RuntimeError) as exc_b:
        get_firebase_app()
    assert "Mismatched Firebase emulator configuration" in str(exc_b.value)

    reset_firebase_client_for_testing()


def test_production_validation_requires_firebase_web_api_key(monkeypatch):
    """
    Verify that ProductionConfig.validate_production() raises RuntimeError
    when FIREBASE_WEB_API_KEY is missing, empty, or whitespace.
    """
    import pytest
    from config import ProductionConfig

    monkeypatch.setenv('SECRET_KEY', 'a-valid-production-secret-key-32-chars-long')
    monkeypatch.delenv('FIRESTORE_EMULATOR_HOST', raising=False)
    monkeypatch.delenv('FIREBASE_AUTH_EMULATOR_HOST', raising=False)

    # 1. Missing variable raises RuntimeError
    monkeypatch.delenv('FIREBASE_WEB_API_KEY', raising=False)
    with pytest.raises(RuntimeError) as exc_missing:
        ProductionConfig.validate_production()
    assert "FIREBASE_WEB_API_KEY must be configured in production" in str(exc_missing.value)

    # 2. Empty or whitespace variable raises RuntimeError
    monkeypatch.setenv('FIREBASE_WEB_API_KEY', '   ')
    with pytest.raises(RuntimeError) as exc_empty:
        ProductionConfig.validate_production()
    assert "FIREBASE_WEB_API_KEY must be configured in production" in str(exc_empty.value)

    # 3. Present and valid variable succeeds
    monkeypatch.setenv('FIREBASE_WEB_API_KEY', 'AIzaSyValidProductionApiKey123')
    ProductionConfig.validate_production()
