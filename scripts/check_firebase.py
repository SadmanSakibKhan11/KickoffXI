"""
KickoffXI — Firebase Configuration & Connectivity Verification
==============================================================
Validates:
1. Presence of environment configuration (shape only, no secrets).
2. Firebase Admin SDK initialization.
3. Cloud Firestore connectivity via read/write/delete of a _healthcheck document.
4. Firebase Auth service availability.
5. Identity Toolkit REST API configuration (FIREBASE_WEB_API_KEY).

Never prints or logs secret contents, credentials, or private keys.
"""

import os
import sys
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()


def check_firebase():
    print("=== KickoffXI Firebase Environment & Connectivity Check ===")

    service_account_var = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON')
    gac_var = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    web_api_key = os.getenv('FIREBASE_WEB_API_KEY')
    auth_emulator = os.getenv('FIREBASE_AUTH_EMULATOR_HOST')
    firestore_emulator = os.getenv('FIRESTORE_EMULATOR_HOST')

    print(f"FIREBASE_SERVICE_ACCOUNT_JSON:  {'PRESENT' if service_account_var else 'ABSENT'}")
    print(f"GOOGLE_APPLICATION_CREDENTIALS: {'PRESENT' if gac_var else 'ABSENT'}")
    print(f"FIREBASE_WEB_API_KEY:          {'PRESENT' if web_api_key else 'ABSENT'}")
    print(f"FIRESTORE_EMULATOR_HOST:       {firestore_emulator or 'None (using live Firebase)'}")
    print(f"FIREBASE_AUTH_EMULATOR_HOST:   {auth_emulator or 'None (using live Firebase)'}")

    has_creds = bool(service_account_var or gac_var or auth_emulator or firestore_emulator)
    if not has_creds:
        print("\n[BLOCKED] Firebase Admin credentials are not configured locally.")
        print("To configure the development project:")
        print("  1. Save your Firebase service account JSON key to a safe folder outside the repository.")
        print("  2. In your local .env file, add:")
        print("     GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-service-account-key.json")
        print("     # OR")
        print("     FIREBASE_SERVICE_ACCOUNT_JSON=/path/to/your-service-account-key.json")
        if not web_api_key:
            print("  3. Set FIREBASE_WEB_API_KEY=your-web-api-key from Firebase Console (Project Settings -> General).")
        return False

    # Attempt to initialize Admin SDK
    try:
        from app.firebase_client import get_firebase_app, get_firestore_client, get_auth_module
        app = get_firebase_app()
        print("\n[OK] Firebase Admin SDK initialized successfully.")
    except Exception as e:
        print(f"\n[ERROR] Failed to initialize Firebase Admin SDK: {e}")
        return False

    # Verify Firestore read/write/delete
    try:
        db = get_firestore_client()
        check_id = f"check_{uuid.uuid4().hex[:8]}"
        doc_ref = db.collection('_healthcheck').document(check_id)

        # Write
        doc_ref.set({
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

        # Read
        snap = doc_ref.get()
        if not snap.exists:
            raise RuntimeError("Healthcheck document was written but could not be read back.")

        # Delete
        doc_ref.delete()
        print("[OK] Cloud Firestore read/write/delete check passed.")
    except Exception as e:
        print(f"[ERROR] Cloud Firestore connectivity failed: {e}")
        return False

    # Verify Auth module
    try:
        auth_mod = get_auth_module()
        # Test listing up to 1 user as a harmless API ping
        list(auth_mod.list_users(max_results=1).iterate_all())
        print("[OK] Firebase Admin Auth API responded successfully.")
    except Exception as e:
        print(f"[ERROR] Firebase Admin Auth API call failed: {e}")
        return False

    # Verify Web API Key for REST calls
    if not web_api_key and not auth_emulator:
        print("[WARNING] FIREBASE_WEB_API_KEY is not configured. REST authentication (signIn/reset) requires this key.")
        return False
    else:
        print("[OK] Firebase Web API Key is present.")

    print("\n[SUCCESS] All Firebase checks passed successfully.")
    return True


if __name__ == '__main__':
    success = check_firebase()
    if not success:
        sys.exit(1)

