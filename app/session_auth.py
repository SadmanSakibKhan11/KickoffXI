"""
Session Authentication & Cookie Management
==========================================
Implements Firebase Auth session cookies per Decision D4:
- Cookie Name: Config-driven (default: 'kxi_session')
- Flags: HttpOnly=True, SameSite='Lax', Secure in production
- Remember Me = True:
    * Server-side expires_in = 14 days (Firebase maximum)
    * Browser cookie Max-Age = 14 days (1,209,600 seconds)
- Remember Me = False (and signup auto-login):
    * Server-side expires_in = Config-driven (default: 12 hours)
    * Browser cookie has NO Max-Age / Expires (session cookie)
- Verification:
    * auth.verify_session_cookie()
    * check_revoked=True on state-changing/sensitive operations
    * check_revoked=False on standard page loads
    * Clears cookie and marks user logged out on any verification failure
"""

import logging
from datetime import timedelta
from functools import wraps
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse

from flask import request, current_app, g, session, redirect, url_for, jsonify
from firebase_admin import auth
from app.firebase_client import get_auth_module
from app.user_store import get_user_store

logger = logging.getLogger(__name__)


def is_safe_url(target: str) -> bool:
    """
    Strict security check to prevent open redirect vulnerabilities.
    Blocks control chars, backslashes, protocol-relative prefixes (//, ///, /\\),
    and enforces exact host matching for absolute URLs.
    """
    if not target or not isinstance(target, str):
        return False

    # Block control characters and whitespace
    if any(c in target for c in ('\r', '\n', '\t', ' ')):
        return False

    # Disallow backslashes (normalized to forward slashes by some browsers)
    if '\\' in target:
        return False

    # Disallow protocol-relative URLs
    if target.startswith('//') or target.startswith('///'):
        return False

    ref_url = urlparse(request.host_url)
    test_url = urlparse(target)

    # Relative paths: must start with / and not have a scheme or netloc
    if not test_url.scheme and not test_url.netloc:
        return target.startswith('/')

    # Absolute URLs: scheme and netloc must match current host exactly
    return test_url.scheme in ('http', 'https') and test_url.netloc == ref_url.netloc


def get_cookie_name() -> str:
    """Return configured session cookie name."""
    return current_app.config.get('AUTH_SESSION_COOKIE_NAME', 'kxi_session')


def get_session_durations(remember: bool = False) -> Tuple[timedelta, Optional[int]]:
    """
    Calculate server-side expires_in and browser Max-Age.
    Returns (server_expires_in: timedelta, browser_max_age: Optional[int]).
    """
    if remember:
        days = current_app.config.get('AUTH_REMEMBER_DAYS', 14)
        # Clamped to maximum 14 days per Firebase requirements
        days = min(14, max(1, days))
        server_delta = timedelta(days=days)
        browser_max_age = int(server_delta.total_seconds())
    else:
        hours = current_app.config.get('AUTH_SHORT_SESSION_HOURS', 12)
        hours = max(1, hours)
        server_delta = timedelta(hours=hours)
        browser_max_age = None  # Browser session cookie

    return server_delta, browser_max_age


def create_firebase_session_cookie(id_token: str, remember: bool = False) -> Tuple[str, Optional[int]]:
    """
    Create a Firebase session cookie from an authenticated user's ID token.
    Returns (session_cookie: str, browser_max_age: Optional[int]).
    """
    auth_mod = get_auth_module()
    server_delta, browser_max_age = get_session_durations(remember)

    session_cookie = auth_mod.create_session_cookie(id_token, expires_in=server_delta)
    return session_cookie, browser_max_age


def set_auth_cookie(response, session_cookie: str, browser_max_age: Optional[int] = None):
    """
    Attach the Firebase session cookie to a Flask response.
    """
    cookie_name = get_cookie_name()
    secure = current_app.config.get('SESSION_COOKIE_SECURE', False)

    response.set_cookie(
        key=cookie_name,
        value=session_cookie,
        max_age=browser_max_age,
        httponly=True,
        secure=secure,
        samesite='Lax',
        path='/'
    )
    return response


def clear_auth_cookie(response):
    """
    Delete the session cookie from a Flask response.
    Includes matching path, secure, httponly, and samesite flags per RFC 6265bis.
    """
    cookie_name = get_cookie_name()
    secure = current_app.config.get('SESSION_COOKIE_SECURE', False)
    response.delete_cookie(
        cookie_name,
        path='/',
        secure=secure,
        httponly=True,
        samesite='Lax'
    )
    return response


def get_current_user_from_request(check_revoked: bool = False) -> Optional[Dict[str, Any]]:
    """
    Verify the session cookie on the current request and return user claims dict.
    Caches result on flask.g per-request tied to the specific session cookie value.

    Safeguard: A request verified with check_revoked=False CANNOT bypass a later
    check_revoked=True verification within the same request lifecycle.
    """
    cookie_name = get_cookie_name()
    session_cookie = request.cookies.get(cookie_name)

    cached_cookie = getattr(g, '_current_user_cookie', None)
    cached_checked_revoked = getattr(g, '_current_user_checked_revoked', False)

    # Re-use cached result ONLY IF the cookie matches AND
    # (either revocation check is not requested, or the cached result was already verified with check_revoked=True)
    if cached_cookie is not None and cached_cookie == session_cookie:
        if not check_revoked or cached_checked_revoked:
            return getattr(g, '_current_user', None)

    if not session_cookie:
        # Check if test mock user is in session — strictly prohibited outside TESTING mode
        if current_app.config.get('TESTING') and 'test_uid' in session:
            test_user = {
                'id': session['test_uid'],
                'uid': session['test_uid'],
                'username': session.get('username', 'TestUser'),
                'email': session.get('email', 'test@example.com')
            }
            g._current_user = test_user
            g._current_user_cookie = None
            g._current_user_checked_revoked = True
            return test_user

        g._current_user = None
        g._current_user_cookie = None
        g._current_user_checked_revoked = False
        return None

    try:
        auth_mod = get_auth_module()
        claims = auth_mod.verify_session_cookie(session_cookie, check_revoked=check_revoked)

        uid = claims.get('uid') or claims.get('sub')
        email = claims.get('email', '')
        username = claims.get('name')

        if not username:
            # Fallback to Firestore user profile
            try:
                profile = get_user_store().get_user_by_uid(uid)
                if profile:
                    username = profile.get('username')
            except Exception:
                pass

        user_info = {
            'id': uid,
            'uid': uid,
            'username': username or 'User',
            'email': email
        }
        g._current_user = user_info
        g._current_user_cookie = session_cookie
        # If this verification checked revocation, or if a previous check in this request did, mark it
        g._current_user_checked_revoked = check_revoked or cached_checked_revoked
        return user_info

    except auth.ExpiredSessionCookieError:
        logger.debug("Session cookie expired.")
        g._current_user = None
        g._current_user_cookie = None
        g._current_user_checked_revoked = False
        g._clear_cookie_needed = True
        return None
    except auth.RevokedSessionCookieError:
        logger.debug("Session cookie revoked.")
        g._current_user = None
        g._current_user_cookie = None
        g._current_user_checked_revoked = False
        g._clear_cookie_needed = True
        return None
    except auth.InvalidSessionCookieError as e:
        logger.debug(f"Invalid session cookie: {e}")
        g._current_user = None
        g._current_user_cookie = None
        g._current_user_checked_revoked = False
        g._clear_cookie_needed = True
        return None
    except Exception as e:
        logger.debug(f"Session cookie verification failed: {e}")
        g._current_user = None
        g._current_user_cookie = None
        g._current_user_checked_revoked = False
        g._clear_cookie_needed = True
        return None


def login_required(func_or_none=None, *, check_revoked=False):
    """
    Decorator that ensures the user is authenticated.
    - Page routes: redirects to /signin?next=...
    - API routes (JSON or /api/): returns 401 JSON {'error': 'Login required.', 'login_required': True}

    Can be used as:
        @login_required
    or:
        @login_required(check_revoked=True)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user_from_request(check_revoked=check_revoked)
            if not user:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({
                        'error': 'Login required.',
                        'login_required': True
                    }), 401
                return redirect(url_for('auth.signin', next=request.url))
            return f(*args, **kwargs)
        return decorated_function

    if func_or_none is not None and callable(func_or_none):
        return decorator(func_or_none)
    return decorator
