"""Guest-mode auth — lets evaluators try Notschool without a Google account.

Tokens are HMAC-signed so the server can verify a guest is who they claim to be
without keeping per-session state. Calendar features stay disabled because the
guest never grants Google Calendar scope; everything else (roadmap, quizzes,
doubts, dashboard) works end-to-end.
"""
import base64
import hashlib
import hmac
import os
import secrets
from typing import Optional


GUEST_PREFIX = "guest:"
_DEFAULT_SECRET = "notschool-guest-fallback-secret-do-not-use-in-prod"


def _secret() -> bytes:
    return (os.getenv("GUEST_TOKEN_SECRET") or _DEFAULT_SECRET).encode("utf-8")


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64u_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(payload: bytes) -> str:
    sig = hmac.new(_secret(), payload, hashlib.sha256).digest()
    return _b64u(sig)


def issue_guest_token(name: Optional[str] = None) -> dict:
    """Mint a new guest identity + token. The user_id is unique per call so
    each evaluator gets their own sandbox.
    """
    raw_id = secrets.token_urlsafe(9)
    user_id = f"guest_{raw_id}"
    payload = user_id.encode("utf-8")
    sig = _sign(payload)
    token = f"{GUEST_PREFIX}{_b64u(payload)}.{sig}"
    display = (name or "").strip()[:40] or "Guest Evaluator"
    return {
        "token": token,
        "user_id": user_id,
        "email": f"{user_id}@guest.notschool.local",
        "name": display,
        "picture": None,
    }


def verify_guest_token(token: str) -> Optional[dict]:
    """Return guest user info if the token is valid, else None.

    Token format: `guest:<b64url(user_id)>.<b64url(hmac)>`.
    """
    if not token or not token.startswith(GUEST_PREFIX):
        return None
    body = token[len(GUEST_PREFIX):]
    if "." not in body:
        return None
    payload_b64, sig_b64 = body.split(".", 1)
    try:
        payload = _b64u_decode(payload_b64)
    except (ValueError, base64.binascii.Error):
        return None
    expected = _sign(payload)
    if not hmac.compare_digest(expected, sig_b64):
        return None
    try:
        user_id = payload.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not user_id.startswith("guest_"):
        return None
    return {
        "sub": user_id,
        "email": f"{user_id}@guest.notschool.local",
        "name": "Guest Evaluator",
        "picture": None,
    }


def is_guest_token(token: Optional[str]) -> bool:
    return bool(token) and token.startswith(GUEST_PREFIX)
