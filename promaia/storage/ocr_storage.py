"""
OCR-specific storage helpers for Promaia.

Manages OCR uploads table and provides convenience functions 
for storing and querying OCR results.

Now uses PostgreSQL for centralized storage.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from psycopg2 import extras
from promaia.storage.db_factory import db_connect, get_postgres_db

# Avoid circular import - ProcessedDocument will be passed as parameter

logger = logging.getLogger(__name__)


class OCRStorage:
    """Manages OCR uploads in PostgreSQL storage."""

    def __init__(self, db_path: str = "data/hybrid_metadata.db"):
        """
        Initialize OCR storage.

        Args:
            db_path: Deprecated - kept for backward compatibility.
        """
        self.db_path = db_path
        self.db = get_db()
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        """Verify ocr_uploads table exists."""
        if not self.db.table_exists('ocr_uploads'):
            logger.warning("ocr_uploads table not found. Run: python -m promaia.storage.db_init init")

    def store_processed_document(
        self,
        doc: Any,  # ProcessedDocument - avoiding circular import
        workspace: str,
        database_name: str = "uploads",
        page_id: Optional[str] = None
    ) -> bool:
        """
        Store processed OCR document in database.

        Args:
            doc: ProcessedDocument from OCR processor
            workspace: Workspace name
            database_name: Database name (default: "uploads")
            page_id: Optional Notion page ID if synced

        Returns:
            True if successful
        """
        try:
            with db_connect() as conn:
                cursor = conn.cursor()

                # Prepare data
                title = doc.image_path.stem
                upload_date = datetime.fromtimestamp(
                    doc.image_path.stat().st_mtime
                ).isoformat()
                processing_date = datetime.now().isoformat()

                metadata = {
                    "text_regions_count": len(doc.ocr_result.text_regions) if doc.ocr_result else 0,
                    "processing_time": doc.ocr_result.processing_time if doc.ocr_result else 0,
                }

                # Insert or update on conflict
                cursor.execute("""
                    INSERT INTO ocr_uploads (
                        page_id, workspace, database_name, title, file_path,
                        source_image_path, processed_image_path,
                        ocr_confidence, ocr_engine, language, text_length,
                        status, upload_date, processing_date,
                        created_time, last_edited_time, synced_time,
                        metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_image_path) DO UPDATE SET
                        page_id = EXCLUDED.page_id,
                        workspace = EXCLUDED.workspace,
                        database_name = EXCLUDED.database_name,
                        title = EXCLUDED.title,
                        file_path = EXCLUDED.file_path,
                        processed_image_path = EXCLUDED.processed_image_path,
                        ocr_confidence = EXCLUDED.ocr_confidence,
                        ocr_engine = EXCLUDED.ocr_engine,
                        language = EXCLUDED.language,
                        text_length = EXCLUDED.text_length,
                        status = EXCLUDED.status,
                        upload_date = EXCLUDED.upload_date,
                        processing_date = EXCLUDED.processing_date,
                        last_edited_time = EXCLUDED.last_edited_time,
                        synced_time = EXCLUDED.synced_time,
                        metadata = EXCLUDED.metadata
                """, (
                    page_id,
                    workspace,
                    database_name,
                    title,
                    str(doc.markdown_path) if doc.markdown_path else "",
                    str(doc.image_path),
                    str(doc.processed_image_path) if doc.processed_image_path else "",
                    doc.ocr_result.confidence if doc.ocr_result else 0.0,
                    doc.ocr_result.metadata.get("api", "unknown") if doc.ocr_result else "unknown",
                    doc.ocr_result.language if doc.ocr_result else "unknown",
                    len(doc.ocr_result.text) if doc.ocr_result and doc.ocr_result.text else 0,
                    doc.status,
                    upload_date,
                    processing_date,
                    processing_date,  # created_time
                    processing_date,  # last_edited_time
                    datetime.now().isoformat() if page_id else None,  # synced_time
                    json.dumps(metadata)
                ))

                logger.debug(f"Stored OCR document: {title}")
                return True

        except Exception as e:
            logger.error(f"Error storing OCR document: {e}")
            return False

    def update_page_id(self, source_image_path: str, page_id: str) -> bool:
        """
        Update Notion page ID for an OCR upload.

        Args:
            source_image_path: Original image path
            page_id: Notion page ID

        Returns:
            True if successful
        """
        try:
            with db_connect() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE ocr_uploads
                    SET page_id = %s, synced_time = %s
                    WHERE source_image_path = %s
                """, (page_id, datetime.now().isoformat(), source_image_path))

                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error updating page ID: {e}")
            return False

    def get_by_image_path(self, image_path: str) -> Optional[Dict[str, Any]]:
        """
        Get OCR upload by image path.

        Args:
            image_path: Source image path

        Returns:
            Upload record dict or None
        """
        try:
            with db_connect() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

                cursor.execute("""
                    SELECT * FROM ocr_uploads
                    WHERE source_image_path = %s
                """, (image_path,))

                row = cursor.fetchone()
                return dict(row) if row else None

        except Exception as e:
            logger.error(f"Error getting OCR upload: {e}")
            return None

    def get_by_workspace(
        self,
        workspace: str,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all OCR uploads for a workspace.

        Args:
            workspace: Workspace name
            status: Optional status filter

        Returns:
            List of upload records
        """
        try:
            with db_connect() as conn:
                cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

                if status:
                    cursor.execute("""
                        SELECT * FROM ocr_uploads
                        WHERE workspace = %s AND status = %s
                        ORDER BY processing_date DESC
                    """, (workspace, status))
                else:
                    cursor.execute("""
                        SELECT * FROM ocr_uploads
                        WHERE workspace = %s
                        ORDER BY processing_date DESC
                    """, (workspace,))

                rows = cursor.fetchall()
                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Error getting workspace uploads: {e}")
            return []

    def get_stats(self, workspace: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about OCR uploads.

        Args:
            workspace: Optional workspace filter

        Returns:
            Dict with statistics
        """
        try:
            with db_connect() as conn:
                cursor = conn.cursor()

                where_clause = "WHERE workspace = %s" if workspace else ""
                params = (workspace,) if workspace else ()

                # Get counts by status
                cursor.execute(f"""
                    SELECT status, COUNT(*) as count
                    FROM ocr_uploads
                    {where_clause}
                    GROUP BY status
                """, params)

                status_counts = {row[0]: row[1] for row in cursor.fetchall()}

                # Get total and average confidence
                cursor.execute(f"""
                    SELECT
                        COUNT(*) as total,
                        AVG(ocr_confidence) as avg_confidence,
                        MIN(ocr_confidence) as min_confidence,
                        MAX(ocr_confidence) as max_confidence
                    FROM ocr_uploads
                    {where_clause}
                """, params)

                row = cursor.fetchone()

                return {
                    "total": row[0] or 0,
                    "status_counts": status_counts,
                    "avg_confidence": row[1] or 0.0,
                    "min_confidence": row[2] or 0.0,
                    "max_confidence": row[3] or 0.0
                }

        except Exception as e:
            logger.error(f"Error getting OCR stats: {e}")
            return {
                "total": 0,
                "status_counts": {},
                "avg_confidence": 0.0,
                "min_confidence": 0.0,
                "max_confidence": 0.0
            }

    def delete_by_image_path(self, image_path: str) -> bool:
        """
        Delete OCR upload record by image path.

        Args:
            image_path: Source image path

        Returns:
            True if successful
        """
        try:
            with db_connect() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    DELETE FROM ocr_uploads
                    WHERE source_image_path = %s
                """, (image_path,))

                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error deleting OCR upload: {e}")
            return False


# Convenience functions
def store_ocr_result(
    doc: Any,  # ProcessedDocument
    workspace: str,
    database_name: str = "uploads",
    page_id: Optional[str] = None
) -> bool:
    """
    Store OCR result in hybrid storage.

    Args:
        doc: ProcessedDocument
        workspace: Workspace name
        database_name: Database name
        page_id: Optional Notion page ID

    Returns:
        True if successful
    """
    storage = OCRStorage()
    return storage.store_processed_document(doc, workspace, database_name, page_id)


def get_ocr_stats(workspace: Optional[str] = None) -> Dict[str, Any]:
    """
    Get OCR processing statistics.

    Args:
        workspace: Optional workspace filter

    Returns:
        Statistics dict
    """
    storage = OCRStorage()
    return storage.get_stats(workspace)
