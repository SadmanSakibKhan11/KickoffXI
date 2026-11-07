"""
User Store — Firestore Access for Users and Usernames
======================================================
Manages user profiles, username reservations, and reset request throttling.
Data Model:
    users/{uid}
        uid: string
        username: string (original case)
        username_normalized: string (lowercase)
        email: string (lowercase)
        created_at: ISO-8601 UTC string
        updated_at: ISO-8601 UTC string
        last_reset_request_at: nullable ISO-8601 UTC string

    usernames/{username_normalized}
        uid: string
        created_at: ISO-8601 UTC string

Features:
- Transactional username reservation to guarantee uniqueness.
- Strict username rules: 3-20 characters [a-zA-Z0-9_.-], adhering to Firestore document ID limits.
- Anti-enumeration: returns plain dicts, errors are controlled.
- Interface pattern allowing in-memory substitution for tests.
"""

import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple

from app.firebase_client import get_firestore_client

# Document ID rules and username constraints
USERNAME_REGEX = re.compile(r'^[a-zA-Z0-9_.-]{3,20}$')
MAX_USERNAME_BYTES = 1500


def normalize_username(username: str) -> str:
    """Normalize username for uniqueness checks and Firestore doc IDs."""
    return username.strip().lower()


def validate_document_id_rules(username: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a username obeys Cloud Firestore document ID rules:
    - Not empty
    - Does not contain '/'
    - Is not '.' or '..'
    - Does not match '__.*__'
    - UTF-8 representation <= 1500 bytes
    """
    if not username or not username.strip():
        return False, "Username is empty."
    norm = normalize_username(username)
    if '/' in norm:
        return False, "Username cannot contain '/' (prohibited in Firestore document IDs)."
    if norm in ('.', '..'):
        return False, "Username cannot be '.' or '..' (prohibited in Firestore document IDs)."
    if norm.startswith('__') and norm.endswith('__'):
        return False, "Username cannot match '__.*__' (reserved in Firestore document IDs)."
    if len(norm.encode('utf-8')) > MAX_USERNAME_BYTES:
        return False, f"Username exceeds maximum size of {MAX_USERNAME_BYTES} bytes."
    return True, None


def validate_username(username: str) -> Tuple[bool, Optional[str]]:
    """
    Validate username for new signups:
    - 3 to 20 characters
    - Allowed characters: letters, numbers, underscores, periods, hyphens
    - Must also satisfy Firestore document ID rules
    """
    if not username:
        return False, "Username is required."

    raw = username.strip()
    if len(raw) < 3 or len(raw) > 20:
        return False, "Username must be between 3 and 20 characters."

    if not USERNAME_REGEX.match(raw):
        return False, "Username can only contain letters, numbers, underscores, periods, and hyphens."

    return validate_document_id_rules(raw)


class UsernameAlreadyTakenError(Exception):
    """Raised when attempting to reserve a username that is already taken."""
    pass


class UserNotFoundError(Exception):
    """Raised when a user document does not exist."""
    pass


class BaseUserStore:
    """Abstract interface for user profile and username data operations."""

    def create_user_profile(
        self,
        uid: str,
        username: str,
        email: str,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def get_user_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def resolve_username_to_uid(self, username: str) -> Optional[str]:
        raise NotImplementedError

    def check_and_update_reset_throttle(
        self,
        uid: str,
        cooldown_seconds: int = 60
    ) -> Tuple[bool, int]:
        """
        Atomically check and update last_reset_request_at.
        Returns (allowed: bool, remaining_seconds: int).
        """
        raise NotImplementedError

    def delete_user_profile(self, uid: str, username: str) -> None:
        """Compensating cleanup: deletes username reservation and user document."""
        raise NotImplementedError


class FirestoreUserStore(BaseUserStore):
    """Production implementation using Google Cloud Firestore."""

    def __init__(self, db=None):
        self._db = db

    @property
    def db(self):
        if self._db is None:
            self._db = get_firestore_client()
        return self._db

    def create_user_profile(
        self,
        uid: str,
        username: str,
        email: str,
    ) -> Dict[str, Any]:
        norm = normalize_username(username)
        now_iso = datetime.now(timezone.utc).isoformat()

        username_ref = self.db.collection('usernames').document(norm)
        user_ref = self.db.collection('users').document(uid)

        from google.cloud import firestore

        @firestore.transactional
        def _txn_create(transaction):
            snap = username_ref.get(transaction=transaction)
            if snap.exists:
                existing_uid = (snap.to_dict() or {}).get('uid')
                if existing_uid != uid:
                    raise UsernameAlreadyTakenError(f"Username '{username}' is already taken.")

            user_doc = {
                'uid': uid,
                'username': username.strip(),
                'username_normalized': norm,
                'email': email.strip().lower(),
                'created_at': now_iso,
                'updated_at': now_iso,
                'last_reset_request_at': None,
            }

            username_doc = {
                'uid': uid,
                'created_at': now_iso,
            }

            transaction.set(username_ref, username_doc)
            transaction.set(user_ref, user_doc)
            return user_doc

        transaction = self.db.transaction()
        return _txn_create(transaction)

    def get_user_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        user_ref = self.db.collection('users').document(uid)
        snap = user_ref.get()
        if not snap.exists:
            return None
        return snap.to_dict()

    def resolve_username_to_uid(self, username: str) -> Optional[str]:
        norm = normalize_username(username)
        snap = self.db.collection('usernames').document(norm).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return data.get('uid')

    def check_and_update_reset_throttle(
        self,
        uid: str,
        cooldown_seconds: int = 60
    ) -> Tuple[bool, int]:
        user_ref = self.db.collection('users').document(uid)
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        from google.cloud import firestore

        @firestore.transactional
        def _txn_throttle(transaction):
            snap = user_ref.get(transaction=transaction)
            last_request = None
            if snap.exists:
                data = snap.to_dict() or {}
                last_request = data.get('last_reset_request_at')

            if last_request:
                try:
                    last_dt = datetime.fromisoformat(last_request)
                    elapsed = (now - last_dt).total_seconds()
                    if elapsed < cooldown_seconds:
                        remaining = int(cooldown_seconds - elapsed)
                        return False, remaining
                except Exception:
                    pass

            transaction.set(user_ref, {
                'last_reset_request_at': now_iso,
                'updated_at': now_iso
            }, merge=True)
            return True, 0

        transaction = self.db.transaction()
        return _txn_throttle(transaction)

    def delete_user_profile(self, uid: str, username: str) -> None:
        """
        Compensating cleanup: deletes username reservation and user document.
        Validates ownership: only deletes username reservation if it actually maps to uid.
        """
        norm = normalize_username(username)
        from google.cloud import firestore

        username_ref = self.db.collection('usernames').document(norm)
        user_ref = self.db.collection('users').document(uid)

        @firestore.transactional
        def _txn_delete(transaction):
            u_snap = username_ref.get(transaction=transaction)
            if u_snap.exists and (u_snap.to_dict() or {}).get('uid') == uid:
                transaction.delete(username_ref)
            user_snap = user_ref.get(transaction=transaction)
            if user_snap.exists:
                transaction.delete(user_ref)

        transaction = self.db.transaction()
        _txn_delete(transaction)


class InMemoryUserStore(BaseUserStore):
    """In-memory user store for fast, isolated offline unit tests."""

    def __init__(self):
        self.users: Dict[str, Dict[str, Any]] = {}
        self.usernames: Dict[str, str] = {}  # norm -> uid

    def create_user_profile(
        self,
        uid: str,
        username: str,
        email: str,
    ) -> Dict[str, Any]:
        norm = normalize_username(username)
        if norm in self.usernames:
            raise UsernameAlreadyTakenError(f"Username '{username}' is already taken.")

        now_iso = datetime.now(timezone.utc).isoformat()
        user_doc = {
            'uid': uid,
            'username': username.strip(),
            'username_normalized': norm,
            'email': email.strip().lower(),
            'created_at': now_iso,
            'updated_at': now_iso,
            'last_reset_request_at': None,
        }
        self.usernames[norm] = uid
        self.users[uid] = user_doc
        return dict(user_doc)

    def get_user_by_uid(self, uid: str) -> Optional[Dict[str, Any]]:
        doc = self.users.get(uid)
        return dict(doc) if doc else None

    def resolve_username_to_uid(self, username: str) -> Optional[str]:
        norm = normalize_username(username)
        return self.usernames.get(norm)

    def check_and_update_reset_throttle(
        self,
        uid: str,
        cooldown_seconds: int = 60
    ) -> Tuple[bool, int]:
        user = self.users.setdefault(uid, {'uid': uid})
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        last_request = user.get('last_reset_request_at')

        if last_request:
            try:
                last_dt = datetime.fromisoformat(last_request)
                elapsed = (now - last_dt).total_seconds()
                if elapsed < cooldown_seconds:
                    return False, int(cooldown_seconds - elapsed)
            except Exception:
                pass

        user['last_reset_request_at'] = now_iso
        user['updated_at'] = now_iso
        return True, 0

    def delete_user_profile(self, uid: str, username: str) -> None:
        norm = normalize_username(username)
        if self.usernames.get(norm) == uid:
            self.usernames.pop(norm, None)
        self.users.pop(uid, None)


# Default singleton instance (can be overridden in tests via set_user_store)
_current_user_store: Optional[BaseUserStore] = None


def get_user_store() -> BaseUserStore:
    global _current_user_store
    if _current_user_store is None:
        _current_user_store = FirestoreUserStore()
    return _current_user_store


def set_user_store(store: BaseUserStore) -> None:
    global _current_user_store
    _current_user_store = store
