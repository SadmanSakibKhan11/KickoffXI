"""
Firebase Client Module
======================
Provides lazy, thread-safe, idempotent initialization of the Firebase Admin SDK.
Exposes Firebase Auth and Cloud Firestore clients for server-side operations.
Honors Firebase Emulator environment variables when set.
Fails safely with clear messages without ever printing secret contents.
"""

import os
import json
import logging
import threading
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore, auth

logger = logging.getLogger(__name__)

_init_lock = threading.Lock()
_app: Optional[firebase_admin.App] = None
_db = None


def get_firebase_app() -> firebase_admin.App:
    """
    Idempotently initialize and return the default Firebase Admin App.
    Safe across threads and gunicorn workers.
    """
    global _app
    if _app is not None:
        return _app

    with _init_lock:
        if _app is not None:
            return _app

        try:
            # Check if default app is already initialized
            _app = firebase_admin.get_app()
            return _app
        except ValueError:
            # Not initialized yet, proceed
            pass

        # Check for emulator environment
        firestore_emulator = os.getenv('FIRESTORE_EMULATOR_HOST')
        auth_emulator = os.getenv('FIREBASE_AUTH_EMULATOR_HOST')

        # Safeguard: prevent split-brain where Auth and Firestore connect to different environments
        if bool(firestore_emulator) != bool(auth_emulator):
            raise RuntimeError(
                f"Mismatched Firebase emulator configuration: "
                f"FIRESTORE_EMULATOR_HOST is {'set (' + firestore_emulator + ')' if firestore_emulator else 'unset'} and "
                f"FIREBASE_AUTH_EMULATOR_HOST is {'set (' + auth_emulator + ')' if auth_emulator else 'unset'}. "
                f"Both variables must be set together to run against the Firebase Emulator Suite, "
                f"or both unset to connect to live Firebase."
            )

        flask_config = os.getenv('FLASK_CONFIG', '')
        if flask_config == 'production' and (firestore_emulator or auth_emulator):
            raise RuntimeError(
                "Firebase emulator environment variables (FIRESTORE_EMULATOR_HOST, FIREBASE_AUTH_EMULATOR_HOST) "
                "cannot be configured in production."
            )

        service_account_val = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
        gac_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

        cred = None

        if firestore_emulator and auth_emulator:
            # Running against Firebase Emulator Suite: can use dummy credentials
            logger.info("[EMULATOR] Initializing Firebase Admin with emulator credentials.")
            project_id = os.getenv('FIREBASE_PROJECT_ID', 'kickoffxi-dev')
            _app = firebase_admin.initialize_app(options={'projectId': project_id})
            return _app

        elif service_account_val:
            val_stripped = service_account_val.strip()
            if val_stripped.startswith('{') and val_stripped.endswith('}'):
                # Raw JSON string
                try:
                    sa_info = json.loads(val_stripped)
                    cred = credentials.Certificate(sa_info)
                except Exception as e:
                    raise RuntimeError(
                        f"FIREBASE_SERVICE_ACCOUNT_JSON appears to be a JSON string but could not be parsed: {e}"
                    )
            else:
                # File path
                if not os.path.isfile(val_stripped):
                    raise FileNotFoundError(
                        f"FIREBASE_SERVICE_ACCOUNT_JSON path does not exist: {val_stripped}"
                    )
                cred = credentials.Certificate(val_stripped)

        elif gac_path:
            gac_stripped = gac_path.strip()
            if not os.path.isfile(gac_stripped):
                raise FileNotFoundError(
                    f"GOOGLE_APPLICATION_CREDENTIALS path does not exist: {gac_stripped}"
                )
            cred = credentials.Certificate(gac_stripped)

        else:
            raise RuntimeError(
                "Firebase credentials not configured. Please set GOOGLE_APPLICATION_CREDENTIALS "
                "or FIREBASE_SERVICE_ACCOUNT_JSON to your service account key file path or JSON content."
            )

        _app = firebase_admin.initialize_app(cred)
        logger.info("[OK] Firebase Admin SDK initialized successfully.")
        return _app


def get_firestore_client():
    """Return the Firestore client instance."""
    global _db
    if _db is not None:
        return _db

    get_firebase_app()
    _db = firestore.client()
    return _db


def get_auth_module():
    """Return the Firebase Admin auth module with verified initialization."""
    get_firebase_app()
    return auth


def reset_firebase_client_for_testing():
    """Reset cached client instances (used in test fixtures)."""
    global _app, _db
    with _init_lock:
        _app = None
        _db = None

