import os
import contextlib
from typing import Generator, Any

from .libsql_db import LibSQLDB, get_libsql_db, libsql_connect


def get_db() -> LibSQLDB:
    """Return the active database client (libSQL)."""
    return get_libsql_db()


@contextlib.contextmanager
def db_connect() -> Generator[Any, None, None]:
    """Yield an active libSQL database connection."""
    with libsql_connect() as conn:
        yield conn
