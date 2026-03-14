import os
import contextlib
from typing import Generator, Any

from .postgres_db import get_postgres_db, pg_connect
from .libsql_db import LibSQLDB, get_libsql_db, libsql_connect

def get_db() -> Any:
    """
    Factory function to return the active database client based on environment variable.
    Returns either a PostgresDB or LibSQLDB instance.
    """
    backend = os.getenv("STORE_BACKEND", "postgres").lower()
    if backend == "libsql":
        return get_libsql_db()
    return get_postgres_db()

@contextlib.contextmanager
def db_connect() -> Generator[Any, None, None]:
    """
    Factory context manager to yield an active database connection.
    Yields either a psycopg2 connection or a libsql connection.
    """
    backend = os.getenv("STORE_BACKEND", "postgres").lower()
    if backend == "libsql":
        with libsql_connect() as conn:
            yield conn
    else:
        with pg_connect() as conn:
            yield conn
