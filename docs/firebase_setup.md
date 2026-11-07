# KickoffXI — Firebase Configuration and Deployment Guide

This document describes how to configure Firebase Authentication and Cloud Firestore for the KickoffXI application in development and production environments.

> **CRITICAL SECURITY NOTE:** Never commit service account keys, private API keys, or credentials to version control. Always keep key files outside the Git repository or in secure deployment secret managers.

---

## 1. Firebase Project Overview

- **Project ID:** `KickoffXI` (Development environment)
- **Authentication:** Email/Password provider enabled. Email enumeration protection enabled.
- **Database:** Cloud Firestore in Singapore (`asia-southeast1`).
- **Security Architecture:** Server-side only via Firebase Admin SDK and Identity Toolkit REST. Direct client SDK access is completely blocked via security rules.

---

## 2. Local Development Configuration

### Step A: Service Account Key (Admin SDK)
1. In the Firebase Console, navigate to **Project settings** → **Service accounts**.
2. Click **Generate new private key** and download the JSON file.
3. Save the JSON file to a directory **outside the repository** (e.g. `C:\Users\<user>\.firebase\kickoffxi-adminsdk.json` or `/etc/secrets/kickoffxi-adminsdk.json`).
4. Configure either of the following in your local `.env`:
   ```bash
   # Option 1: File path
   GOOGLE_APPLICATION_CREDENTIALS=/path/to/kickoffxi-adminsdk.json
   # OR
   FIREBASE_SERVICE_ACCOUNT_JSON=/path/to/kickoffxi-adminsdk.json
   ```

### Step B: Web API Key (Identity Toolkit REST)
1. In the Firebase Console, navigate to **Project settings** → **General** tab.
2. Locate the **Web API Key**.
3. In your local `.env`, set:
   ```bash
   FIREBASE_WEB_API_KEY=your-web-api-key-here
   ```

### Step C: Application Base URL & Session Settings
In your local `.env`:
```bash
APP_BASE_URL=http://localhost:5000
AUTH_SESSION_COOKIE_NAME=kxi_session
AUTH_REMEMBER_DAYS=14
AUTH_SHORT_SESSION_HOURS=12
```

---

## 3. Render Production Deployment (Future Reference)

When ready for production deployment (under a separate, authorized production Firebase project):

### Option A: Secret File (Recommended on Render)
1. In Render Dashboard, go to your Web Service → **Environment**.
2. Under **Secret Files**, add:
   - **Filename:** `firebase-adminsdk.json`
   - **Contents:** Paste the contents of your production service-account JSON key.
3. Render places secret files at `/etc/secrets/firebase-adminsdk.json`.
4. In **Environment Variables**, set:
   ```bash
   GOOGLE_APPLICATION_CREDENTIALS=/etc/secrets/firebase-adminsdk.json
   ```

### Option B: Environment Variable
Alternatively, set the raw JSON content as an environment variable in Render:
```bash
FIREBASE_SERVICE_ACCOUNT_JSON={"type": "service_account", ...}
```
The application's `firebase_client.py` detects whether `FIREBASE_SERVICE_ACCOUNT_JSON` is a file path or a raw JSON string and parses accordingly.

### Production Environment Variables in Render:
| Variable Name | Value / Description |
|---|---|
| `FLASK_CONFIG` | `production` |
| `SECRET_KEY` | Managed by Render (`generateValue: true`) |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | File path or raw JSON string |
| `FIREBASE_WEB_API_KEY` | Production Web API Key |
| `APP_BASE_URL` | `https://your-app-name.onrender.com` |
| `MAIL_USERNAME` | Production Gmail / SMTP address |
| `MAIL_PASSWORD` | 16-character Google App Password |

---

## 4. Firebase Console Configuration

### Authorized Domains
Ensure the following domains are registered under **Firebase Console → Authentication → Settings → Authorized domains**:
- `localhost`
- `127.0.0.1`
- `your-app-name.onrender.com` (Render domain)
- Custom domain (if applicable)

### Deploying Firestore Security Rules
All client-side access is blocked. Deploy the rules from the repository root:
```bash
firebase deploy --only firestore:rules
```
Or paste the contents of `firestore.rules` directly into **Firebase Console → Firestore Database → Rules**:
```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

