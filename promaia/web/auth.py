"""
Authentication middleware for the Promaia web dashboard.

Simple token-based auth for a single-user personal system:
- Browser sessions: cookie set after login with username/password
- API access: Bearer token in Authorization header
- Login page shown for unauthenticated browser requests

Env vars:
    DASHBOARD_USERNAME  -- login username (default: "admin")
    DASHBOARD_PASSWORD  -- login password (REQUIRED for auth to activate)
    DASHBOARD_SECRET    -- secret key for signing cookies (auto-generated if not set)
    DASHBOARD_AUTH_TOKEN -- optional static Bearer token for API access
"""
import hashlib
import hmac
import logging
import os
import time
from urllib.parse import quote

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, JSONResponse

logger = logging.getLogger(__name__)

# Cookie name and max age (30 days)
COOKIE_NAME = "promaia_session"
COOKIE_MAX_AGE = 30 * 24 * 60 * 60

# Paths that don't require authentication
PUBLIC_PATHS = {"/login", "/api/health", "/telegram/webhook"}


def _get_secret() -> str:
    """Return the signing secret, generating one if not configured."""
    secret = os.environ.get("DASHBOARD_SECRET", "")
    if not secret:
        # Generate a stable secret from the password so it survives restarts
        password = os.environ.get("DASHBOARD_PASSWORD", "")
        if password:
            secret = hashlib.sha256(f"promaia-session-{password}".encode()).hexdigest()
        else:
            secret = "no-auth-configured"
    return secret


def _sign_token(username: str, expires: int) -> str:
    """Create a signed session token: username|expires|signature."""
    secret = _get_secret()
    payload = f"{username}|{expires}"
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload}|{sig}"


def _verify_token(token: str) -> str | None:
    """Verify a session token. Returns username if valid, None otherwise."""
    try:
        parts = token.split("|")
        if len(parts) != 3:
            return None
        username, expires_str, sig = parts
        expires = int(expires_str)
        if time.time() > expires:
            return None
        secret = _get_secret()
        expected = hmac.new(
            secret.encode(), f"{username}|{expires_str}".encode(), hashlib.sha256
        ).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            return None
        return username
    except Exception:
        return None


def create_session_cookie(username: str) -> str:
    """Create a signed session cookie value."""
    expires = int(time.time()) + COOKIE_MAX_AGE
    return _sign_token(username, expires)


def verify_credentials(username: str, password: str) -> bool:
    """Check if the provided credentials match the configured ones."""
    expected_user = os.environ.get("DASHBOARD_USERNAME", "admin")
    expected_pass = os.environ.get("DASHBOARD_PASSWORD", "")
    if not expected_pass:
        return False
    return (
        hmac.compare_digest(username, expected_user)
        and hmac.compare_digest(password, expected_pass)
    )


def is_auth_enabled() -> bool:
    """Auth is enabled only when DASHBOARD_PASSWORD is set."""
    return bool(os.environ.get("DASHBOARD_PASSWORD", ""))


class DashboardAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces authentication on all routes except PUBLIC_PATHS.

    If auth is not configured (no DASHBOARD_PASSWORD), all requests pass through.
    """

    async def dispatch(self, request: Request, call_next):
        # If auth is not enabled, pass everything through
        if not is_auth_enabled():
            return await call_next(request)

        path = request.url.path

        # Allow public paths
        if path in PUBLIC_PATHS:
            return await call_next(request)

        # Allow static files (CSS, JS, images)
        if path.startswith("/static/"):
            return await call_next(request)

        # Check Bearer token (for API/programmatic access)
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            # Check against static API token
            api_token = os.environ.get("DASHBOARD_AUTH_TOKEN", "")
            if api_token and hmac.compare_digest(token, api_token):
                return await call_next(request)
            # Also check if it's a valid session token
            if _verify_token(token):
                return await call_next(request)
            # API requests get 401, not redirect
            if path.startswith("/api/"):
                return JSONResponse(
                    {"detail": "Invalid or expired token"}, status_code=401
                )

        # Check session cookie
        session_cookie = request.cookies.get(COOKIE_NAME)
        if session_cookie:
            username = _verify_token(session_cookie)
            if username:
                return await call_next(request)

        # Not authenticated
        if path.startswith("/api/"):
            return JSONResponse(
                {"detail": "Authentication required"}, status_code=401
            )

        # Redirect browser to login, preserving the original URL
        redirect_to = quote(str(request.url.path), safe="")
        return RedirectResponse(
            url=f"/login?next={redirect_to}", status_code=303
        )
