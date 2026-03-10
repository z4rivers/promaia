import uuid
from promaia.storage.postgres_db import get_postgres_db
from promaia.storage.vector_db import VectorDBManager
from promaia.brain.muninn import get_muninn

SESSION_ID = str(uuid.uuid4())

_db = None
_vector_manager = None

def get_db():
    global _db
    if _db is None:
        _db = get_postgres_db()
    return _db

def get_vector_mgr():
    global _vector_manager
    if _vector_manager is None:
        _vector_manager = VectorDBManager()
    return _vector_manager

async def get_muninn_client():
    return await get_muninn()
