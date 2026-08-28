"""
Auth Routes — Authentication Blueprint
========================================
Handles user registration, login, logout, profile, and
password reset (OTP via email).

Routes:
    /signup             — Account creation (GET/POST)
    /signin             — Login (GET/POST)
    /logout             — Sign out (POST)
    /profile            — Authenticated profile page (GET)
    /forgot-password    — Password reset flow (GET)
    /api/auth/send-otp  — Send/resend OTP email (POST)
    /api/auth/verify-otp    — Verify OTP code (POST)
    /api/auth/reset-password — Set new password (POST)
"""

import re
import secrets
import logging
import smtplib
from functools import wraps
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, jsonify, current_app
)
from werkzeug.security import generate_password_hash, check_password_hash

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

# Email format regex (simple but effective)
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

# OTP configuration
OTP_EXPIRY_MINUTES = 5
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 60
MIN_PASSWORD_LENGTH = 6


# ════════════════════════════════════════════════════════════════
# LOGIN REQUIRED DECORATOR
# ════════════════════════════════════════════════════════════════

def login_required(f):
    """
    Decorator that ensures the user is authenticated.
    - Page routes: redirects to /signin
    - API routes (JSON): returns 401
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({
                    'error': 'Login required.',
                    'login_required': True
                }), 401
            return redirect(url_for('auth.signin', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def _get_db_path():
    """Get the database path from the current app config."""
    return current_app.config.get('SAVED_SQUADS_DB')


# ════════════════════════════════════════════════════════════════
# SIGN UP
# ════════════════════════════════════════════════════════════════

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """Account creation page and handler."""
    if 'user_id' in session:
        return redirect(url_for('main.index'))

    if request.method == 'GET':
        return render_template('signup.html')

    from app.auth_db import create_user, username_exists, email_exists

    db_path = _get_db_path()

    # Extract form data
    username = (request.form.get('username') or '').strip()
    email = (request.form.get('email') or '').strip()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')

    # Server-side validation — collect all errors
    errors = {}

    if not username:
        errors['username'] = 'Username is required.'
    elif username_exists(db_path, username):
        errors['username'] = 'Username already exists.'

    if not email:
        errors['email'] = 'Email is required.'
    elif not EMAIL_REGEX.match(email):
        errors['email'] = 'Please enter a valid email address.'
    elif email_exists(db_path, email):
        errors['email'] = 'Email is already registered.'

    if not password:
        errors['password'] = 'Password is required.'
    elif len(password) < MIN_PASSWORD_LENGTH:
        errors['password'] = f'Password must contain at least {MIN_PASSWORD_LENGTH} characters.'

    if password != confirm_password:
        errors['confirm_password'] = 'Passwords do not match.'

    if errors:
        return render_template('signup.html', errors=errors,
                               username=username, email=email), 400

    # Create user
    password_hash = generate_password_hash(password)
    try:
        user_id = create_user(db_path, username, email, password_hash)
    except Exception as e:
        logger.error(f"[ERROR] Failed to create user: {e}")
        errors['general'] = 'An error occurred. Please try again.'
        return render_template('signup.html', errors=errors,
                               username=username, email=email), 500

    # Auto-login after signup
    session.clear()
    session['user_id'] = user_id
    session['username'] = username
    session.permanent = True

    return redirect(url_for('main.index'))


# ════════════════════════════════════════════════════════════════
# SIGN IN
# ════════════════════════════════════════════════════════════════

@auth_bp.route('/signin', methods=['GET', 'POST'])
def signin():
    """Login page and handler."""
    if 'user_id' in session:
        return redirect(url_for('main.index'))

    if request.method == 'GET':
        return render_template('signin.html')

    from app.auth_db import get_user_by_username_or_email

    db_path = _get_db_path()

    identifier = (request.form.get('identifier') or '').strip()
    password = request.form.get('password', '')

    errors = {}

    if not identifier:
        errors['identifier'] = 'Username or email is required.'
    if not password:
        errors['password'] = 'Password is required.'

    if errors:
        return render_template('signin.html', errors=errors,
                               identifier=identifier), 400

    # Look up user — generic error to prevent enumeration
    user = get_user_by_username_or_email(db_path, identifier)

    if not user or not check_password_hash(user['password_hash'], password):
        errors['general'] = 'Incorrect username/email or password.'
        return render_template('signin.html', errors=errors,
                               identifier=identifier), 401

    # Establish session
    session.clear()
    session['user_id'] = user['id']
    session['username'] = user['username']

    # Redirect to original page if 'next' was specified
    next_url = request.args.get('next') or request.form.get('next')
    if next_url and _is_safe_url(next_url):
        return redirect(next_url)

    return redirect(url_for('main.index'))


def _is_safe_url(target):
    """Basic check to prevent open redirect attacks."""
    from urllib.parse import urlparse
    ref_url = urlparse(request.host_url)
    test_url = urlparse(target)
    return test_url.scheme in ('', 'http', 'https') and ref_url.netloc == test_url.netloc


# ════════════════════════════════════════════════════════════════
# LOGOUT
# ════════════════════════════════════════════════════════════════

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Sign out — clear session completely."""
    session.clear()
    return redirect(url_for('main.index'))


# ════════════════════════════════════════════════════════════════
# PROFILE
# ════════════════════════════════════════════════════════════════

@auth_bp.route('/profile')
@login_required
def profile():
    """Authenticated profile page."""
    from app.auth_db import get_user_by_id
    from app.saved_squads_db import list_squads, get_db_path

    db_path = _get_db_path()
    user_id = session['user_id']

    user = get_user_by_id(db_path, user_id)
    if not user:
        session.clear()
        return redirect(url_for('auth.signin'))

    squads = list_squads(db_path, user_id)

    return render_template('profile.html', user=user, squads=squads)


# ════════════════════════════════════════════════════════════════
# FORGOT PASSWORD — PAGE
# ════════════════════════════════════════════════════════════════

@auth_bp.route('/forgot-password')
def forgot_password():
    """Forgot password page (3-step SPA flow)."""
    if 'user_id' in session:
        return redirect(url_for('main.index'))
    return render_template('forgot_password.html')


# ════════════════════════════════════════════════════════════════
# FORGOT PASSWORD — SEND OTP API
# ════════════════════════════════════════════════════════════════

@auth_bp.route('/api/auth/send-otp', methods=['POST'])
def send_otp():
    """
    Send a 6-digit OTP to the user's email.
    Generic response regardless of whether email exists (anti-enumeration).
    """
    from app.auth_db import (
        get_user_by_email, create_otp, get_active_otp,
        invalidate_user_otps
    )

    db_path = _get_db_path()
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()

    if not email or not EMAIL_REGEX.match(email):
        return jsonify({'error': 'Please enter a valid email address.'}), 400

    # Generic success response (anti-enumeration)
    generic_response = jsonify({
        'message': 'If an account exists for this email, a verification code has been sent.'
    })

    user = get_user_by_email(db_path, email)
    if not user:
        return generic_response

    # Check resend cooldown
    active_otp = get_active_otp(db_path, user['id'])
    if active_otp:
        created = datetime.fromisoformat(active_otp['created_at'])
        now = datetime.now(timezone.utc)
        elapsed = (now - created).total_seconds()
        if elapsed < OTP_RESEND_COOLDOWN_SECONDS:
            remaining = int(OTP_RESEND_COOLDOWN_SECONDS - elapsed)
            return jsonify({
                'error': f'Please wait {remaining} seconds before requesting a new code.',
                'cooldown': remaining
            }), 429

    # Invalidate previous OTPs
    invalidate_user_otps(db_path, user['id'])

    # Generate 6-digit OTP
    otp_code = str(secrets.randbelow(900000) + 100000)
    otp_hash = generate_password_hash(otp_code)
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat()

    # Attempt to send email before committing OTP to DB
    try:
        _send_otp_email(email, otp_code, user['username'])
    except Exception as e:
        logger.error(f"[ERROR] Failed to send OTP email to {email}: {e}")
        return jsonify({
            'error': 'Failed to send verification email. Please try again.'
        }), 500

    # Email sent successfully — now store the OTP
    try:
        create_otp(db_path, user['id'], otp_hash, expires_at)
    except Exception as e:
        logger.error(f"[ERROR] Failed to store OTP: {e}")
        return jsonify({
            'error': 'An error occurred. Please try again.'
        }), 500

    return generic_response


# ════════════════════════════════════════════════════════════════
# FORGOT PASSWORD — VERIFY OTP API
# ════════════════════════════════════════════════════════════════

@auth_bp.route('/api/auth/verify-otp', methods=['POST'])
def verify_otp():
    """Verify the 6-digit OTP code."""
    from app.auth_db import (
        get_user_by_email, get_active_otp,
        increment_otp_attempts, consume_otp
    )

    db_path = _get_db_path()
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    otp_code = (data.get('otp') or '').strip()

    if not email or not otp_code:
        return jsonify({'error': 'Email and verification code are required.'}), 400

    user = get_user_by_email(db_path, email)
    if not user:
        return jsonify({'error': 'Invalid verification code.'}), 400

    active_otp = get_active_otp(db_path, user['id'])
    if not active_otp:
        return jsonify({'error': 'No active verification code found. Please request a new one.'}), 400

    # Check expiry
    expires = datetime.fromisoformat(active_otp['expires_at'])
    now = datetime.now(timezone.utc)
    if now > expires:
        consume_otp(db_path, active_otp['id'])
        return jsonify({
            'error': 'This code has expired. Please request a new one.',
            'expired': True
        }), 400

    # Check attempt limit
    if active_otp['attempt_count'] >= OTP_MAX_ATTEMPTS:
        consume_otp(db_path, active_otp['id'])
        return jsonify({
            'error': 'Too many incorrect attempts. Please request a new code.',
            'max_attempts': True
        }), 400

    # Verify OTP hash
    if not check_password_hash(active_otp['otp_hash'], otp_code):
        increment_otp_attempts(db_path, active_otp['id'])
        remaining = OTP_MAX_ATTEMPTS - active_otp['attempt_count'] - 1
        return jsonify({
            'error': f'Invalid verification code. {remaining} attempt(s) remaining.'
        }), 400

    # OTP verified — mark as consumed and set session flag
    consume_otp(db_path, active_otp['id'])
    session['otp_verified_user_id'] = user['id']
    session['otp_verified_email'] = email

    return jsonify({'message': 'Code verified successfully.', 'verified': True})


# ════════════════════════════════════════════════════════════════
# FORGOT PASSWORD — RESET PASSWORD API
# ════════════════════════════════════════════════════════════════

@auth_bp.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    """Set new password after OTP verification."""
    from app.auth_db import update_password

    db_path = _get_db_path()

    # Verify that OTP was previously verified in this session
    verified_user_id = session.get('otp_verified_user_id')
    if not verified_user_id:
        return jsonify({'error': 'Please verify your email first.'}), 403

    data = request.get_json(silent=True) or {}
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')

    errors = {}

    if not new_password:
        errors['new_password'] = 'New password is required.'
    elif len(new_password) < MIN_PASSWORD_LENGTH:
        errors['new_password'] = f'Password must contain at least {MIN_PASSWORD_LENGTH} characters.'

    if new_password != confirm_password:
        errors['confirm_password'] = 'Passwords do not match.'

    if errors:
        return jsonify({'errors': errors}), 400

    # Update password
    try:
        new_hash = generate_password_hash(new_password)
        update_password(db_path, verified_user_id, new_hash)
    except Exception as e:
        logger.error(f"[ERROR] Failed to update password: {e}")
        return jsonify({'error': 'An error occurred. Please try again.'}), 500

    # Clear OTP verification session data
    session.pop('otp_verified_user_id', None)
    session.pop('otp_verified_email', None)

    return jsonify({'message': 'Password reset successful. You can now sign in with your new password.'})


# ════════════════════════════════════════════════════════════════
# EMAIL SENDING
# ════════════════════════════════════════════════════════════════

def _send_otp_email(to_email, otp_code, username):
    """
    Send the OTP verification email via Gmail SMTP.
    Reads configuration from current_app.config.

    Raises Exception on failure (caller handles).
    """
    mail_server = current_app.config.get('MAIL_SERVER', 'smtp.gmail.com')
    mail_port = current_app.config.get('MAIL_PORT', 587)
    mail_use_tls = current_app.config.get('MAIL_USE_TLS', True)
    mail_username = current_app.config.get('MAIL_USERNAME', '')
    mail_password = current_app.config.get('MAIL_PASSWORD', '')

    if not mail_username or not mail_password:
        raise ValueError("SMTP credentials not configured. Set MAIL_USERNAME and MAIL_PASSWORD in .env")

    app_name = current_app.config.get('APP_NAME', 'KickoffXI')

    subject = f'{app_name} — Password Reset Code'
    html_body = f"""
    <div style="font-family: 'Inter', -apple-system, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px 24px;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h1 style="color: #141e33; font-size: 20px; font-weight: 800; letter-spacing: 0.05em; text-transform: uppercase; margin: 0;">
                {app_name}
            </h1>
        </div>

        <div style="background: #f8f9fa; border-radius: 16px; padding: 32px 24px; text-align: center;">
            <h2 style="color: #141e33; font-size: 18px; font-weight: 700; margin: 0 0 8px 0;">
                Password Reset
            </h2>
            <p style="color: #667; font-size: 14px; margin: 0 0 24px 0; line-height: 1.5;">
                Hi <strong>{username}</strong>, use the code below to reset your password.
            </p>

            <div style="background: #141e33; border-radius: 12px; padding: 20px; margin: 0 0 24px 0;">
                <span style="color: #d4a017; font-size: 32px; font-weight: 900; letter-spacing: 0.3em;">
                    {otp_code}
                </span>
            </div>

            <p style="color: #999; font-size: 12px; margin: 0; line-height: 1.5;">
                This code expires in {OTP_EXPIRY_MINUTES} minutes.<br>
                If you didn't request this, you can safely ignore this email.
            </p>
        </div>

        <p style="color: #ccc; font-size: 11px; text-align: center; margin-top: 24px;">
            &copy; 2026 {app_name}
        </p>
    </div>
    """

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f'{app_name} <{mail_username}>'
    msg['To'] = to_email

    # Plain text fallback
    text_body = (
        f"{app_name} — Password Reset\n\n"
        f"Hi {username},\n\n"
        f"Your password reset code is: {otp_code}\n\n"
        f"This code expires in {OTP_EXPIRY_MINUTES} minutes.\n"
        f"If you didn't request this, ignore this email.\n"
    )

    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    with smtplib.SMTP(mail_server, mail_port) as server:
        if mail_use_tls:
            server.starttls()
        server.login(mail_username, mail_password)
        server.sendmail(mail_username, to_email, msg.as_string())

    logger.info(f"[OK] OTP email sent to {to_email}")
