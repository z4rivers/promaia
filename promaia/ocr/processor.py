"""
Main OCR processor for Promaia.

Orchestrates the full OCR pipeline:
- Image preprocessing
- Text extraction
- Text postprocessing
- Markdown generation
- File organization
"""
import logging
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from promaia.config.ocr import get_ocr_config
from promaia.ocr.engines.base import BaseOCREngine, OCRResult
from promaia.ocr.engines.mock import MockOCREngine
from promaia.ocr.image_preprocessor import ImagePreprocessor
from promaia.ocr.text_postprocessor import TextPostprocessor, create_ocr_markdown
from promaia.storage.ocr_storage import OCRStorage

# Try to import Google Vision engine
try:
    from promaia.ocr.engines.google_vision import GoogleVisionEngine
    google_vision_available = True
except ImportError:
    google_vision_available = False
    GoogleVisionEngine = None

# Try to import Gemini Semantic engine
try:
    from promaia.ocr.engines.gemini_semantic import GeminiSemanticEngine
    gemini_semantic_available = True
except ImportError:
    gemini_semantic_available = False
    GeminiSemanticEngine = None

# Try to import Notion sync
try:
    from promaia.ocr.notion_sync import create_notion_page_from_ocr
    notion_sync_available = True
except ImportError:
    notion_sync_available = False
    create_notion_page_from_ocr = None

# Try to import Brain connection
try:
    from promaia.storage.db_factory import get_db
    from promaia.storage.vector_db import VectorDBManager
    from promaia.brain.core.memory_pipeline import capture_memory
    brain_integration_available = True
except ImportError:
    brain_integration_available = False

logger = logging.getLogger(__name__)


@dataclass
class ProcessedDocument:
    """Result from processing an image through OCR pipeline."""

    image_path: Path
    ocr_result: OCRResult
    markdown_path: Optional[Path] = None
    processed_image_path: Optional[Path] = None
    status: str = "pending"  # pending, completed, failed, review_needed
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "image_path": str(self.image_path),
            "markdown_path": str(self.markdown_path) if self.markdown_path else None,
            "processed_image_path": str(self.processed_image_path) if self.processed_image_path else None,
            "status": self.status,
            "confidence": self.ocr_result.confidence if self.ocr_result else 0.0,
            "language": self.ocr_result.language if self.ocr_result else "unknown",
            "text_length": len(self.ocr_result.text) if self.ocr_result and self.ocr_result.text else 0,
            "error": self.error
        }


class OCRProcessor:
    """Main OCR processor orchestrating the full pipeline."""

    def __init__(self, config_file: str = "promaia.config.json", workspace: str = "default"):
        """
        Initialize OCR processor.

        Args:
            config_file: Path to configuration file
            workspace: Workspace name for storing results
        """
        self.config = get_ocr_config()
        self.workspace = workspace
        self.engine = self._initialize_engine()
        self.preprocessor = ImagePreprocessor(
            resize_max=self.config.preprocessing.get("resize_max", 4096),
            enhance_contrast=self.config.preprocessing.get("enhance_contrast", True),
            denoise=self.config.preprocessing.get("denoise", False)
        )
        self.postprocessor = TextPostprocessor()
        self.storage = OCRStorage()

    def _get_notion_database_id(self) -> Optional[str]:
        """Get Notion database ID from config if available."""
        try:
            import json
            with open("promaia.config.json", 'r') as f:
                config = json.load(f)
                db_config = config.get("databases", {}).get("ocr_uploads", {})
                return db_config.get("database_id")
        except Exception as e:
            logger.debug(f"No Notion database configured: {e}")
            return None

    def _initialize_engine(self) -> BaseOCREngine:
        """
        Initialize the OCR engine based on configuration.

        Returns:
            Configured OCR engine
        """
        engine_name = self.config.engine
        engine_config = self.config.get_engine_config()

        if engine_name == "google_cloud_vision":
            if not google_vision_available:
                logger.error(
                    "Google Cloud Vision not available. "
                    "Install with: pip install google-cloud-vision"
                )
                logger.warning("Falling back to mock engine")
                return MockOCREngine(engine_config)
            return GoogleVisionEngine(engine_config)
        elif engine_name == "gemini":
            if not gemini_semantic_available:
                logger.error("Gemini OCR engine not available. Install google-genai to use.")
                logger.warning("Falling back to mock engine")
                return MockOCREngine(engine_config)
            return GeminiSemanticEngine(engine_config)
        elif engine_name == "mock":
            return MockOCREngine(engine_config)
        elif engine_name == "tesseract":
            # TODO: Implement TesseractEngine
            logger.warning("Tesseract engine not yet implemented, using mock")
            return MockOCREngine(engine_config)
        else:
            logger.error(f"Unknown OCR engine: {engine_name}, using mock")
            return MockOCREngine(engine_config)

    async def process_image(
        self,
        image_path: Path,
        save_markdown: bool = True,
        move_to_processed: bool = True
    ) -> ProcessedDocument:
        """
        Process a single image through the OCR pipeline.

        Args:
            image_path: Path to image file
            save_markdown: Whether to save markdown file
            move_to_processed: Whether to move image to processed folder

        Returns:
            ProcessedDocument with results
        """
        logger.info(f"Processing image: {image_path}")

        try:
            # Validate image exists
            if not image_path.exists():
                raise FileNotFoundError(f"Image not found: {image_path}")

            # Preprocess image
            preprocessed_path = await self.preprocessor.preprocess_image(image_path)

            # Extract text using OCR engine
            ocr_result = await self.engine.extract_text(preprocessed_path)

            if not ocr_result.success:
                # OCR failed
                doc = ProcessedDocument(
                    image_path=image_path,
                    ocr_result=ocr_result,
                    status="failed",
                    error=ocr_result.error
                )

                # Move to failed directory
                if move_to_processed:
                    failed_path = self._move_to_failed(image_path)
                    doc.processed_image_path = failed_path

                return doc

            # Postprocess text
            cleaned_text = self.postprocessor.postprocess_text(ocr_result.text)
            ocr_result.text = cleaned_text

            # Determine status based on confidence
            status = "completed"
            if ocr_result.confidence < self.config.confidence_threshold:
                status = "review_needed"

            # Create processed document
            doc = ProcessedDocument(
                image_path=image_path,
                ocr_result=ocr_result,
                status=status
            )

            # Save markdown file
            if save_markdown:
                markdown_path = self._save_markdown(image_path, ocr_result)
                doc.markdown_path = markdown_path

            # Store in database BEFORE moving file (so we can get file stats)
            self.storage.store_processed_document(
                doc,
                workspace=self.workspace,
                database_name="uploads"
            )

            # Auto-sync to Notion if configured
            if notion_sync_available:
                notion_database_id = self._get_notion_database_id()
                if notion_database_id:
                    try:
                        page_id = await create_notion_page_from_ocr(
                            notion_database_id,
                            doc,
                            self.workspace
                        )
                        if page_id:
                            # Update storage with page ID (use original path as stored in DB)
                            self.storage.update_page_id(str(image_path), page_id)
                            logger.info(f"✓ Created Notion page: {page_id}")
                        else:
                            logger.warning("Notion page creation returned no page_id")
                    except Exception as e:
                        logger.warning(f"Failed to sync to Notion: {e}")
                        import traceback
                        logger.debug(traceback.format_exc())

            # Dual-write to MuninnDB if available
            if brain_integration_available and status == "completed":
                try:
                    db = get_db()
                    vector_mgr = VectorDBManager()

                    brain_content = ""
                    meta = doc.ocr_result.metadata if hasattr(doc.ocr_result, 'metadata') and doc.ocr_result.metadata else {}
                    
                    if "summary" in meta and meta["summary"]:
                        brain_content += f"Summary: {meta['summary']}\n\n"
                    if "action_items" in meta and meta["action_items"]:
                        brain_content += "Action Items:\n"
                        for action in meta["action_items"]:
                            brain_content += f"- {action}\n"
                        brain_content += "\n"

                    brain_content += f"Raw OCR Text:\n{doc.ocr_result.text}"

                    await capture_memory(
                        db=db,
                        vector_mgr=vector_mgr,
                        content=brain_content,
                        session_id="ocr_pipeline",
                        domain_name=self.workspace or "promaia",
                        confidence=doc.ocr_result.confidence or 0.9,
                        image_paths=[str(image_path)],
                        source="ocr"
                    )
                    logger.info(f"✓ Embedded {image_path.name} into MuninnDB")
                except Exception as e:
                    logger.warning(f"Failed to embed in MuninnDB: {e}")

            # Move image to processed directory (after all processing is complete)
            if move_to_processed:
                if status == "completed" or status == "review_needed":
                    processed_path = self._move_to_processed(image_path)
                    doc.processed_image_path = processed_path
                else:
                    failed_path = self._move_to_failed(image_path)
                    doc.processed_image_path = failed_path

            # Clean up temporary preprocessed image
            if preprocessed_path != image_path and preprocessed_path.exists():
                preprocessed_path.unlink()

            logger.info(
                f"Successfully processed {image_path.name} "
                f"(confidence: {ocr_result.confidence:.2f}, status: {status})"
            )

            return doc

        except Exception as e:
            logger.error(f"Error processing image {image_path}: {e}")

            doc = ProcessedDocument(
                image_path=image_path,
                ocr_result=OCRResult(text="", confidence=0.0, success=False, error=str(e)),
                status="failed",
                error=str(e)
            )

            # Move to failed directory
            if move_to_processed:
                try:
                    failed_path = self._move_to_failed(image_path)
                    doc.processed_image_path = failed_path
                except Exception as move_error:
                    logger.error(f"Failed to move image to failed directory: {move_error}")

            return doc

    async def process_directory(
        self,
        directory: Optional[Path] = None,
        batch_size: int = None,
        recursive: bool = False
    ) -> List[ProcessedDocument]:
        """
        Process all images in a directory.

        Args:
            directory: Directory to process (default: config uploads_directory)
            batch_size: Number of images to process in parallel (default: config batch_size)
            recursive: Whether to process subdirectories

        Returns:
            List of processed documents
        """
        if directory is None:
            directory = Path(self.config.uploads_directory)

        if batch_size is None:
            batch_size = self.config.batch_size

        # Find all image files
        image_files = self._find_image_files(directory, recursive)

        if not image_files:
            logger.info(f"No images found in {directory}")
            return []

        logger.info(f"Found {len(image_files)} images to process")

        # Process images in batches
        results = []
        for i in range(0, len(image_files), batch_size):
            batch = image_files[i:i + batch_size]
            logger.info(
                f"Processing batch {i // batch_size + 1} "
                f"({len(batch)} images)"
            )

            # Process batch sequentially for now
            # Could be parallelized with asyncio.gather in the future
            for image_path in batch:
                result = await self.process_image(image_path)
                results.append(result)

        # Log summary
        self._log_summary(results)

        return results

    def _find_image_files(
        self,
        directory: Path,
        recursive: bool = False
    ) -> List[Path]:
        """
        Find all image files in directory.

        Args:
            directory: Directory to search
            recursive: Whether to search subdirectories

        Returns:
            List of image file paths
        """
        supported_formats = self.engine.get_supported_formats()
        image_files = []

        pattern = "**/*" if recursive else "*"

        for file_path in directory.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in supported_formats:
                image_files.append(file_path)

        # Sort by modification time (oldest first)
        image_files.sort(key=lambda p: p.stat().st_mtime)

        return image_files

    def _save_markdown(self, image_path: Path, ocr_result: OCRResult) -> Path:
        """
        Save OCR result as markdown file.

        Args:
            image_path: Original image path
            ocr_result: OCR result

        Returns:
            Path to saved markdown file
        """
        # Create markdown directory if needed
        md_dir = Path("data/md/ocr")
        md_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename: YYYY-MM-DD filename.md
        date_str = datetime.now().strftime("%Y-%m-%d")
        md_filename = f"{date_str} {image_path.stem}.md"
        md_path = md_dir / md_filename

        # Create metadata
        metadata = {
            "title": image_path.stem,
            "source_image": str(image_path),
            "confidence": f"{ocr_result.confidence:.2f}",
            "language": ocr_result.language,
            "processed_date": datetime.now().isoformat(),
            "text_length": len(ocr_result.text)
        }
        
        # Inject Gemini semantic insights
        if hasattr(ocr_result, 'metadata') and ocr_result.metadata:
            metadata.update(ocr_result.metadata)

        # Create markdown content
        markdown_content = create_ocr_markdown(
            text=ocr_result.text,
            title=image_path.stem,
            metadata=metadata
        )

        # Write to file
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        logger.debug(f"Saved markdown to {md_path}")

        return md_path

    def _move_to_processed(self, image_path: Path) -> Path:
        """
        Move image to processed directory.

        Args:
            image_path: Image to move

        Returns:
            New path
        """
        processed_dir = Path(self.config.processed_directory)
        processed_dir.mkdir(parents=True, exist_ok=True)

        dest_path = processed_dir / image_path.name

        # Handle name conflicts
        counter = 1
        while dest_path.exists():
            dest_path = processed_dir / f"{image_path.stem}_{counter}{image_path.suffix}"
            counter += 1

        shutil.move(str(image_path), str(dest_path))
        logger.debug(f"Moved image to {dest_path}")

        return dest_path

    def _move_to_failed(self, image_path: Path) -> Path:
        """
        Move image to failed directory.

        Args:
            image_path: Image to move

        Returns:
            New path
        """
        failed_dir = Path(self.config.failed_directory)
        failed_dir.mkdir(parents=True, exist_ok=True)

        dest_path = failed_dir / image_path.name

        # Handle name conflicts
        counter = 1
        while dest_path.exists():
            dest_path = failed_dir / f"{image_path.stem}_{counter}{image_path.suffix}"
            counter += 1

        shutil.move(str(image_path), str(dest_path))
        logger.debug(f"Moved image to failed directory: {dest_path}")

        return dest_path

    def _log_summary(self, results: List[ProcessedDocument]):
        """
        Log summary of processing results.

        Args:
            results: List of processed documents
        """
        total = len(results)
        completed = sum(1 for r in results if r.status == "completed")
        review_needed = sum(1 for r in results if r.status == "review_needed")
        failed = sum(1 for r in results if r.status == "failed")

        avg_confidence = sum(
            r.ocr_result.confidence for r in results if r.ocr_result
        ) / total if total > 0 else 0.0

        logger.info("=" * 60)
        logger.info("OCR Processing Summary")
        logger.info("=" * 60)
        logger.info(f"Total images:        {total}")
        logger.info(f"Completed:           {completed}")
        logger.info(f"Review needed:       {review_needed}")
        logger.info(f"Failed:              {failed}")
        logger.info(f"Average confidence:  {avg_confidence:.2f}")
        logger.info("=" * 60)
