"""
Vector Database Manager using sqlite-vec for semantic search.

Handles embedding generation (Google Gemini gemini-embedding-001)
and sqlite-vec operations for content storage and retrieval.
"""
import os
import json
import math
import logging
import struct
from typing import List, Dict, Any, Optional

import numpy as np

# Load environment first
from promaia.utils.config import load_environment
load_environment()

from promaia.ai.models import GOOGLE_MODELS
from promaia.storage.db_factory import get_db

logger = logging.getLogger(__name__)


class VectorDBManager:
    """
    Manages sqlite-vec operations and embedding generation.

    One-to-one mapping: 1 page_id = 1 markdown file = 1 vector embedding
    (or multiple chunks for chunked content).
    """

    def __init__(self, chroma_path: str = None):
        """
        Initialize sqlite-vec client and embedding function.

        Args:
            chroma_path: Deprecated parameter, ignored. Kept for backward compatibility.
        """
        self.collection_name = "promaia_content"

        # Initialize sqlite-vec via LibSQLDB singleton
        try:
            self.db = get_db()
            # Vector operations handled by sqlite-vec extension in LibSQL
            pass
            logger.info("sqlite-vec initialized via LibSQLDB singleton")
        except Exception as e:
            import traceback
            logger.error(f"Failed to initialize sqlite-vec: {e}")
            logger.error(traceback.format_exc())
            raise

        # Initialize embedding function
        self._init_embedding_function()

    def _init_embedding_function(self):
        """Initialize embedding model (Google Gemini gemini-embedding-001)."""
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if google_api_key:
            try:
                from google import genai
                self.genai_client = genai.Client(api_key=google_api_key)
                self.embedding_provider = "google"
                self.embedding_model = GOOGLE_MODELS["embedding"]
                logger.info(f"Using Google Gemini embeddings: {self.embedding_model}")
                return
            except Exception as e:
                logger.warning(f"Google Gemini embeddings unavailable: {e}")

        logger.error("Failed to initialize embedding provider: GOOGLE_API_KEY not set")
        raise RuntimeError("No embedding provider available. Set GOOGLE_API_KEY.")

    def generate_embedding(self, text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> List[float]:
        """
        Generate embedding for given text.

        Args:
            text: Input text to embed
            task_type: Gemini task type to optimize vector geometry.
                       Use "RETRIEVAL_DOCUMENT" when storing content (default).
                       Use "RETRIEVAL_QUERY" when embedding a search query.
                       Other options: SEMANTIC_SIMILARITY, CLASSIFICATION,
                       CLUSTERING, CODE_RETRIEVAL_QUERY, QUESTION_ANSWERING,
                       FACT_VERIFICATION.

        Returns:
            List of floats representing the embedding vector (768 dimensions)
        """
        if not text or not text.strip():
            raise ValueError("Cannot generate embedding for empty text")

        try:
            if self.embedding_provider == "google":
                result = self.genai_client.models.embed_content(
                    model=GOOGLE_MODELS["embedding"],
                    contents=text,
                    config={
                        'output_dimensionality': 768,
                        'task_type': task_type,
                    },
                )
                raw = result.embeddings[0].values
                # Gemini Embedding 2 only normalizes the full 3072d output.
                # Sub-3072 dimensions (768, 1536) require manual L2 normalization
                # for accurate cosine similarity computations.
                arr = np.array(raw, dtype=np.float64)
                norm = np.linalg.norm(arr)
                if norm > 0:
                    arr = arr / norm
                return arr.tolist()
            else:
                raise RuntimeError(f"Unknown embedding provider: {self.embedding_provider}")

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise

    def generate_multimodal_embedding(
        self,
        text: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
        audio_paths: Optional[List[str]] = None,
        document_paths: Optional[List[str]] = None,
        task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> List[float]:
        """
        Generate a single aggregated embedding from mixed modalities
        using Gemini Embedding 2.

        Args:
            text: Optional text content
            image_paths: Optional list of absolute paths to images
            audio_paths: Optional list of absolute paths to audio files
            document_paths: Optional list of absolute paths to documents (PDFs, txt, csv, md)
            task_type: Defaults to RETRIEVAL_DOCUMENT

        Returns:
            List of floats representing the embedding vector, L2 normalized (768 dimensions).
        """
        if not text and not image_paths and not audio_paths and not document_paths:
            raise ValueError("Must provide at least one modality for embedding")

        try:
            if self.embedding_provider != "google":
                raise RuntimeError(f"Multimodal embeddings require Google provider. Current: {self.embedding_provider}")

            from google.genai import types

            parts = []
            if text and text.strip():
                parts.append(types.Part.from_text(text=text))

            if image_paths:
                for img_path in image_paths:
                    with open(img_path, 'rb') as f:
                        image_bytes = f.read()
                    
                    # Basic mime type inference
                    lower_path = img_path.lower()
                    if lower_path.endswith('.png'):
                        mime = 'image/png'
                    elif lower_path.endswith('.webp'):
                        mime = 'image/webp'
                    else:
                        mime = 'image/jpeg'
                        
                    parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime))

            if audio_paths:
                for aud_path in audio_paths:
                    with open(aud_path, 'rb') as f:
                        audio_bytes = f.read()
                        
                    lower_path = aud_path.lower()
                    if lower_path.endswith('.wav'):
                        mime = 'audio/wav'
                    elif lower_path.endswith('.ogg'):
                        mime = 'audio/ogg'
                    else:
                        mime = 'audio/mpeg'
                        
                    parts.append(types.Part.from_bytes(data=audio_bytes, mime_type=mime))

            if document_paths:
                for doc_path in document_paths:
                    with open(doc_path, 'rb') as f:
                        doc_bytes = f.read()
                        
                    lower_path = doc_path.lower()
                    if lower_path.endswith('.pdf'):
                        mime = 'application/pdf'
                    elif lower_path.endswith('.csv'):
                        mime = 'text/csv'
                    elif lower_path.endswith('.md'):
                        mime = 'text/markdown'
                    else:
                        mime = 'text/plain'
                        
                    parts.append(types.Part.from_bytes(data=doc_bytes, mime_type=mime))

            # Assemble content entry for aggregation
            content_entry = types.Content(parts=parts)

            result = self.genai_client.models.embed_content(
                model=GOOGLE_MODELS["embedding"],
                contents=content_entry,
                config={
                    'output_dimensionality': 768,
                    'task_type': task_type,
                },
            )
            raw = result.embeddings[0].values
            
            # Gemini Embedding 2 only normalizes the full 3072d output.
            # Sub-3072 dimensions require manual L2 normalization.
            arr = np.array(raw, dtype=np.float64)
            norm = np.linalg.norm(arr)
            if norm > 0:
                arr = arr / norm
            return arr.tolist()

        except Exception as e:
            logger.error(f"Multimodal embedding generation failed: {e}")
            raise

    def add_content(
        self,
        page_id: str,
        content_text: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Add content to sqlite-vec with embedding.

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

            # Clean metadata: store as JSON text
            clean_metadata = {}
            for k, v in metadata.items():
                if v is None:
                    continue
                if isinstance(v, (str, int, float, bool)):
                    clean_metadata[k] = v
                elif isinstance(v, (list, dict)):
                    clean_metadata[k] = v  # JSON handles these natively
                else:
                    logger.debug(f"Skipping metadata key '{k}' with unsupported type {type(v)}")

            # Extract workspace and database_name from metadata for indexed columns
            workspace = clean_metadata.pop('workspace', metadata.get('workspace'))
            database_name = clean_metadata.pop('database_name', metadata.get('database_name'))

            # Upsert to content_embeddings via sqlite-vec
            embedding_array = json.dumps(embedding)
            try:
                self.db.execute("""
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
                logger.error(f"sqlite-vec error adding {page_id}: {db_error}")
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
        Add content to sqlite-vec with chunking support.

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
                self.db.execute("DELETE FROM content_embeddings WHERE page_id = %s", [page_id])
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
                    embedding_array = json.dumps(embedding)

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

                    self.db.execute("""
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
            embedding_array = json.dumps(embedding)

            # Extract indexed columns from metadata
            workspace = base_metadata.get('workspace')
            database_name = base_metadata.get('database_name')

            # Build metadata JSON (excluding indexed columns)
            metadata = {
                k: v for k, v in base_metadata.items()
                if v is not None and k not in ('workspace', 'database_name')
            }
            metadata['page_id'] = page_id
            metadata['property_name'] = property_name
            metadata['property_type'] = property_type

            self.db.execute("""
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
            cur = self.db.execute("DELETE FROM property_embeddings WHERE page_id = %s AND property_name = %s", [page_id, property_name])
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
                sql += " AND json_extract(metadata, '$.database_id') = %s"
                params.append(database_id)
            if workspace:
                sql += " AND workspace = %s"
                params.append(workspace)
            if database_name:
                sql += " AND database_name = %s"
                params.append(database_name)

            cur = self.db.execute(sql, params)
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
            # Generate query embedding (asymmetric: queries use RETRIEVAL_QUERY)
            query_embedding = self.generate_embedding(query_text, task_type="RETRIEVAL_QUERY")
            query_blob = struct.pack(f'{len(query_embedding)}f', *query_embedding)

            sql = """
                SELECT id, page_id, property_value,
                       1 - vec_distance_cosine(embedding, %s) AS similarity_score,
                       metadata, property_name, property_type
                FROM property_embeddings
                WHERE property_name = %s
            """
            params: list = [query_blob, property_name]

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
                        sql += " AND json_extract(metadata, '$.' || %s) = %s"
                        params.extend([key, str(value)])

            sql += " ORDER BY vec_distance_cosine(embedding, %s) LIMIT %s"
            params.extend([query_blob, n_results])

            cur = self.db.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]

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
            # Generate query embedding (asymmetric: queries use RETRIEVAL_QUERY)
            query_embedding = self.generate_embedding(query_text, task_type="RETRIEVAL_QUERY")
            query_blob = struct.pack(f'{len(query_embedding)}f', *query_embedding)

            sql = """
                SELECT page_id, content,
                       1 - vec_distance_cosine(embedding, %s) AS similarity_score,
                       metadata, workspace, database_name
                FROM content_embeddings
                WHERE 1=1
            """
            params: list = [query_blob]

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

            sql += " ORDER BY vec_distance_cosine(embedding, %s) LIMIT %s"
            params.extend([query_blob, n_results])

            cur = self.db.execute(sql, params)
            rows = [dict(r) for r in cur.fetchall()]

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
            cur = self.db.execute("SELECT 1 FROM content_embeddings WHERE page_id = %s LIMIT 1", [page_id])
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
            cur = self.db.execute("SELECT COUNT(*) FROM content_embeddings")
            content_count = cur.fetchone()[0]

            cur = self.db.execute("SELECT COUNT(*) FROM property_embeddings")
            property_count = cur.fetchone()[0]

            return {
                "collection_name": self.collection_name,
                "total_documents": content_count,
                "total_property_embeddings": property_count,
                "embedding_provider": self.embedding_provider,
                "embedding_model": self.embedding_model,
                "backend": "sqlite-vec (libSQL)"
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}


# Convenience function for easy import
def get_vector_db_manager() -> VectorDBManager:
    """Get or create a VectorDBManager instance."""
    return VectorDBManager()
