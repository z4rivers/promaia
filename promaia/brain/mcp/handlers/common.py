import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def _get_or_create_domain_id(db, domain_name: str) -> int:
    existing = db.fetch_one("SELECT id FROM domains WHERE name = ?", (domain_name,))
    if existing: return existing['id']
    return db.insert_returning("INSERT INTO domains (name) VALUES (?) RETURNING id", (domain_name,))

def _days_ago(ts) -> float:
    if ts is None: return 0.0
    now = datetime.now(timezone.utc)
    if isinstance(ts, str):
        try: ts = datetime.fromisoformat(ts)
        except ValueError: return 0.0
    if getattr(ts, 'tzinfo', None) is None: ts = ts.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds() / 86400.0

def _fmt_ts(ts) -> str:
    if ts is None: return "unknown"
    if isinstance(ts, str):
        try: ts = datetime.fromisoformat(ts)
        except ValueError: return str(ts)
    if getattr(ts, 'tzinfo', None) is None: ts = ts.replace(tzinfo=timezone.utc)
    return ts.strftime("%Y-%m-%d %H:%M UTC")

def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

