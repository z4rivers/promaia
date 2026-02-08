"""
Supabase Query Interface for Promaia - PostgreSQL Backend

This module provides backward compatibility with existing code that imports
from supabase_query.py. All functionality is now provided by PostgresQueryInterface.
"""

import logging
from typing import Optional

from promaia.storage.postgres_db import (
    PostgresQueryInterface,
    get_postgres_query_interface as _get_postgres_query_interface
)

logger = logging.getLogger(__name__)

# Backward compatibility: SupabaseQueryInterface is now PostgresQueryInterface
SupabaseQueryInterface = PostgresQueryInterface

# Global instance (using PostgreSQL backend)
_supabase_query_interface: Optional[PostgresQueryInterface] = None


def get_supabase_query_interface(user_id: str = "00000000-0000-0000-0000-000000000001") -> PostgresQueryInterface:
    """
    Get the global query interface instance.
    
    This function is kept for backward compatibility.
    Returns a PostgresQueryInterface instance.
    """
    global _supabase_query_interface
    if _supabase_query_interface is None:
        _supabase_query_interface = _get_postgres_query_interface(user_id)
    return _supabase_query_interface
