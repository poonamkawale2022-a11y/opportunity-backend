"""Gmail integration: OAuth2 + draft/send/list/get. Graceful demo fallback."""
from __future__ import annotations

import base64
import time
from email.message import EmailMessage
from typing import Optional

from .config import get_settings
from .store import col


def status(user_id: str = "demo-user") -> dict:
    s = get_settings()
    row = col("integrations").find_one({"user_id": user_id, "provider": "gmail"})
    configured = bool(s.GOOGLE_CLIENT_ID and s.GOOGLE_CLIENT_SECRET)
    if row and row.get("refresh_token"):
        return {"connected": True, "mode": "oauth",
                "email": row.get("email", ""),
                "configured": configured}
    if configured:
        return {"connected": False, "mode": "oauth-ready",
                "message": "OAuth configured — user must connect Gmail."}
    return {"connected": False, "mode": "draft-only",
            "message": "Gmail OAuth not configured. Drafts can be copied/downloaded as .eml."}


def auth_url(user_id: str = "demo-user", state: str = "") -> dict:
    s = get_settings()
    if not (s.GOOGLE_CLIENT_ID and s.GOOGLE_REDIRECT_URI):
        return {"ok": False, "error": "GOOGLE_CLIENT_ID/GOOGLE_REDIRECT_URI not configured"}
    from urllib.parse import urlencode

    q = urlencode({
        "client_id": s.GOOGLE_CLIENT_ID,
        "redirect_uri": s.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly",
        "access_type": "offline", "prompt": "consent",
        "state": state or user_id,
    })
    return {"ok": True, "url": f"https://accounts.google.com/o/oauth2/v2/auth?{q}"}


def oauth_callback(code: str, user_id: str = "demo-user") -> dict:
    s = get_settings()
    try:
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            {"web": {"client_id": s.GOOGLE_CLIENT_ID,
                     "client_secret": s.GOOGLE_CLIENT_SECRET,
                     "redirect_uris": [s.GOOGLE_REDIRECT_URI],
                     "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                     "token_uri": "https://oauth2.googleapis.com/token"}},
            scopes=["https://www.googleapis.com/auth/gmail.send",
                    "https://www.googleapis.com/auth/gmail.readonly"],
            redirect_uri=s.GOOGLE_REDIRECT_URI)
        flow.fetch_token(code=code)
        creds = flow.credentials
        col("integrations").upsert(
            {"user_id": user_id, "provider": "gmail"},
            {"user_id": user_id, "provider": "gmail",
             "refresh_token": creds.refresh_token or "",
             "token": creds.token or "", "updated_at": time.time()})
        return {"ok": True, "connected": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _service(user_id: str = "demo-user"):
    row = col("integrations").find_one({"user_id": user_id, "provider": "gmail"})
    s = get_settings()
    if not row or not row.get("refresh_token"):
        raise RuntimeError("Gmail not connected")
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(token=row.get("token"), refresh_token=row.get("refresh_token"),
                        client_id=s.GOOGLE_CLIENT_ID,
                        client_secret=s.GOOGLE_CLIENT_SECRET,
                        token_uri="https://oauth2.googleapis.com/token")
    return build("gmail", "v1", credentials=creds)


def build_eml(to: str, subject: str, body: str, sender: str = "me") -> str:
    msg = EmailMessage()
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    return msg.as_string()


def create_draft(user_id: str, to: str, subject: str, body: str) -> dict:
    st = status(user_id)
    if not st.get("connected"):
        eml = build_eml(to, subject, body)
        return {"ok": True, "mode": "local-draft", "eml": eml,
                "message": "Draft ready — connect Gmail to send."}
    try:
        raw = base64.urlsafe_b64encode(build_eml(to, subject, body).encode()).decode()
        svc = _service(user_id)
        d = svc.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
        return {"ok": True, "mode": "gmail-draft", "draft_id": d.get("id"),
                "message_id": (d.get("message") or {}).get("id", "")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def send_message(user_id: str, to: str, subject: str, body: str) -> dict:
    st = status(user_id)
    if not st.get("connected"):
        return {"ok": False, "error": "Gmail not connected — draft only",
                "mode": "draft-only"}
    try:
        raw = base64.urlsafe_b64encode(build_eml(to, subject, body).encode()).decode()
        svc = _service(user_id)
        m = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"ok": True, "message_id": m.get("id", ""),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    except Exception as e:
        return {"ok": False, "error": str(e)}
