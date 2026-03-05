"""
Vector Database Manager using pgvector for semantic search.

Handles embedding generation (Google Gemini gemini-embedding-001)
and pgvector operations for content storage and retrieval via Supabase PostgreSQL.
"""
import os
import json
import math
import logging
from typing import List, Dict, Any, Optional

import numpy as np
import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector

# Load environment first
from promaia.utils.config import load_environment
load_environment()

from promaia.storage.postgres_db import get_postgres_db

logger = logging.getLogger(__name__)


class VectorDBManager:
    """
    Manages pgvector operations and embedding generation.

    One-to-one mapping: 1 page_id = 1 markdown file = 1 vector embedding
    (or multiple chunks for chunked content).
    """

    def __init__(self, chroma_path: str = None):
        """
        Initialize pgvector client and embedding function.

        Args:
            chroma_path: Deprecated parameter, ignored. Kept for backward compatibility.
        """
        self.collection_name = "promaia_content"

        # Initialize pgvector via PostgresDB singleton
        try:
            self.db = get_postgres_db()
            # Register pgvector type on a connection to verify it works
            self._register_vector_on_connection()
            logger.info("pgvector initialized via PostgresDB singleton")
        except Exception as e:
            import traceback
            logger.error(f"Failed to initialize pgvector: {e}")
            logger.error(traceback.format_exc())
            raise

        # Initialize embedding function
        self._init_embedding_function()

    def _register_vector_on_connection(self):
        """Register pgvector type on a connection from the pool (verification only)."""
        with self.db.get_connection() as conn:
            register_vector(conn)

    def _get_vector_connection(self):
        """
        Get a connection from the pool with pgvector type registered.

        NOTE: The caller must use this within the db.get_connection() context manager.
        This is a helper that registers vector on an already-obtained connection.
        """
        pass  # Registration is done inline where needed

    def _init_embedding_function(self):
        """Initialize embedding model (Google Gemini gemini-embedding-001)."""
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if google_api_key:
            try:
                from google import genai
                self.genai_client = genai.Client(api_key=google_api_key)
                self.embedding_provider = "google"
                self.embedding_model = "gemini-embedding-001"
                logger.info(f"Using Google Gemini embeddings: {self.embedding_model}")
                return
            except Exception as e:
                logger.warning(f"Google Gemini embeddings unavailable: {e}")

        logger.error("Failed to initialize embedding provider: GOOGLE_API_KEY not set")
        raise RuntimeError("No embedding provider available. Set GOOGLE_API_KEY.")

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for given text.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector (768 dimensions)
        """
        if not text or not text.strip():
            raise ValueError("Cannot generate embedding for empty text")

        try:
            if self.embedding_provider == "google":
                result = self.genai_client.models.embed_content(
                    model='gemini-embedding-001',
                    contents=text
                )
                return result.embeddings[0].values
            else:
                raise RuntimeError(f"Unknown embedding provider: {self.embedding_provider}")

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise

    def add_content(
        self,
        page_id: str,
        content_text: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Add content to pgvector with embedding.

        Args:
            page_id: Unique identifier (from unified_content)
            content_text: Full markdown content to embed
            metadata: Metadata dict with database_name, workspace, created_time, etc.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate inputs
            if not content_text or not isinstance(content_text, str):
                logger.warning(f"Invalid content_text for {page_id}, skipping vector embedding")
                return False

            if not page_id or not isinstance(page_id, str):
                logger.warning(f"Invalid page_id, skipping vector embedding")
                return False

            # Generate embedding
            embedding = self.generate_embedding(content_text)

            # Validate embedding
            if embedding is None or not isinstance(embedding, list) or len(embedding) == 0:
                logger.warning(f"Invalid embedding generated for {page_id}, skipping")
                return False

            # Check for NaN or inf values
            try:
                if any(not math.isfinite(x) for x in embedding):
                    logger.warning(f"Embedding for {page_id} contains NaN or inf values, skipping")
                    return False
            except (TypeError, ValueError) as e:
                logger.warning(f"Invalid embedding values for {page_id}: {e}, skipping")
                return False

            # Clean metadata: store as JSONB
            clean_metadata = {}
            for k, v in metadata.items():
                if v is None:
                    continue
                if isinstance(v, (str, int, float, bool)):
                    clean_metadata[k] = v
                elif isinstance(v, (list, dict)):
                    clean_metadata[k] = v  # JSONB handles these natively
                else:
                    logger.debug(f"Skipping metadata key '{k}' with unsupported type {type(v)}")

            # Extract workspace and database_name from metadata for indexed columns
            workspace = clean_metadata.pop('workspace', metadata.get('workspace'))
            database_name = clean_metadata.pop('database_name', metadata.get('database_name'))

            # Upsert to content_embeddings via pgvector
            embedding_array = np.array(embedding)
            try:
                with self.db.get_connection() as conn:
                    register_vector(conn)
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO content_embeddings
                                (page_id, chunk_id, content, embedding, workspace, database_name, metadata)
                            VALUES (%s, NULL, %s, %s, %s, %s, %s)
                            ON CONFLICT (page_id, chunk_id) DO UPDATE SET
                                content = EXCLUDED.content,
                                embedding = EXCLUDED.embedding,
                                workspace = EXCLUDED.workspace,
                                database_name = EXCLUDED.database_name,
                                metadata = EXCLUDED.metadata,
                                updated_at = CURRENT_TIMESTAMP
                        """, [page_id, content_text, embedding_array, workspace, database_name, json.dumps(clean_metadata)])
                logger.debug(f"Upserted embedding for page_id: {page_id}")
                return True
            except Exception as db_error:
                logger.error(f"pgvector error adding {page_id}: {db_error}")
                logger.warning(f"Skipping vector embedding for {page_id} due to database error")
                return False

        except Exception as e:
            logger.error(f"Failed to add content for {page_id}: {e}")
            return False

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for given text.

        Args:
            text: Input text to estimate tokens for

        Returns:
            Estimated token count
        """
        # Rough estimation (no tiktoken dependency needed for google embeddings)
        return len(text) // 4

    def add_content_with_chunking(
        self,
        page_id: str,
        content_text: str,
        metadata: Dict[str, Any],
        chunks: List[Dict[str, Any]]
    ) -> bool:
        """
        Add content to pgvector with chunking support.

        Embeds each chunk separately with chunk-specific metadata.

        Args:
            page_id: Unique page identifier
            content_text: Full markdown content (not used, chunks used instead)
            metadata: Base metadata dict (database_name, workspace, etc.)
            chunks: List of chunk dicts from page_chunker.chunk_page_content()
                    Each contains: chunk_id, content, chunk_index, total_chunks, etc.

        Returns:
            True if all chunks embedded successfully, False otherwise
        """
        try:
            # First, remove any existing embeddings for this page
            # (including old chunks or non-chunked versions)
            try:
                with self.db.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM content_embeddings WHERE page_id = %s", [page_id])
            except Exception:
                pass  # May not exist, that's okay

            # Extract workspace and database_name from metadata
            workspace = metadata.get('workspace')
            database_name = metadata.get('database_name')

            # Embed each chunk
            success_count = 0
            for chunk in chunks:
                try:
                    chunk_id = chunk['chunk_id']
                    chunk_content = chunk['content']

                    # Generate embedding for this chunk
                    embedding = self.generate_embedding(chunk_content)
                    embedding_array = np.array(embedding)

                    # Prepare chunk-specific metadata
                    chunk_metadata = {
                        k: v for k, v in metadata.items()
                        if v is not None and k not in ('workspace', 'database_name')
                    }
                    chunk_metadata['page_id'] = page_id
                    chunk_metadata['chunk_id'] = chunk_id
                    chunk_metadata['chunk_index'] = chunk['chunk_index']
                    chunk_metadata['total_chunks'] = chunk['total_chunks']
                    chunk_metadata['is_chunk'] = True
                    chunk_metadata['estimated_tokens'] = chunk.get('estimated_tokens', 0)

                    with self.db.get_connection() as conn:
                        register_vector(conn)
                        with conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO content_embeddings
                                    (page_id, chunk_id, content, embedding, workspace, database_name,
                                     metadata, is_chunk, chunk_index, total_chunks)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (page_id, chunk_id) DO UPDATE SET
                                    content = EXCLUDED.content,
                                    embedding = EXCLUDED.embedding,
                                    workspace = EXCLUDED.workspace,
                                    database_name = EXCLUDED.database_name,
                                    metadata = EXCLUDED.metadata,
                                    is_chunk = EXCLUDED.is_chunk,
                                    chunk_index = EXCLUDED.chunk_index,
                                    total_chunks = EXCLUDED.total_chunks,
                                    updated_at = CURRENT_TIMESTAMP
                            """, [page_id, chunk_id, chunk_content, embedding_array,
                                  workspace, database_name, json.dumps(chunk_metadata),
                                  True, chunk['chunk_index'], chunk['total_chunks']])

                    success_count += 1
                    logger.debug(f"Upserted chunk {chunk['chunk_index'] + 1}/{chunk['total_chunks']} for page {page_id}")

                except Exception as e:
                    logger.error(f"Failed to embed chunk {chunk.get('chunk_id')}: {e}")
                    # Continue with other chunks even if one fails

            if success_count == len(chunks):
                logger.info(f"Successfully embedded all {success_count} chunks for page {page_id}")
                return True
            elif success_count > 0:
                logger.warning(f"Partially embedded {success_count}/{len(chunks)} chunks for page {page_id}")
                return True  # Consider partial success as success
            else:
                logger.error(f"Failed to embed any chunks for page {page_id}")
                return False

        except Exception as e:
            logger.error(f"Failed to add chunked content for {page_id}: {e}")
            return False

    def add_property_embedding(
        self,
        page_id: str,
        property_name: str,
        property_value: str,
        property_type: str,
        base_metadata: Dict[str, Any]
    ) -> bool:
        """
        Add property-specific embedding to property_embeddings table.

        Args:
            page_id: Base page ID
            property_name: Column name (e.g., "epic", "status")
            property_value: Formatted text value to embed
            property_type: Notion type (e.g., "relation", "select")
            base_metadata: Base metadata (workspace, database_name, etc.)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate embedding
            embedding = self.generate_embedding(property_value)
            embedding_array = np.array(embedding)

            # Extract indexed columns from metadata
            workspace = base_metadata.get('workspace')
            database_name = base_metadata.get('database_name')

            # Build metadata JSONB (excluding indexed columns)
            metadata = {
                k: v for k, v in base_metadata.items()
                if v is not None and k not in ('workspace', 'database_name')
            }
            metadata['page_id'] = page_id
            metadata['property_name'] = property_name
            metadata['property_type'] = property_type

            with self.db.get_connection() as conn:
                register_vector(conn)
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO property_embeddings
                            (page_id, property_name, property_type, property_value,
                             embedding, workspace, database_name, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (page_id, property_name) DO UPDATE SET
                            property_type = EXCLUDED.property_type,
                            property_value = EXCLUDED.property_value,
                            embedding = EXCLUDED.embedding,
                            workspace = EXCLUDED.workspace,
                            database_name = EXCLUDED.database_name,
                            metadata = EXCLUDED.metadata
                    """, [page_id, property_name, property_type, property_value,
                          embedding_array, workspace, database_name, json.dumps(metadata)])

            logger.debug(f"Upserted property embedding: {page_id}_prop_{property_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to add property embedding for {page_id}.{property_name}: {e}")
            return False

    def delete_property_embedding(
        self,
        page_id: str,
        property_name: str
    ) -> bool:
        """
        Delete a single property embedding.

        Args:
            page_id: Base page ID
            property_name: Property column name

        Returns:
            True if deleted, False otherwise
        """
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM property_embeddings WHERE page_id = %s AND property_name = %s",
                        [page_id, property_name]
                    )
                    deleted = cur.rowcount > 0

            if deleted:
                logger.debug(f"Deleted property embedding: {page_id}_prop_{property_name}")
            else:
                logger.debug(f"Property embedding not found: {page_id}_prop_{property_name}")
            return deleted

        except Exception as e:
            logger.error(f"Failed to delete property embedding {page_id}.{property_name}: {e}")
            return False

    def delete_property_embeddings(
        self,
        property_name: str,
        database_id: str = None,
        workspace: str = None,
        database_name: str = None
    ) -> int:
        """
        Delete all embeddings for a specific property.

        Args:
            property_name: Property column name to delete
            database_id: Optional database ID filter
            workspace: Optional workspace filter
            database_name: Optional database name filter

        Returns:
            Number of embeddings deleted
        """
        try:
            sql = "DELETE FROM property_embeddings WHERE property_name = %s"
            params = [property_name]

            if database_id:
                sql += " AND metadata->>'database_id' = %s"
                params.append(database_id)
            if workspace:
                sql += " AND workspace = %s"
                params.append(workspace)
            if database_name:
                sql += " AND database_name = %s"
                params.append(database_name)

            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    count = cur.rowcount

            if count > 0:
                logger.info(f"Deleted {count} property embeddings for {property_name}")
            else:
                logger.debug(f"No property embeddings found for {property_name}")
            return count

        except Exception as e:
            logger.error(f"Failed to delete property embeddings for {property_name}: {e}")
            return 0

    def search_property(
        self,
        property_name: str,
        query_text: str,
        filters: Optional[Dict[str, Any]] = None,
        n_results: int = 20,
        min_similarity: float = 0.2
    ) -> List[Dict[str, Any]]:
        """
        Search specific property embeddings.

        Args:
            property_name: Property to search (e.g., "epic", "title")
            query_text: Semantic query text
            filters: Additional metadata filters (workspace, database_name)
            n_results: Max results
            min_similarity: Minimum similarity threshold

        Returns:
            List of results with page_id and similarity scores
        """
        try:
            # Generate query embedding
            query_embedding = self.generate_embedding(query_text)
            query_array = np.array(query_embedding)

            sql = """
                SELECT id, page_id, property_value,
                       1 - (embedding <=> %s::vector) AS similarity_score,
                       metadata, property_name, property_type
                FROM property_embeddings
                WHERE property_name = %s
            """
            params: list = [query_array, property_name]

            # Add optional filters
            if filters:
                for key, value in filters.items():
                    if key.startswith('$'):
                        continue  # Skip ChromaDB-style operators
                    if key == 'workspace':
                        sql += " AND workspace = %s"
                        params.append(value)
                    elif key == 'database_name':
                        sql += " AND database_name = %s"
                        params.append(value)
                    else:
                        sql += " AND metadata->>%s = %s"
                        params.extend([key, str(value)])

            sql += " ORDER BY embedding <=> %s::vector LIMIT %s"
            params.extend([query_array, n_results])

            with self.db.get_connection() as conn:
                register_vector(conn)
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(sql, params)
                    rows = cur.fetchall()

            # Format results
            formatted_results = []
            for row in rows:
                similarity = float(row['similarity_score'])
                if similarity >= min_similarity:
                    formatted_results.append({
                        'id': f"{row['page_id']}_prop_{row['property_name']}",
                        'page_id': row['page_id'],
                        'similarity_score': similarity,
                        'metadata': row['metadata'] if row['metadata'] else {},
                        'property_value': row['property_value']
                    })

            logger.info(f"Property search '{property_name}' returned {len(formatted_results)} results")
            return formatted_results

        except Exception as e:
            logger.error(f"Property search failed: {e}")
            return []

    def search(
        self,
        query_text: str,
        filters: Optional[Dict[str, Any]] = None,
        n_results: int = 20,
        min_similarity: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Search for similar content using semantic similarity.

        Args:
            query_text: Search query text
            filters: Metadata filters (e.g., {"workspace": "trass", "database_name": {"$in": [...]}})
            n_results: Maximum number of results to return
            min_similarity: Minimum similarity score (0-1, cosine distance)

        Returns:
            List of dicts with page_id, distance (similarity), and metadata
        """
        try:
            # Generate query embedding
            query_embedding = self.generate_embedding(query_text)
            query_array = np.array(query_embedding)

            sql = """
                SELECT page_id, content,
                       1 - (embedding <=> %s::vector) AS similarity_score,
                       metadata, workspace, database_name
                FROM content_embeddings
                WHERE 1=1
            """
            params: list = [query_array]

            # Add metadata filters if provided
            if filters:
                if 'workspace' in filters:
                    sql += " AND workspace = %s"
                    params.append(filters['workspace'])

                if 'database_name' in filters:
                    db_filter = filters['database_name']
                    if isinstance(db_filter, dict) and '$in' in db_filter:
                        # Handle ChromaDB-style $in filters for backward compat
                        placeholders = ','.join(['%s'] * len(db_filter['$in']))
                        sql += f" AND database_name IN ({placeholders})"
                        params.extend(db_filter['$in'])
                    elif isinstance(db_filter, str):
                        sql += " AND database_name = %s"
                        params.append(db_filter)

            sql += " ORDER BY embedding <=> %s::vector LIMIT %s"
            params.extend([query_array, n_results])

            with self.db.get_connection() as conn:
                register_vector(conn)
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(sql, params)
                    rows = cur.fetchall()

            # Format results
            formatted_results = []
            for row in rows:
                similarity_score = float(row['similarity_score'])
                distance = 1 - similarity_score

                # Filter by minimum similarity
                if similarity_score >= min_similarity:
                    formatted_results.append({
                        'page_id': row['page_id'],
                        'similarity_score': similarity_score,
                        'distance': distance,
                        'metadata': row['metadata'] if row['metadata'] else {}
                    })

            logger.info(f"Vector search returned {len(formatted_results)} results")
            return formatted_results

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def check_exists(self, page_id: str) -> bool:
        """
        Check if a page_id already exists in content_embeddings.

        Args:
            page_id: The page_id to check

        Returns:
            True if exists, False otherwise
        """
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM content_embeddings WHERE page_id = %s LIMIT 1", [page_id])
                    return cur.fetchone() is not None
        except Exception as e:
            logger.debug(f"Check exists failed for {page_id}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector database.

        Returns:
            Dict with collection stats
        """
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM content_embeddings")
                    content_count = cur.fetchone()[0]

                    cur.execute("SELECT COUNT(*) FROM property_embeddings")
                    property_count = cur.fetchone()[0]

            return {
                "collection_name": self.collection_name,
                "total_documents": content_count,
                "total_property_embeddings": property_count,
                "embedding_provider": self.embedding_provider,
                "embedding_model": self.embedding_model,
                "backend": "pgvector (Supabase PostgreSQL)"
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}


# Convenience function for easy import
def get_vector_db_manager() -> VectorDBManager:
    """Get or create a VectorDBManager instance."""
    return VectorDBManager()
