"""
Auth Routes — Authentication Blueprint
========================================
Handles user registration, login, logout, profile, and password reset
via Firebase Authentication, Cloud Firestore, and Identity Toolkit REST.

Routes:
    /signup             — Account creation (GET/POST)
    /signin             — Login (GET/POST)
    /logout             — Sign out (POST)
    /profile            — Authenticated profile page (GET)
    /forgot-password    — Password reset request (GET/POST)
    /reset-password     — Password reset execution (GET/POST)
"""

import re
import time
import logging
from urllib.parse import urlparse, parse_qs

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, jsonify, current_app, make_response
)
from firebase_admin import auth, exceptions as fb_exceptions

from app.firebase_client import get_auth_module
from app.identity_rest import IdentityClient, IdentityApiError
from app.user_store import (
    get_user_store, validate_username, normalize_username,
    UsernameAlreadyTakenError
)
from app.squad_store import get_squad_store
from app.session_auth import (
    login_required, is_safe_url, get_current_user_from_request,
    create_firebase_session_cookie, set_auth_cookie, clear_auth_cookie
)
from app.email_sender import send_password_reset_email, EmailDeliveryError

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
MIN_PASSWORD_LENGTH = 6


def _add_security_headers(response):
    """Add no-store and referrer-policy headers for sensitive pages."""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


# ════════════════════════════════════════════════════════════════
# SIGN UP
# ════════════════════════════════════════════════════════════════

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """Account creation page and handler using Firebase Auth & Firestore."""
    if get_current_user_from_request():
        return redirect(url_for('main.index'))

    if request.method == 'GET':
        return render_template('signup.html')

    user_store = get_user_store()

    username = (request.form.get('username') or '').strip()
    email = (request.form.get('email') or '').strip().lower()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')

    errors = {}

    # 1. Validation
    is_valid_uname, uname_err = validate_username(username)
    if not is_valid_uname:
        errors['username'] = uname_err
    elif user_store.resolve_username_to_uid(username):
        errors['username'] = 'Username already exists.'

    if not email:
        errors['email'] = 'Email is required.'
    elif not EMAIL_REGEX.match(email):
        errors['email'] = 'Please enter a valid email address.'

    if not password:
        errors['password'] = 'Password is required.'
    elif len(password) < MIN_PASSWORD_LENGTH:
        errors['password'] = f'Password must contain at least {MIN_PASSWORD_LENGTH} characters.'

    if password != confirm_password:
        errors['confirm_password'] = 'Passwords do not match.'

    if errors:
        return render_template(
            'signup.html',
            errors=errors,
            username=username,
            email=email
        ), 400

    auth_mod = get_auth_module()
    identity_client = IdentityClient()

    # 2. Create Auth user
    try:
        auth_user = auth_mod.create_user(
            email=email,
            password=password,
            display_name=username
        )
    except auth.EmailAlreadyExistsError:
        errors['email'] = 'Email is already registered.'
        return render_template(
            'signup.html',
            errors=errors,
            username=username,
            email=email
        ), 400
    except Exception as e:
        logger.error(f"[ERROR] Failed to create Firebase Auth user: {e}")
        errors['general'] = 'An error occurred during account creation. Please try again.'
        return render_template(
            'signup.html',
            errors=errors,
            username=username,
            email=email
        ), 500

    # 3. Create Firestore profile with transactional username reservation
    created_profile = False
    try:
        user_store.create_user_profile(
            uid=auth_user.uid,
            username=username,
            email=email
        )
        created_profile = True
    except UsernameAlreadyTakenError:
        # Compensating action: delete auth user
        try:
            auth_mod.delete_user(auth_user.uid)
        except Exception as rollback_err:
            logger.error(f"[CRITICAL] Failed to delete orphan auth user {auth_user.uid}: {rollback_err}")
        errors['username'] = 'Username already exists.'
        return render_template(
            'signup.html',
            errors=errors,
            username=username,
            email=email
        ), 400
    except Exception as e:
        logger.error(f"[ERROR] Failed to create Firestore user profile: {e}")
        try:
            auth_mod.delete_user(auth_user.uid)
        except Exception as rollback_err:
            logger.error(f"[CRITICAL] Failed to delete orphan auth user {auth_user.uid}: {rollback_err}")
        errors['general'] = 'An error occurred during registration. Please try again.'
        return render_template(
            'signup.html',
            errors=errors,
            username=username,
            email=email
        ), 500

    # 4. Auto-login after signup (non-persistent)
    session.clear()
    try:
        sign_in_resp = identity_client.sign_in_with_password(email, password)
        id_token = sign_in_resp['idToken']
        session_cookie, max_age = create_firebase_session_cookie(id_token, remember=False)

        resp = make_response(redirect(url_for('main.index')))
        return set_auth_cookie(resp, session_cookie, max_age)
    except Exception as e:
        logger.error(f"[ERROR] Post-signup auto-login failed: {e}")
        # Even if auto-login fails, account was created -> redirect to signin
        return redirect(url_for('auth.signin'))


# ════════════════════════════════════════════════════════════════
# SIGN IN
# ════════════════════════════════════════════════════════════════

@auth_bp.route('/signin', methods=['GET', 'POST'])
def signin():
    """Login page and handler supporting Username or Email with Firebase session cookies."""
    if get_current_user_from_request():
        return redirect(url_for('main.index'))

    success_msg = None
    if request.args.get('reset') == 'success':
        success_msg = 'Password has been reset successfully. Please sign in with your new password.'

    if request.method == 'GET':
        return render_template('signin.html', success_message=success_msg)

    user_store = get_user_store()
    identity_client = IdentityClient()

    identifier = (request.form.get('identifier') or '').strip()
    password = request.form.get('password', '')
    remember = request.form.get('remember') in ('true', '1', 'on', True)

    errors = {}
    if not identifier:
        errors['identifier'] = 'Username or email is required.'
    if not password:
        errors['password'] = 'Password is required.'

    if errors:
        return render_template(
            'signin.html',
            errors=errors,
            identifier=identifier,
            success_message=success_msg
        ), 400

    target_email = None

    # Resolve identifier: email or username
    if '@' in identifier:
        target_email = identifier.lower()
    else:
        # Username resolution via Firestore
        resolved_uid = user_store.resolve_username_to_uid(identifier)
        if resolved_uid:
            user_doc = user_store.get_user_by_uid(resolved_uid)
            if user_doc:
                target_email = user_doc.get('email')

    # Timing-attack mitigation: if username not found, perform dummy verification call
    if not target_email:
        try:
            # Synthetic verification call takes similar time to real round-trip
            identity_client.sign_in_with_password("invalid-user@dummy.internal", password)
        except IdentityApiError:
            pass
        except Exception:
            pass

        errors['general'] = 'Incorrect username/email or password.'
        return render_template(
            'signin.html',
            errors=errors,
            identifier=identifier,
            success_message=success_msg
        ), 401

    # Authenticate via Identity Toolkit REST
    try:
        sign_in_resp = identity_client.sign_in_with_password(target_email, password)
        id_token = sign_in_resp['idToken']

        # Verify auth_time freshness (< 5 minutes)
        auth_mod = get_auth_module()
        decoded = auth_mod.verify_id_token(id_token)
        auth_time = decoded.get('auth_time', 0)
        current_time = time.time()
        if (current_time - auth_time) > 300:
            errors['general'] = 'Authentication expired. Please try again.'
            return render_template('signin.html', errors=errors, identifier=identifier), 401

        session_cookie, max_age = create_firebase_session_cookie(id_token, remember=remember)

        session.clear()
        next_url = request.args.get('next') or request.form.get('next')
        target_redirect = next_url if (next_url and is_safe_url(next_url)) else url_for('main.index')

        resp = make_response(redirect(target_redirect))
        return set_auth_cookie(resp, session_cookie, max_age)

    except IdentityApiError as e:
        if e.code == 'TOO_MANY_ATTEMPTS':
            errors['general'] = 'Too many attempts, please try again later.'
            status_code = 429
        else:
            errors['general'] = 'Incorrect username/email or password.'
            status_code = 401
        return render_template(
            'signin.html',
            errors=errors,
            identifier=identifier,
            success_message=success_msg
        ), status_code
    except Exception as e:
        logger.error(f"[ERROR] Unexpected sign-in error: {e}")
        errors['general'] = 'An unexpected error occurred. Please try again.'
        return render_template('signin.html', errors=errors, identifier=identifier), 500


# ════════════════════════════════════════════════════════════════
# LOGOUT
# ════════════════════════════════════════════════════════════════

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Sign out — revoke user tokens, clear session cookie and Flask session."""
    curr_user = get_current_user_from_request(check_revoked=False)
    if curr_user and curr_user.get('uid'):
        try:
            auth_mod = get_auth_module()
            auth_mod.revoke_refresh_tokens(curr_user['uid'])
        except Exception as e:
            logger.debug(f"Failed to revoke tokens on logout: {e}")

    session.clear()
    resp = make_response(redirect(url_for('main.index')))
    return clear_auth_cookie(resp)


# ════════════════════════════════════════════════════════════════
# PROFILE
# ════════════════════════════════════════════════════════════════

@auth_bp.route('/profile')
@login_required(check_revoked=True)
def profile():
    """Authenticated profile page displaying user information and saved squads."""
    curr_user = get_current_user_from_request(check_revoked=True)
    if not curr_user:
        return redirect(url_for('auth.signin'))

    user_store = get_user_store()
    squad_store = get_squad_store()

    user_doc = user_store.get_user_by_uid(curr_user['uid'])
    if not user_doc:
        # Fallback dictionary from session claims
        user_doc = {
            'username': curr_user.get('username', 'User'),
            'email': curr_user.get('email', ''),
            'created_at': '2026-01-01T00:00:00Z'
        }

    squads = squad_store.list_squads(curr_user['uid'])
    return render_template('profile.html', user=user_doc, squads=squads)


# ════════════════════════════════════════════════════════════════
# FORGOT PASSWORD
# ════════════════════════════════════════════════════════════════

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Password reset request page and handler."""
    if get_current_user_from_request():
        return redirect(url_for('main.index'))

    if request.method == 'GET':
        return render_template('forgot_password.html')

    user_store = get_user_store()
    auth_mod = get_auth_module()

    email = (request.form.get('email') or '').strip().lower()
    errors = {}

    if not email:
        errors['email'] = 'Email is required.'
    elif not EMAIL_REGEX.match(email):
        errors['email'] = 'Please enter a valid email address.'

    if errors:
        return render_template('forgot_password.html', errors=errors, email=email), 400

    # Generic confirmation text (anti-enumeration)
    generic_confirmation = (
        'If an account exists for this email, a password reset link has been sent. '
        'Please check your inbox.'
    )

    try:
        user_record = auth_mod.get_user_by_email(email)
    except (auth.UserNotFoundError, fb_exceptions.NotFoundError):
        # Email does not exist: return generic confirmation without leaking presence
        return render_template('forgot_password.html', submitted=True, success_message=generic_confirmation)
    except Exception as e:
        logger.error(f"[ERROR] Failed to query user for reset: {e}")
        return render_template('forgot_password.html', submitted=True, success_message=generic_confirmation)

    # Check 60-second throttle
    allowed, remaining = user_store.check_and_update_reset_throttle(user_record.uid, cooldown_seconds=60)
    if not allowed:
        logger.info(f"Password reset throttled for user {user_record.uid} ({remaining}s remaining)")
        return render_template('forgot_password.html', submitted=True, success_message=generic_confirmation)

    # Generate Firebase ActionCodeSettings and link
    try:
        base_url = current_app.config.get('APP_BASE_URL') or request.host_url.rstrip('/')
        action_settings = auth.ActionCodeSettings(
            url=f"{base_url}/signin",
            handle_code_in_app=False
        )
        fb_link = auth_mod.generate_password_reset_link(email, action_settings)

        # Extract oobCode from returned link
        parsed = urlparse(fb_link)
        query_params = parse_qs(parsed.query)
        oob_code = query_params.get('oobCode', [None])[0]

        if not oob_code:
            logger.error("[ERROR] Failed to extract oobCode from generated reset link")
            return render_template('forgot_password.html', submitted=True, success_message=generic_confirmation)

        reset_url = f"{base_url}/reset-password?oobCode={oob_code}"
        username = user_record.display_name or 'User'

        # Send email via Gmail SMTP
        send_password_reset_email(email, reset_url, username)

    except EmailDeliveryError as e:
        logger.error(f"[ERROR] Password reset email delivery failed: {e}")
        return render_template(
            'forgot_password.html',
            errors={'general': 'Unable to send password reset email at this time. Please try again later.'},
            email=email
        ), 500
    except Exception as e:
        logger.error(f"[ERROR] Failed to generate/send reset link: {e.__class__.__name__}")
        return render_template('forgot_password.html', submitted=True, success_message=generic_confirmation)

    return render_template('forgot_password.html', submitted=True, success_message=generic_confirmation)


# ════════════════════════════════════════════════════════════════
# RESET PASSWORD
# ════════════════════════════════════════════════════════════════

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """Password reset form and submission using single-use oobCode."""
    identity_client = IdentityClient()

    if request.method == 'GET':
        oob_code = (request.args.get('oobCode') or '').strip()
        if not oob_code:
            resp = make_response(render_template(
                'reset_password.html',
                link_error='Invalid password reset link. Please request a new one.'
            ))
            return _add_security_headers(resp), 400

        try:
            # Verify code server-side via REST (verify-only)
            identity_client.verify_password_reset_code(oob_code)
            resp = make_response(render_template('reset_password.html', oob_code=oob_code))
            return _add_security_headers(resp)
        except IdentityApiError as e:
            resp = make_response(render_template('reset_password.html', link_error=e.message))
            return _add_security_headers(resp), 400

    # POST: Confirm new password
    oob_code = (request.form.get('oobCode') or '').strip()
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    errors = {}
    if not oob_code:
        resp = make_response(render_template(
            'reset_password.html',
            link_error='Invalid or missing reset token.'
        ))
        return _add_security_headers(resp), 400

    if not new_password:
        errors['new_password'] = 'New password is required.'
    elif len(new_password) < MIN_PASSWORD_LENGTH:
        errors['new_password'] = f'Password must contain at least {MIN_PASSWORD_LENGTH} characters.'

    if new_password != confirm_password:
        errors['confirm_password'] = 'Passwords do not match.'

    if errors:
        resp = make_response(render_template(
            'reset_password.html',
            errors=errors,
            oob_code=oob_code
        ))
        return _add_security_headers(resp), 400

    try:
        identity_client.confirm_password_reset(oob_code, new_password)
        # Success: redirect to signin with success message (do not auto-login)
        resp = make_response(redirect(url_for('auth.signin', reset='success')))
        return _add_security_headers(resp)
    except IdentityApiError as e:
        if e.code in ('EXPIRED_OOB_CODE', 'INVALID_OOB_CODE'):
            resp = make_response(render_template(
                'reset_password.html',
                link_error=e.message
            ))
            return _add_security_headers(resp), 400
        else:
            errors['general'] = e.message
            resp = make_response(render_template(
                'reset_password.html',
                errors=errors,
                oob_code=oob_code
            ))
            return _add_security_headers(resp), 400
