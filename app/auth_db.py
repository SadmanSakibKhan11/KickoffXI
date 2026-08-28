"""
Auth Database — SQLite Data Access Layer
==========================================
Handles user accounts and password reset OTPs using raw sqlite3.
Reuses the same SQLite database as saved_squads_db.py.

Tables:
    users                — User accounts (username, email, hashed password)
    password_reset_otps  — Time-limited OTP records for password resets

All queries use parameterized placeholders for SQL injection safety.
Usernames and emails use COLLATE NOCASE for case-insensitive uniqueness.
"""

import sqlite3
import os
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


def get_db(db_path):
    """
    Open a SQLite connection with foreign key enforcement enabled.

    Returns:
        sqlite3.Connection with row_factory set to sqlite3.Row
        for dict-like access.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_auth_db(db_path):
    """
    Create the users and password_reset_otps tables if they don't
    already exist. Safe to call on every app startup.
    """
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    conn = get_db(db_path)
    try:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
                email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at    TEXT NOT NULL,
                updated_at    TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS password_reset_otps (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                otp_hash      TEXT NOT NULL,
                created_at    TEXT NOT NULL,
                expires_at    TEXT NOT NULL,
                consumed      INTEGER NOT NULL DEFAULT 0,
                attempt_count INTEGER NOT NULL DEFAULT 0
            );
        ''')
        conn.commit()
        logger.info(f"[OK] Auth database tables initialized at {db_path}")
    except Exception as e:
        logger.error(f"[ERROR] Failed to initialize auth database: {e}")
        raise
    finally:
        conn.close()


def _now_iso():
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ════════════════════════════════════════════════════════════════
# USER CRUD
# ════════════════════════════════════════════════════════════════

def create_user(db_path, username, email, password_hash):
    """
    Insert a new user record.

    Returns:
        The new user's ID.

    Raises:
        sqlite3.IntegrityError if username or email already exists.
    """
    now = _now_iso()
    conn = get_db(db_path)
    try:
        cursor = conn.execute(
            'INSERT INTO users (username, email, password_hash, created_at, updated_at) '
            'VALUES (?, ?, ?, ?, ?)',
            (username, email, password_hash, now, now)
        )
        conn.commit()
        user_id = cursor.lastrowid
        logger.info(f"[OK] Created user '{username}' (ID: {user_id})")
        return user_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_user_by_id(db_path, user_id):
    """Retrieve a user by ID. Returns dict or None."""
    conn = get_db(db_path)
    try:
        row = conn.execute(
            'SELECT id, username, email, password_hash, created_at, updated_at '
            'FROM users WHERE id = ?',
            (user_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_username_or_email(db_path, identifier):
    """
    Look up a user by username or email (case-insensitive).
    The identifier is checked against both columns.

    Returns dict or None.
    """
    conn = get_db(db_path)
    try:
        row = conn.execute(
            'SELECT id, username, email, password_hash, created_at, updated_at '
            'FROM users WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE',
            (identifier, identifier)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_email(db_path, email):
    """Retrieve a user by email (case-insensitive). Returns dict or None."""
    conn = get_db(db_path)
    try:
        row = conn.execute(
            'SELECT id, username, email, password_hash, created_at, updated_at '
            'FROM users WHERE email = ? COLLATE NOCASE',
            (email,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def username_exists(db_path, username):
    """Check if a username is already taken (case-insensitive)."""
    conn = get_db(db_path)
    try:
        row = conn.execute(
            'SELECT 1 FROM users WHERE username = ? COLLATE NOCASE',
            (username,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def email_exists(db_path, email):
    """Check if an email is already registered (case-insensitive)."""
    conn = get_db(db_path)
    try:
        row = conn.execute(
            'SELECT 1 FROM users WHERE email = ? COLLATE NOCASE',
            (email,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def update_password(db_path, user_id, new_password_hash):
    """Update a user's password hash."""
    now = _now_iso()
    conn = get_db(db_path)
    try:
        conn.execute(
            'UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?',
            (new_password_hash, now, user_id)
        )
        conn.commit()
        logger.info(f"[OK] Password updated for user ID {user_id}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════════
# PASSWORD RESET OTP
# ════════════════════════════════════════════════════════════════

def create_otp(db_path, user_id, otp_hash, expires_at):
    """
    Insert a new OTP record for a user.

    Args:
        user_id:    The user's ID.
        otp_hash:   Hash of the 6-digit OTP code.
        expires_at: ISO 8601 expiry timestamp.

    Returns:
        The new OTP record's ID.
    """
    now = _now_iso()
    conn = get_db(db_path)
    try:
        cursor = conn.execute(
            'INSERT INTO password_reset_otps '
            '(user_id, otp_hash, created_at, expires_at, consumed, attempt_count) '
            'VALUES (?, ?, ?, ?, 0, 0)',
            (user_id, otp_hash, now, expires_at)
        )
        conn.commit()
        return cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_active_otp(db_path, user_id):
    """
    Get the most recent unconsumed OTP for a user.
    Returns dict or None.
    """
    conn = get_db(db_path)
    try:
        row = conn.execute(
            'SELECT id, user_id, otp_hash, created_at, expires_at, consumed, attempt_count '
            'FROM password_reset_otps '
            'WHERE user_id = ? AND consumed = 0 '
            'ORDER BY created_at DESC LIMIT 1',
            (user_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def increment_otp_attempts(db_path, otp_id):
    """Increment the attempt counter for an OTP record."""
    conn = get_db(db_path)
    try:
        conn.execute(
            'UPDATE password_reset_otps SET attempt_count = attempt_count + 1 WHERE id = ?',
            (otp_id,)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def consume_otp(db_path, otp_id):
    """Mark an OTP record as consumed (used)."""
    conn = get_db(db_path)
    try:
        conn.execute(
            'UPDATE password_reset_otps SET consumed = 1 WHERE id = ?',
            (otp_id,)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def invalidate_user_otps(db_path, user_id):
    """Mark all unconsumed OTPs for a user as consumed (invalidated)."""
    conn = get_db(db_path)
    try:
        conn.execute(
            'UPDATE password_reset_otps SET consumed = 1 WHERE user_id = ? AND consumed = 0',
            (user_id,)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
