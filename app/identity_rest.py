"""
Identity Toolkit REST API Wrapper
=================================
Handles server-side calls to the Google Identity Toolkit REST API:
- accounts:signInWithPassword
- accounts:resetPassword (verify oobCode and confirm new password)

Features:
- Configurable base URL (honors FIREBASE_AUTH_EMULATOR_HOST)
- Explicit request timeouts
- Standardized error-code mapping
- Strict privacy: passwords, API keys, and reset codes are NEVER logged
"""

import os
import logging
from typing import Dict, Any, Optional
import requests

logger = logging.getLogger(__name__)

DEFAULT_IDENTITY_TOOLKIT_URL = "https://identitytoolkit.googleapis.com/v1"
DEFAULT_TIMEOUT_SECONDS = 10.0


class IdentityApiError(Exception):
    """Base exception for Identity Toolkit REST failures."""
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class IdentityClient:
    """
    Client for calling Identity Toolkit REST endpoints.
    """
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT_SECONDS):
        self.api_key = api_key if api_key is not None else os.getenv('FIREBASE_WEB_API_KEY', '')
        self.timeout = timeout

        auth_emulator = os.getenv('FIREBASE_AUTH_EMULATOR_HOST')
        if base_url:
            self.base_url = base_url.rstrip('/')
        elif auth_emulator:
            if not auth_emulator.startswith('http'):
                auth_emulator = f"http://{auth_emulator}"
            self.base_url = f"{auth_emulator.rstrip('/')}/identitytoolkit.googleapis.com/v1"
        else:
            self.base_url = DEFAULT_IDENTITY_TOOLKIT_URL

    def _get_url(self, action: str) -> str:
        # Build URL with api_key query param
        key = self.api_key if self.api_key is not None else os.getenv('FIREBASE_WEB_API_KEY', '')
        return f"{self.base_url}/{action}?key={key}"

    def sign_in_with_password(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticate user with email and password via accounts:signInWithPassword.
        Returns response dict containing 'idToken', 'localId', 'email', 'expiresIn'.
        Raises IdentityApiError on failure.
        """
        if not self.api_key and not os.getenv('FIREBASE_AUTH_EMULATOR_HOST'):
            raise IdentityApiError(
                code='MISSING_API_KEY',
                message='Firebase Web API key is not configured. Set FIREBASE_WEB_API_KEY.',
                status_code=500
            )

        url = self._get_url("accounts:signInWithPassword")
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
        except requests.RequestException as e:
            logger.error(f"[ERROR] Identity Toolkit sign-in network failure: {e.__class__.__name__}")
            raise IdentityApiError('NETWORK_ERROR', 'Authentication service temporarily unavailable.', status_code=503)

        if resp.status_code == 200:
            return resp.json()

        # Parse error response
        error_code = 'UNKNOWN_ERROR'
        error_msg = 'Authentication failed.'
        try:
            err_data = resp.json().get('error', {})
            raw_msg = err_data.get('message', '')
            # Clean possible prefix like "EMAIL_NOT_FOUND : ..."
            code_candidate = raw_msg.split(':')[0].strip()

            if code_candidate in (
                'EMAIL_NOT_FOUND', 'INVALID_PASSWORD', 'USER_DISABLED',
                'INVALID_LOGIN_CREDENTIALS', 'INVALID_EMAIL'
            ):
                error_code = 'INVALID_CREDENTIALS'
                error_msg = 'Incorrect username/email or password.'
            elif code_candidate == 'TOO_MANY_ATTEMPTS_TRY_LATER':
                error_code = 'TOO_MANY_ATTEMPTS'
                error_msg = 'Too many attempts, please try again later.'
            else:
                error_code = code_candidate or 'INVALID_CREDENTIALS'
                error_msg = 'Incorrect username/email or password.'
        except Exception:
            pass

        raise IdentityApiError(code=error_code, message=error_msg, status_code=resp.status_code)

    def verify_password_reset_code(self, oob_code: str) -> Dict[str, Any]:
        """
        Verify that an out-of-band password reset code (oobCode) is valid.
        Returns response dict containing 'email' and 'requestType' if valid.
        Raises IdentityApiError on failure (e.g. EXPIRED_OOB_CODE, INVALID_OOB_CODE).
        """
        if not self.api_key and not os.getenv('FIREBASE_AUTH_EMULATOR_HOST'):
            raise IdentityApiError(
                code='MISSING_API_KEY',
                message='Firebase Web API key is not configured. Set FIREBASE_WEB_API_KEY.',
                status_code=500
            )

        url = self._get_url("accounts:resetPassword")
        payload = {"oobCode": oob_code}

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
        except requests.RequestException as e:
            logger.error(f"[ERROR] Identity Toolkit verify reset code network failure: {e.__class__.__name__}")
            raise IdentityApiError('NETWORK_ERROR', 'Authentication service temporarily unavailable.', status_code=503)

        if resp.status_code == 200:
            return resp.json()

        code = 'INVALID_OOB_CODE'
        msg = 'The password reset link is invalid or has already been used.'
        try:
            err_data = resp.json().get('error', {})
            raw_msg = err_data.get('message', '')
            code_candidate = raw_msg.split(':')[0].strip()

            if code_candidate == 'EXPIRED_OOB_CODE':
                code = 'EXPIRED_OOB_CODE'
                msg = 'This password reset link has expired. Please request a new one.'
            elif code_candidate == 'INVALID_OOB_CODE':
                code = 'INVALID_OOB_CODE'
                msg = 'This password reset link is invalid or has already been used. Please request a new one.'
            else:
                code = code_candidate
        except Exception:
            pass

        raise IdentityApiError(code=code, message=msg, status_code=resp.status_code)

    def confirm_password_reset(self, oob_code: str, new_password: str) -> Dict[str, Any]:
        """
        Confirm password reset with the oobCode and new password.
        Returns response dict on success.
        Raises IdentityApiError on failure.
        """
        if not self.api_key and not os.getenv('FIREBASE_AUTH_EMULATOR_HOST'):
            raise IdentityApiError(
                code='MISSING_API_KEY',
                message='Firebase Web API key is not configured. Set FIREBASE_WEB_API_KEY.',
                status_code=500
            )

        url = self._get_url("accounts:resetPassword")
        payload = {
            "oobCode": oob_code,
            "newPassword": new_password
        }

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
        except requests.RequestException as e:
            logger.error(f"[ERROR] Identity Toolkit confirm reset network failure: {e.__class__.__name__}")
            raise IdentityApiError('NETWORK_ERROR', 'Authentication service temporarily unavailable.', status_code=503)

        if resp.status_code == 200:
            return resp.json()

        code = 'INVALID_OOB_CODE'
        msg = 'Failed to reset password.'
        try:
            err_data = resp.json().get('error', {})
            raw_msg = err_data.get('message', '')
            code_candidate = raw_msg.split(':')[0].strip()

            if code_candidate == 'EXPIRED_OOB_CODE':
                code = 'EXPIRED_OOB_CODE'
                msg = 'This password reset link has expired. Please request a new one.'
            elif code_candidate == 'INVALID_OOB_CODE':
                code = 'INVALID_OOB_CODE'
                msg = 'This password reset link is invalid or has already been used. Please request a new one.'
            elif code_candidate == 'WEAK_PASSWORD':
                code = 'WEAK_PASSWORD'
                msg = 'Password is too weak. Please choose a stronger password.'
            else:
                code = code_candidate
        except Exception:
            pass

        raise IdentityApiError(code=code, message=msg, status_code=resp.status_code)

    def send_password_reset_email(self, email: str, continue_url: str = "https://kickoffxl.onrender.com/signin") -> Dict[str, Any]:
        """
        Request Firebase to generate and deliver a native password reset email.
        Calls accounts:sendOobCode with requestType='PASSWORD_RESET'.
        Returns response dict on success (e.g. {'email': 'user@example.com'}).
        Raises IdentityApiError on failure.
        """
        if not self.api_key and not os.getenv('FIREBASE_AUTH_EMULATOR_HOST'):
            raise IdentityApiError(
                code='MISSING_API_KEY',
                message='Firebase Web API key is not configured. Set FIREBASE_WEB_API_KEY.',
                status_code=500
            )

        url = self._get_url("accounts:sendOobCode")
        payload = {
            "requestType": "PASSWORD_RESET",
            "email": email,
            "continueUrl": continue_url
        }

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
        except requests.RequestException as e:
            logger.error(f"[ERROR] Identity Toolkit sendOobCode network failure: {e.__class__.__name__}")
            raise IdentityApiError('NETWORK_ERROR', 'Authentication service temporarily unavailable.', status_code=503)

        if resp.status_code == 200:
            return resp.json()

        # Parse error response
        error_code = 'UNKNOWN_ERROR'
        error_msg = 'Failed to send password reset email.'
        try:
            err_data = resp.json().get('error', {})
            raw_msg = err_data.get('message', '')
            code_candidate = raw_msg.split(':')[0].strip()

            if code_candidate == 'EMAIL_NOT_FOUND':
                error_code = 'EMAIL_NOT_FOUND'
                error_msg = 'No user found with this email address.'
            elif code_candidate == 'TOO_MANY_ATTEMPTS_TRY_LATER':
                error_code = 'TOO_MANY_ATTEMPTS'
                error_msg = 'Too many attempts, please try again later.'
            elif code_candidate == 'OPERATION_NOT_ALLOWED':
                error_code = 'OPERATION_NOT_ALLOWED'
                error_msg = 'Password reset is disabled for this project.'
            elif code_candidate == 'INVALID_EMAIL':
                error_code = 'INVALID_EMAIL'
                error_msg = 'Invalid email address.'
            elif code_candidate in ('API_KEY_INVALID', 'INVALID_KEY'):
                error_code = 'API_KEY_INVALID'
                error_msg = 'Invalid Firebase API key.'
            else:
                error_code = code_candidate or 'UNKNOWN_ERROR'
                error_msg = 'Failed to send password reset email.'
        except Exception:
            pass

        raise IdentityApiError(code=error_code, message=error_msg, status_code=resp.status_code)

