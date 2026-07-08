import json
import urllib.parse
import urllib.request

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def get_google_auth_url(
    client_id: str, redirect_uri: str, state: str = ""
) -> str:
    """Generates the Google OAuth2 authorization URL to redirect users to."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(
    client_id: str, client_secret: str, redirect_uri: str, code: str
) -> dict:
    """Exchanges the authorization code for an access token and ID token."""
    data = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        GOOGLE_TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_info = e.read().decode("utf-8")
        raise RuntimeError(f"Failed to exchange code: {error_info}") from e


def get_user_info(access_token: str) -> dict:
    """Fetches user profile information from Google using the access token."""
    req = urllib.request.Request(GOOGLE_USERINFO_URL)
    req.add_header("Authorization", f"Bearer {access_token}")
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_info = e.read().decode("utf-8")
        raise RuntimeError(f"Failed to fetch user info: {error_info}") from e


def login(
    client_id: str, client_secret: str, redirect_uri: str, code: str
) -> dict:
    """Performs the full login workflow by exchanging the authorization code

    and retrieving the user profile information.
    """
    tokens = exchange_code_for_tokens(
        client_id, client_secret, redirect_uri, code
    )
    access_token = tokens.get("access_token")
    if not access_token:
        raise ValueError("No access_token found in token response.")
    user_info = get_user_info(access_token)
    return {"tokens": tokens, "user_info": user_info}
