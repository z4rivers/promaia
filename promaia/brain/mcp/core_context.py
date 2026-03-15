from promaia.storage.db_factory import get_db as _get_db_factory
from promaia.storage.vector_db import VectorDBManager
from promaia.brain.muninn import get_muninn

# Stable process-level identifier for event logging and memory capture.
# Previously a random UUID per stdio session — now fixed because the daemon
# is always-on. MCP transport manages per-client session IDs separately.
SESSION_ID = "brain-daemon"

_db = None
_vector_manager = None

def get_db():
    global _db
    if _db is None:
        _db = _get_db_factory()
    return _db

def get_vector_mgr():
    global _vector_manager
    if _vector_manager is None:
        _vector_manager = VectorDBManager()
    return _vector_manager

async def get_muninn_client():
    return await get_muninn()
