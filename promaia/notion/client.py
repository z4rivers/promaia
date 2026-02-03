"""
Notion API client initialization and configuration.
"""
import os
try:
    from dotenv import load_dotenv  # type: ignore
except ImportError:  # pragma: no cover
    load_dotenv = None  # type: ignore[assignment]

# notion_client is optional in some environments (e.g. minimal schedulers/tests).
# Importing it at module import time makes *any* promaia import fail if the
# dependency isn't installed. Keep imports resilient; raise only when used.
try:
    from notion_client import AsyncClient  # type: ignore
except ImportError:  # pragma: no cover
    AsyncClient = None  # type: ignore[assignment]

# Load environment variables (optional dependency)
if load_dotenv is not None:  # pragma: no cover
    load_dotenv()

def get_client(workspace: str = None):
    """Initialize and return an async Notion client for a specific workspace."""
    if AsyncClient is None:  # pragma: no cover
        raise ImportError(
            "notion_client is not installed. Install it to use Notion features "
            "(e.g. `pip install notion-client`)."
        )

    # Try to get workspace-specific API key first
    if workspace:
        from promaia.config.workspaces import get_workspace_api_key
        notion_token = get_workspace_api_key(workspace)
        if notion_token:
            return AsyncClient(auth=notion_token)
    
    # If no workspace specified, try to use default workspace
    if not workspace:
        from promaia.config.workspaces import get_default_workspace, get_workspace_api_key
        default_workspace = get_default_workspace()
        if default_workspace:
            notion_token = get_workspace_api_key(default_workspace)
            if notion_token:
                return AsyncClient(auth=notion_token)
    
    # Fall back to environment variable
    notion_token = os.getenv("NOTION_TOKEN")
    if not notion_token:
        raise ValueError("NOTION_TOKEN environment variable not found and no workspace API key available. Please add it to your .env file or configure workspaces.")
    
    return AsyncClient(auth=notion_token)

def get_client_for_database(database_name: str):
    """Get a Notion client configured for a specific database's workspace."""
    from promaia.config.databases import get_database_config
    
    db_config = get_database_config(database_name)
    if db_config and db_config.workspace:
        return get_client(db_config.workspace)
    
    # Fall back to default client
    return get_client()

# Legacy support - use default workspace
def get_default_client():
    """Get a client using the default workspace."""
    return get_client()

# Create the default client lazily to avoid import-time errors
notion_client = None

def ensure_default_client():
    """Ensure the default client is initialized."""
    global notion_client
    if notion_client is None:
        notion_client = get_default_client()
    return notion_client 