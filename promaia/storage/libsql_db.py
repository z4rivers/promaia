import os
from pathlib import Path
import contextlib
import logging
import json
import time
import sqlite3 as libsql
import sqlite_vec
from typing import Optional, Any, Tuple, Generator, List, Dict
logger = logging.getLogger(__name__)

class SmartRow(dict):
    """Dict-like row that also supports integer indexing (row[0])."""
    
    def __init__(self, data: dict):
        super().__init__(data)
        self._values = list(data.values())
    
    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


def parse_smart_data(row: tuple, description: tuple) -> 'SmartRow':
    """Auto-deserialize JSON and coerce booleans. Returns SmartRow (dict + index access)."""
    if not row or not description:
        return SmartRow({})
        
    result = {}
    for i, col in enumerate(description):
        name = col[0]
        val = row[i]
        
        # Boolean coercion (SQLite returns 1/0 for booleans, Python true/false)
        if val == 1 and ('is_' in name or 'has_' in name or 'can_' in name or 'should_' in name or 'featured' == name or 'boolean' in str(type(val)).lower()):
            val = True
        elif val == 0 and ('is_' in name or 'has_' in name or 'can_' in name or 'should_' in name or 'featured' == name):
            val = False
            
        # JSON parsing
        if isinstance(val, str) and len(val) >= 2:
            if (val.startswith('{') and val.endswith('}')) or (val.startswith('[') and val.endswith(']')):
                try:
                    val = json.loads(val)
                except json.JSONDecodeError:
                    pass # Not valid JSON, keep as string
                    
        result[name] = val
    return SmartRow(result)

class LibSQLCursorWrapper:
    def __init__(self, conn_wrapper):
        self._conn_wrapper = conn_wrapper
        self._cursor = None
        self.description = None
        self.rowcount = -1

    def execute(self, query: str, params: Optional[Tuple] = None):
        # Convert %s placeholders to sqlite ? placeholders
        query = query.replace('%s', '?')
        
        # Exponential backoff retry loop for SQLite locks
        max_retries = 5
        base_delay = 0.05
        
        for attempt in range(max_retries):
            try:
                if params:
                    self._cursor = self._conn_wrapper._conn.execute(query, params)
                else:
                    self._cursor = self._conn_wrapper._conn.execute(query)
                self.description = self._cursor.description
                
                # libSQL returns tuples, set rowcount gracefully
                self.rowcount = getattr(self._cursor, 'rowcount', 1) 
                
                # Auto-commit only for write operations (SELECT doesn't need commit
                # and will error with "SQL statements in progress" if cursor isn't consumed)
                query_upper = query.strip().upper()
                is_write = query_upper.startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER', 'PRAGMA'))
                if is_write:
                    try:
                        self._conn_wrapper._conn.commit()
                    except (ValueError, Exception) as e:
                        if "SQL statements in progress" not in str(e):
                            raise
                return self
            except Exception as e:
                err_str = str(e).lower()
                if "database is locked" in err_str or "busy" in err_str:
                    if attempt < max_retries - 1:
                        sleep_time = base_delay * (2 ** attempt)
                        logger.warning(f"Database locked, retrying in {sleep_time}s (attempt {attempt+1}/{max_retries})")
                        time.sleep(sleep_time)
                        continue
                raise

    def executemany(self, query: str, params_list: List[tuple]):
        query = query.replace('%s', '?')
        rowcount = 0
        for params in params_list:
            self.execute(query, params)
            rowcount += 1
        self.rowcount = rowcount
        return self

    def fetchone(self):
        if not self._cursor: return None
        row = self._cursor.fetchone()
        if not row: return None
        return parse_smart_data(row, self.description)

    def fetchall(self):
        if not self._cursor: return []
        rows = self._cursor.fetchall()
        return [parse_smart_data(row, self.description) for row in rows]

    def close(self):
        pass

class LibSQLConnectionWrapper:
    def __init__(self, conn: libsql.Connection):
        self._conn = conn
        self.autocommit = False
        
    def cursor(self, cursor_factory=None):
        # Ignore cursor_factory because we always return dicts via parse_smart_data
        return LibSQLCursorWrapper(self)
        
    def commit(self):
        self._conn.commit()
        
    def rollback(self):
        # No native rollback method on libsql-experimental Connection
        pass

class LibSQLDB:
    def __init__(self, db_path: str = "promaia.db"):
        self.db_path = db_path
        self._conn: Optional[libsql.Connection] = None
        self._wrapped_conn: Optional[LibSQLConnectionWrapper] = None
        self._init_connection()

    def _init_connection(self):
        try:
            self._conn = libsql.connect(self.db_path, check_same_thread=False)
            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
            self._conn.enable_load_extension(False)
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            self._wrapped_conn = LibSQLConnectionWrapper(self._conn)
            logger.info(f"Connected to local libSQL database at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to connect to libSQL database: {str(e)}")
            raise

    @contextlib.contextmanager
    def get_connection(self):
        yield self._wrapped_conn

    @contextlib.contextmanager
    def get_cursor(self, cursor_factory=None):
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            yield cursor

    @contextlib.contextmanager
    def get_dict_cursor(self):
        with self.get_cursor() as cursor:
            yield cursor

    def execute(self, query: str, params: Optional[Tuple] = None) -> int:
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount

    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        with self.get_cursor() as cursor:
            cursor.executemany(query, params_list)
            return cursor.rowcount

    def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()

    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
            
    def insert_returning(self, query: str, params: tuple = None) -> Optional[Any]:
        # SQLite natively supports RETURNING clause in modern versions
        query = query.replace('%s', '?')
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            if cursor._cursor:
                res = cursor._cursor.fetchone()
                return res[0] if res else None
            return None

    def upsert(self, table: str, data: Dict[str, Any], 
               conflict_columns: List[str],
               update_columns: List[str] = None) -> bool:
        columns = list(data.keys())
        values = list(data.values())
        if update_columns is None:
            update_columns = [c for c in columns if c not in conflict_columns]
            
        col_str = ', '.join(columns)
        val_placeholders = ', '.join(['?'] * len(values))
        conflict_str = ', '.join(conflict_columns)
        
        if update_columns:
            update_str = ', '.join([f"{c} = EXCLUDED.{c}" for c in update_columns])
            query = f"INSERT INTO {table} ({col_str}) VALUES ({val_placeholders}) ON CONFLICT ({conflict_str}) DO UPDATE SET {update_str}"
        else:
            query = f"INSERT INTO {table} ({col_str}) VALUES ({val_placeholders}) ON CONFLICT ({conflict_str}) DO NOTHING"
            
        self.execute(query, tuple(values))
        return True

    def table_exists(self, table_name: str) -> bool:
        query = "SELECT EXISTS(SELECT name FROM sqlite_master WHERE type='table' AND name=?)"
        res = self.fetch_one(query, (table_name,))
        if res:
            return list(res.values())[0] == 1
        return False

    def column_exists(self, table_name: str, column_name: str) -> bool:
        query = f"PRAGMA table_info({table_name})"
        columns = self.fetch_all(query)
        for col in columns:
            if col.get('name') == column_name:
                return True
        return False

    def close(self):
        pass
        
    def close_pool(self):
        pass

# ---------------------------------------------------------------------------
# Resolve the canonical database path: always relative to the project root
# (this file lives at promaia/storage/libsql_db.py → project root is 2 up)
# This prevents the MCP server (spawned by the IDE with an unknown cwd)
# from creating a ghost database in the wrong directory.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DB_PATH = str(_PROJECT_ROOT / "promaia.db")

# Global instance
_db_instance = None

def get_libsql_db(db_path: str = None) -> LibSQLDB:
    global _db_instance
    if _db_instance is None:
        resolved = db_path or _DEFAULT_DB_PATH
        _db_instance = LibSQLDB(resolved)
    return _db_instance

@contextlib.contextmanager
def libsql_connect(db_path: str = None):
    db = get_libsql_db(db_path)
    with db.get_connection() as conn:
        yield conn
