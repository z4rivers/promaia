"""
Production configuration for the Promaia web server.

Reads environment variables with sensible defaults for both
local development and cloud deployment (Railway, Render, etc.).
"""
import os


def get_config() -> dict:
    """Return a dict of web server configuration."""
    return {
        # Server binding
        "host": os.environ.get("HOST", "0.0.0.0"),
        "port": int(os.environ.get("PORT", "8000")),
        # CORS -- comma-separated origins, or "*" for dev
        "cors_origins": _parse_cors_origins(),
        # Trusted hosts (for reverse proxy setups)
        "trusted_hosts": _parse_list("TRUSTED_HOSTS", default="*"),
        # Auth
        "auth_enabled": bool(os.environ.get("DASHBOARD_PASSWORD")),
        # Telegram webhook
        "telegram_webhook_url": os.environ.get("TELEGRAM_WEBHOOK_URL", ""),
        # Environment
        "environment": os.environ.get("PYTHON_ENV", "development"),
    }


def _parse_cors_origins() -> list[str]:
    """Parse CORS_ORIGINS env var into a list."""
    raw = os.environ.get("CORS_ORIGINS", "")
    if not raw:
        # Default: allow common local + production origins
        return [
            "https://zbrain.online",
            "http://localhost:5174",
            "http://localhost:8000",
            "https://www.koiib.com",
        ]
    if raw.strip() == "*":
        if os.environ.get("PYTHON_ENV") == "production":
            return ["https://zbrain.online"]
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


def _parse_list(env_var: str, default: str = "") -> list[str]:
    """Parse a comma-separated env var into a list."""
    raw = os.environ.get(env_var, default)
    if raw.strip() == "*":
        return ["*"]
    return [item.strip() for item in raw.split(",") if item.strip()]
