import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

def _today_str() -> str:
    """Returns today's date in YYYY-MM-DD format based on local timezone (assumed PT for user)."""
    return datetime.now().astimezone().strftime('%Y-%m-%d')

def _days_ago(days: int) -> str:
    """Returns the date in YYYY-MM-DD format for N days ago."""
    dt = datetime.now() - timedelta(days=days)
    return dt.strftime('%Y-%m-%d')

def _fmt_ts(ts) -> str:
    """Format a timestamp into a friendly relative or absolute string."""
    if not ts:
        return "Unknown"
    
    # If it's already a string, try to parse it
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        except ValueError:
            return ts
            
    # Ensure it's timezone-aware for comparison
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
        
    now = datetime.now(timezone.utc)
    diff = now - ts
    
    if diff.total_seconds() < 3600:
        mins = int(diff.total_seconds() / 60)
        return f"{mins}m ago"
    elif diff.total_seconds() < 86400:
        hours = int(diff.total_seconds() / 3600)
        return f"{hours}h ago"
    elif diff.days < 7:
        return f"{diff.days}d ago"
    else:
        return ts.strftime("%Y-%m-%d")

def _get_or_create_domain_id(db, domain_name: str) -> int:
    """Lookup a domain ID by name; create if not exists."""
    if not domain_name:
        return None
        
    # Check if exists
    row = db.fetch_one("SELECT id FROM brain.domains WHERE name = %s", (domain_name,))
    if row:
        return row['id']
        
    # Create if not
    db.execute(
        "INSERT INTO brain.domains (name, description) VALUES (%s, %s)",
        (domain_name, f"Auto-created domain for {domain_name}")
    )
    # Fetch the new ID
    row = db.fetch_one("SELECT id FROM brain.domains WHERE name = %s", (domain_name,))
    return row['id'] if row else None
