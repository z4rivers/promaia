"""
PostgreSQL Database Manager for Promaia.

Provides centralized PostgreSQL connection management with connection pooling,
replacing both Supabase and SQLite storage across the application.

Supabase connection: Use DATABASE_URL env var (session pooler required on Windows
due to IPv6 issues with direct connections). SSL is required for Supabase cloud.
Session pooler URL format:
  postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres
"""
import os
import json
import logging
import threading
from contextlib import contextmanager
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from urllib.parse import urlparse

import psycopg2
from psycopg2 import pool, sql, extras

from promaia.utils.config import load_environment

logger = logging.getLogger(__name__)

# Supabase project session pooler hostname (used as default host when no env vars set)
SUPABASE_POOLER_HOST = 'aws-1-us-east-1.pooler.supabase.com'
SUPABASE_PROJECT_REF = 'jbcspnoqvtvvddifuhth'


class PostgresDB:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure single connection pool."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self,
                 host: str = None,
                 port: int = None,
                 database: str = None,
                 user: str = None,
                 password: str = None,
                 min_connections: int = 1,
                 max_connections: int = 10):

        if self._initialized:
            return

        load_environment()

        self.min_connections = min_connections
        self.max_connections = max_connections
        self._pool = None
        self._database_url = None

        # Check for DATABASE_URL first (Supabase session pooler - preferred on Windows)
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            self._database_url = database_url
            # Parse URL to extract host/port/db for logging
            parsed = urlparse(database_url)
            self.host = parsed.hostname or SUPABASE_POOLER_HOST
            self.port = parsed.port or 5432
            self.database = (parsed.path or '/postgres').lstrip('/')
            self.user = parsed.username or f'postgres.{SUPABASE_PROJECT_REF}'
            self.password = parsed.password or ''
        else:
            # Fall back to individual environment variables
            self.host = host or os.getenv('POSTGRES_HOST', SUPABASE_POOLER_HOST)
            self.port = port or int(os.getenv('POSTGRES_PORT', '5432'))
            self.database = database or os.getenv('POSTGRES_DATABASE', 'postgres')
            self.user = user or os.getenv('POSTGRES_USER', f'postgres.{SUPABASE_PROJECT_REF}')
            self.password = password or os.getenv('POSTGRES_PASSWORD', '')

        self._initialize_pool()
        self._initialized = True

    def _initialize_pool(self):
        """Initialize the connection pool.

        Uses DATABASE_URL if set (Supabase session pooler), otherwise falls back
        to individual connection parameters with sslmode=require for Supabase cloud.
        """
        try:
            if self._database_url:
                # DATABASE_URL path: parse and add sslmode if not present
                dsn = self._database_url
                if 'sslmode' not in dsn:
                    dsn = dsn + ('&' if '?' in dsn else '?') + 'sslmode=require'
                self._pool = pool.ThreadedConnectionPool(
                    self.min_connections,
                    self.max_connections,
                    dsn=dsn,
                    connect_timeout=30
                )
                logger.info(f"PostgreSQL connection pool initialized via DATABASE_URL: {self.host}:{self.port}/{self.database}")
            else:
                # Individual params path: add sslmode=require for Supabase cloud
                self._pool = pool.ThreadedConnectionPool(
                    self.min_connections,
                    self.max_connections,
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                    sslmode='require',
                    connect_timeout=30
                )
                logger.info(f"PostgreSQL connection pool initialized: {self.host}:{self.port}/{self.database}")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):

        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self._pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, cursor_factory=None):
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
            finally:
                cursor.close()
    
    @contextmanager
    def get_dict_cursor(self):
        """Get a cursor that returns results as dictionaries."""
        with self.get_cursor(cursor_factory=extras.RealDictCursor) as cursor:
            yield cursor
    
    def execute(self, query: str, params: tuple = None) -> int:
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount
    
    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        with self.get_cursor() as cursor:
            cursor.executemany(query, params_list)
            return cursor.rowcount
    
    def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        with self.get_dict_cursor() as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone()
            return dict(result) if result else None
    
    def fetch_all(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        with self.get_dict_cursor() as cursor:
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def insert_returning(self, query: str, params: tuple = None) -> Optional[Any]:
        """
        Execute an INSERT query with RETURNING clause.
        
        Args:
            query: INSERT query with RETURNING clause
            params: Query parameters
            
        Returns:
            The returned value (usually id)
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone()
            return result[0] if result else None
    
    def upsert(self, table: str, data: Dict[str, Any], 
               conflict_columns: List[str],
               update_columns: List[str] = None) -> bool:

        columns = list(data.keys())
        values = list(data.values())
        
        if update_columns is None:
            update_columns = [c for c in columns if c not in conflict_columns]
        
        # Build query
        col_str = ', '.join(columns)
        val_placeholders = ', '.join(['%s'] * len(values))
        conflict_str = ', '.join(conflict_columns)
        
        if update_columns:
            update_str = ', '.join([f"{c} = EXCLUDED.{c}" for c in update_columns])
            query = f"""
                INSERT INTO {table} ({col_str})
                VALUES ({val_placeholders})
                ON CONFLICT ({conflict_str})
                DO UPDATE SET {update_str}
            """
        else:
            query = f"""
                INSERT INTO {table} ({col_str})
                VALUES ({val_placeholders})
                ON CONFLICT ({conflict_str})
                DO NOTHING
            """
        
        with self.get_cursor() as cursor:
            cursor.execute(query, values)
            return True
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            )
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, (table_name,))
            return cursor.fetchone()[0]
    
    def column_exists(self, table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table."""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = %s 
                AND column_name = %s
            )
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, (table_name, column_name))
            return cursor.fetchone()[0]
    
    def close(self):
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()
            logger.info("PostgreSQL connection pool closed")
    
    def __del__(self):
        """Cleanup on deletion."""
        self.close()


# Global instance getter
_postgres_db: Optional[PostgresDB] = None

def get_postgres_db() -> PostgresDB:
    """Get the global PostgreSQL database instance."""
    global _postgres_db
    if _postgres_db is None:
        _postgres_db = PostgresDB()
    return _postgres_db


def reset_postgres_db():
    """Reset the global PostgreSQL database instance (for testing)."""
    global _postgres_db
    if _postgres_db:
        _postgres_db.close()
    _postgres_db = None
    PostgresDB._instance = None


class PostgresQueryInterface:
    
    def __init__(self, user_id: str = "00000000-0000-0000-0000-000000000001"):
        """Initialize PostgreSQL query interface."""
        self.db = get_postgres_db()
        self.user_id = user_id
        logger.info(f"🐘 PostgresQueryInterface initialized for user {user_id[:8]}...")
    
    def query_content_for_chat(self, workspace: str, sources: List[str] = None, 
                              days: int = None, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Query content for chat interface - optimized for fast context loading."""
        try:
            logger.info(f"🔍 Querying PostgreSQL: workspace={workspace}, sources={sources}, days={days}")
            
            # Build base query
            query = """
                SELECT id, title, content, source_name, content_type, 
                       created_date, message_date, metadata
                FROM content_items
                WHERE user_id = %s
            """
            params = [self.user_id]
            
            # Filter by sources if specified
            if sources and len(sources) > 0:
                source_names = []
                for source in sources:
                    if ':' in source:
                        source_name = source.split(':')[0]
                        source_names.append(source_name)
                    else:
                        source_names.append(source)
                
                if len(source_names) == 1:
                    query += " AND source_name = %s"
                    params.append(source_names[0])
                else:
                    placeholders = ', '.join(['%s'] * len(source_names))
                    query += f" AND source_name IN ({placeholders})"
                    params.extend(source_names)
            
            # Filter by date range if specified
            if days and days > 0:
                query += " AND created_date >= CURRENT_DATE - INTERVAL '%s days'"
                params.append(days)
            
            # Order and limit
            query += " ORDER BY COALESCE(created_date, indexed_date) DESC LIMIT 1000"
            
            results = self.db.fetch_all(query, tuple(params))
            
            if not results:
                logger.info("📭 No content found matching criteria")
                return []
            
            # Transform to expected format
            transformed = []
            for item in results:
                t = {
                    'id': item['id'],
                    'title': item['title'],
                    'content': item['content'],
                    'source_database': item['source_name'],
                    'database_name': item['source_name'],
                    'content_type': item['content_type'],
                    'timestamp': item.get('created_date'),
                    'date_obj': None,
                    'metadata': item.get('metadata', {})
                }
                
                # Parse date
                if item.get('created_date'):
                    try:
                        if isinstance(item['created_date'], str):
                            t['date_obj'] = datetime.fromisoformat(item['created_date']).date()
                        else:
                            t['date_obj'] = item['created_date']
                    except:
                        pass
                elif item.get('message_date'):
                    try:
                        if isinstance(item['message_date'], str):
                            t['date_obj'] = datetime.fromisoformat(item['message_date']).date()
                        else:
                            t['date_obj'] = item['message_date']
                    except:
                        pass
                
                transformed.append(t)
            
            logger.info(f"Found {len(transformed)} items from PostgreSQL")
            return transformed
            
        except Exception as e:
            logger.error(f"PostgreSQL query failed: {e}")
            return []
    
    def natural_language_query(self, nl_prompt: str, workspace: str = None, 
                              database_names: List[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Process natural language query using PostgreSQL full-text search."""
        try:
            logger.info(f"🤖 Natural language query: '{nl_prompt[:50]}...'")
            
            # Build search query with PostgreSQL full-text search
            query = """
                SELECT id, title, content, source_name, content_type, 
                       created_date, message_date, metadata
                FROM content_items
                WHERE user_id = %s
            """
            params = [self.user_id]
            
            # Filter by database names if specified
            if database_names and len(database_names) > 0:
                if len(database_names) == 1:
                    query += " AND source_name = %s"
                    params.append(database_names[0])
                else:
                    placeholders = ', '.join(['%s'] * len(database_names))
                    query += f" AND source_name IN ({placeholders})"
                    params.extend(database_names)
            
            # Use ILIKE for text matching (can be upgraded to full-text search)
            search_term = f"%{nl_prompt}%"
            query += " AND (content ILIKE %s OR title ILIKE %s)"
            params.extend([search_term, search_term])
            
            query += " ORDER BY created_date DESC LIMIT 500"
            
            results = self.db.fetch_all(query, tuple(params))
            
            if not results:
                logger.info("📭 No content found for natural language query")
                return {}
            
            # Group results by source
            grouped = {}
            for item in results:
                source_name = item['source_name']
                if source_name not in grouped:
                    grouped[source_name] = []
                
                transformed = {
                    'id': item['id'],
                    'title': item['title'],
                    'content': item['content'],
                    'source_database': source_name,
                    'database_name': source_name,
                    'content_type': item['content_type'],
                    'timestamp': item.get('created_date'),
                    'date_obj': None,
                    'metadata': item.get('metadata', {})
                }
                
                if item.get('created_date'):
                    try:
                        if isinstance(item['created_date'], str):
                            transformed['date_obj'] = datetime.fromisoformat(item['created_date']).date()
                        else:
                            transformed['date_obj'] = item['created_date']
                    except:
                        pass
                
                grouped[source_name].append(transformed)
            
            total = sum(len(items) for items in grouped.values())
            logger.info(f"✅ Natural language query found {total} items across {len(grouped)} sources")
            return grouped
            
        except Exception as e:
            logger.error(f"❌ Natural language query failed: {e}")
            return {}
    
    def get_database_context(self, workspace: str) -> Dict[str, Any]:
        """Get database context information for workspace."""
        try:
            logger.info(f"📊 Getting database context for workspace: {workspace}")
            
            # Get counts by source
            query = """
                SELECT source_name, COUNT(*) as count
                FROM content_items
                WHERE user_id = %s
                GROUP BY source_name
            """
            results = self.db.fetch_all(query, (self.user_id,))
            
            source_counts = {r['source_name']: r['count'] for r in results}
            
            # Get total count
            total_query = "SELECT COUNT(*) as total FROM content_items WHERE user_id = %s"
            total_result = self.db.fetch_one(total_query, (self.user_id,))
            total_count = total_result['total'] if total_result else 0
            
            context = {
                'workspace': workspace,
                'total_items': total_count,
                'sources': source_counts,
                'database_type': 'postgresql',
                'last_updated': datetime.now().isoformat()
            }
            
            logger.info(f"✅ Database context: {total_count} total items across {len(source_counts)} sources")
            return context
            
        except Exception as e:
            logger.error(f"❌ Database context query failed: {e}")
            return {
                'workspace': workspace,
                'total_items': 0,
                'sources': {},
                'database_type': 'postgresql',
                'error': str(e)
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the data."""
        try:
            logger.info("📈 Getting PostgreSQL statistics...")
            
            # Get total count
            total_result = self.db.fetch_one(
                "SELECT COUNT(*) as total FROM content_items WHERE user_id = %s",
                (self.user_id,)
            )
            total_count = total_result['total'] if total_result else 0
            
            # Get counts by source
            source_query = """
                SELECT source_name, COUNT(*) as count
                FROM content_items
                WHERE user_id = %s
                GROUP BY source_name
            """
            source_results = self.db.fetch_all(source_query, (self.user_id,))
            source_counts = {r['source_name']: r['count'] for r in source_results}
            
            # Get date range
            date_result = self.db.fetch_one(
                """
                SELECT MIN(created_date) as earliest
                FROM content_items
                WHERE user_id = %s AND created_date IS NOT NULL
                """,
                (self.user_id,)
            )
            earliest_date = date_result['earliest'] if date_result else None
            
            stats = {
                'total': total_count,
                'architecture': 'postgresql',
                'database_host': f"{self.db.host}:{self.db.port}",
                'user_id': self.user_id[:8] + '...',
                'earliest_date': str(earliest_date) if earliest_date else None,
                'last_updated': datetime.now().isoformat(),
                **source_counts
            }
            
            logger.info(f"✅ Statistics: {total_count} total items")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Statistics query failed: {e}")
            return {
                'total': 0,
                'architecture': 'postgresql',
                'error': str(e)
            }


# Global instance
_postgres_query_interface: Optional[PostgresQueryInterface] = None

def get_postgres_query_interface(user_id: str = "00000000-0000-0000-0000-000000000001") -> PostgresQueryInterface:
    """Get the global PostgreSQL query interface instance."""
    global _postgres_query_interface
    if _postgres_query_interface is None:
        _postgres_query_interface = PostgresQueryInterface(user_id)
    return _postgres_query_interface


@contextmanager
def pg_connect(db_path: str = None):
    """
    SQLite-compatible context manager for PostgreSQL connections.
    
    This is a drop-in replacement for sqlite3.connect() that returns
    a PostgreSQL connection instead. The db_path parameter is ignored
    (kept for compatibility).
    
    Usage:
        # Old SQLite code:
        # with sqlite3.connect(self.db_path) as conn:
        
        # New PostgreSQL code:
        from promaia.storage.postgres_db import pg_connect
        with pg_connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
    """
    db = get_postgres_db()
    conn = None
    try:
        conn = db._pool.getconn()
        conn.autocommit = False
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            db._pool.putconn(conn)
