"""Verify Google OAuth access tokens via the userinfo endpoint."""
import urllib.request
import urllib.error
import json


USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def verify_google_token(access_token: str) -> dict | None:
    """
    Calls Google's userinfo endpoint with the access token.
    Returns: {"sub", "email", "name", "picture"} on success, None on failure.

    Token must have the 'userinfo.email' / 'userinfo.profile' / 'openid' scope.
    """
    if not access_token:
        return None
    try:
        req = urllib.request.Request(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        # Required fields
        if not data.get("sub") or not data.get("email"):
            return None
        return {
            "sub": data["sub"],
            "email": data["email"],
            "name": data.get("name"),
            "picture": data.get("picture"),
        }
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, TimeoutError) as e:
        print(f"Auth verification failed: {e}")
        return None