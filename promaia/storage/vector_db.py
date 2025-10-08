"""
Vector Database Manager using ChromaDB for semantic search.

Handles embedding generation (OpenAI with sentence-transformers fallback)
and ChromaDB operations for content storage and retrieval.
"""
import os
from typing import List, Dict, Any, Optional
import logging

# Load environment first
from promaia.utils.config import load_environment
load_environment()

logger = logging.getLogger(__name__)


class VectorDBManager:
    """
    Manages ChromaDB operations and embedding generation.
    
    One-to-one mapping: 1 page_id = 1 markdown file = 1 vector embedding
    """
    
    def __init__(self, chroma_path: str = "chroma_db"):
        """
        Initialize ChromaDB client and embedding function.
        
        Args:
            chroma_path: Path to ChromaDB directory (not a file)
        """
        self.chroma_path = chroma_path
        self.collection_name = "promaia_content"
        
        # Initialize ChromaDB
        try:
            import chromadb
            
            # Ensure the directory exists
            os.makedirs(chroma_path, exist_ok=True)
            
            # Initialize client - use basic initialization for ChromaDB 0.5.x
            self.client = chromadb.PersistentClient(path=chroma_path)
            
            # Get or create collection with cosine similarity (distance function)
            # Note: ChromaDB 0.5.x uses 'l2', 'ip' (inner product), or 'cosine'
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity
            )
            logger.info(f"✅ ChromaDB initialized at {chroma_path}")
        except Exception as e:
            import traceback
            logger.error(f"❌ Failed to initialize ChromaDB: {e}")
            logger.error(traceback.format_exc())
            raise
        
        # Initialize embedding function
        self._init_embedding_function()
    
    def _init_embedding_function(self):
        """Initialize embedding model (OpenAI with fallback to sentence-transformers)."""
        # Try OpenAI first
        if os.getenv("OPENAI_API_KEY"):
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                self.embedding_provider = "openai"
                self.embedding_model = "text-embedding-3-small"
                logger.info(f"✅ Using OpenAI embeddings: {self.embedding_model}")
                return
            except Exception as e:
                logger.warning(f"⚠️  OpenAI embeddings unavailable: {e}")
        
        # Fallback to sentence-transformers
        try:
            from sentence_transformers import SentenceTransformer
            self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.embedding_provider = "sentence-transformers"
            self.embedding_model = "all-MiniLM-L6-v2"
            logger.info(f"✅ Using sentence-transformers: {self.embedding_model}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize any embedding provider: {e}")
            raise RuntimeError("No embedding provider available")
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for given text.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        if not text or not text.strip():
            raise ValueError("Cannot generate embedding for empty text")
        
        try:
            if self.embedding_provider == "openai":
                response = self.openai_client.embeddings.create(
                    input=text,
                    model=self.embedding_model
                )
                return response.data[0].embedding
            
            elif self.embedding_provider == "sentence-transformers":
                embedding = self.sentence_model.encode(text, convert_to_tensor=False)
                return embedding.tolist()
            
            else:
                raise RuntimeError(f"Unknown embedding provider: {self.embedding_provider}")
        
        except Exception as e:
            logger.error(f"❌ Embedding generation failed: {e}")
            raise
    
    def add_content(
        self,
        page_id: str,
        content_text: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Add content to ChromaDB with embedding.
        
        Args:
            page_id: Unique identifier (from unified_content)
            content_text: Full markdown content to embed
            metadata: Metadata dict with database_name, workspace, created_time, etc.
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate embedding
            embedding = self.generate_embedding(content_text)
            
            # Add to collection
            self.collection.add(
                ids=[page_id],
                documents=[content_text],
                embeddings=[embedding],
                metadatas=[metadata]
            )
            
            logger.debug(f"✅ Added embedding for page_id: {page_id}")
            return True
        
        except Exception as e:
            logger.error(f"❌ Failed to add content for {page_id}: {e}")
            return False
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for given text.
        
        Args:
            text: Input text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        if self.embedding_provider == "openai":
            try:
                import tiktoken
                encoding = tiktoken.get_encoding("cl100k_base")
                return len(encoding.encode(text))
            except ImportError:
                logger.warning("tiktoken not available, using rough estimation")
                return len(text) // 4
        else:
            # Rough estimation for other providers
            return len(text) // 4
    
    def add_content_with_chunking(
        self,
        page_id: str,
        content_text: str,
        metadata: Dict[str, Any],
        chunks: List[Dict[str, Any]]
    ) -> bool:
        """
        Add content to ChromaDB with chunking support.
        
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
                self.collection.delete(where={"page_id": page_id})
            except:
                pass  # May not exist, that's okay
            
            # Embed each chunk
            success_count = 0
            for chunk in chunks:
                try:
                    chunk_id = chunk['chunk_id']
                    chunk_content = chunk['content']
                    
                    # Generate embedding for this chunk
                    embedding = self.generate_embedding(chunk_content)
                    
                    # Prepare chunk-specific metadata
                    chunk_metadata = {
                        **metadata,  # Include base metadata
                        'page_id': page_id,  # Store original page_id for retrieval
                        'chunk_id': chunk_id,
                        'chunk_index': chunk['chunk_index'],
                        'total_chunks': chunk['total_chunks'],
                        'is_chunk': True,  # Flag to indicate this is a chunk
                        'estimated_tokens': chunk.get('estimated_tokens', 0)
                    }
                    
                    # Add to collection with chunk_id as the ID
                    self.collection.add(
                        ids=[chunk_id],
                        documents=[chunk_content],
                        embeddings=[embedding],
                        metadatas=[chunk_metadata]
                    )
                    
                    success_count += 1
                    logger.debug(f"✅ Added chunk {chunk['chunk_index'] + 1}/{chunk['total_chunks']} for page {page_id}")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to embed chunk {chunk.get('chunk_id')}: {e}")
                    # Continue with other chunks even if one fails
            
            if success_count == len(chunks):
                logger.info(f"✅ Successfully embedded all {success_count} chunks for page {page_id}")
                return True
            elif success_count > 0:
                logger.warning(f"⚠️  Partially embedded {success_count}/{len(chunks)} chunks for page {page_id}")
                return True  # Consider partial success as success
            else:
                logger.error(f"❌ Failed to embed any chunks for page {page_id}")
                return False
        
        except Exception as e:
            logger.error(f"❌ Failed to add chunked content for {page_id}: {e}")
            return False
    
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
            
            # Build query parameters
            query_params = {
                "query_embeddings": [query_embedding],
                "n_results": n_results
            }
            
            # Add metadata filters if provided
            if filters:
                query_params["where"] = filters
            
            # Execute search
            results = self.collection.query(**query_params)
            
            # Format results
            formatted_results = []
            if results and results['ids'] and len(results['ids']) > 0:
                for i, page_id in enumerate(results['ids'][0]):
                    distance = results['distances'][0][i] if results['distances'] else 0
                    similarity_score = 1 - distance  # Convert distance to similarity
                    
                    # Filter by minimum similarity
                    if similarity_score >= min_similarity:
                        formatted_results.append({
                            'page_id': page_id,
                            'similarity_score': similarity_score,
                            'distance': distance,
                            'metadata': results['metadatas'][0][i] if results['metadatas'] else {}
                        })
            
            logger.info(f"🔍 Vector search returned {len(formatted_results)} results")
            return formatted_results
        
        except Exception as e:
            logger.error(f"❌ Vector search failed: {e}")
            return []
    
    def check_exists(self, page_id: str) -> bool:
        """
        Check if a page_id already exists in ChromaDB.
        
        Args:
            page_id: The page_id to check
            
        Returns:
            True if exists, False otherwise
        """
        try:
            result = self.collection.get(ids=[page_id])
            return len(result['ids']) > 0
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
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "total_documents": count,
                "embedding_provider": self.embedding_provider,
                "embedding_model": self.embedding_model,
                "chroma_path": self.chroma_path
            }
        except Exception as e:
            logger.error(f"❌ Failed to get stats: {e}")
            return {}


# Convenience function for easy import
def get_vector_db_manager(chroma_path: str = "chroma_db") -> VectorDBManager:
    """Get or create a VectorDBManager instance."""
    return VectorDBManager(chroma_path=chroma_path)

