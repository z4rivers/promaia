"""
Gemini Semantic OCR Engine for Promaia.

Extracts verbatim text alongside rich semantic metadata (summary, entities, actions)
using Gemini 3 Flash.
"""
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from promaia.ocr.engines.base import BaseOCREngine, OCRResult
from promaia.ai.models import GOOGLE_MODELS

try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    GOOGLE_GENAI_AVAILABLE = True
except ImportError:
    GOOGLE_GENAI_AVAILABLE = False


logger = logging.getLogger(__name__)


class SemanticExtraction(BaseModel):
    """Structured output expected from Gemini OCR."""
    verbatim_text: str = Field(description="The exact text extracted from the document, preserving structure.")
    document_type: str = Field(description="The type of document (e.g., Receipt, Handwritten Note, Screenshot, Schematic, Article).")
    summary: str = Field(description="A concise 1-3 sentence summary of the document's contents and purpose.")
    entities: List[str] = Field(description="Key entities mentioned (People, Companies, Places). Empty list if none.")
    action_items: List[str] = Field(description="Implicit or explicit action items derived from the document. Empty list if none.")


class GeminiSemanticEngine(BaseOCREngine):
    """
    OCR engine using Gemini 3 Flash to extract text and semantic metadata.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize engine with configuration."""
        super().__init__(config)
        self.api_key = self.config.get("api_key") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        
        if not self.api_key:
            logger.warning("No API key found for GeminiSemanticEngine.")
            
        if GOOGLE_GENAI_AVAILABLE and self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

        self.model_name = self.config.get("model", GOOGLE_MODELS.get("flash", "gemini-3-flash-preview"))

    def preprocess_config(self) -> bool:
        """Validate configuration."""
        if not GOOGLE_GENAI_AVAILABLE:
            logger.error("google-genai package is required. Install with: pip install google-genai")
            return False
            
        if not self.api_key:
            logger.error("No API key provided. Set GEMINI_API_KEY or configure in promaia.config.json")
            return False
            
        return True

    def get_supported_formats(self) -> List[str]:
        """Get supported formats."""
        return ['.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif']

    async def extract_text(self, image_path: Path) -> OCRResult:
        """
        Extract text and semantic metadata from an image using Gemini.
        """
        start_time = time.time()
        
        try:
            self.validate_image_path(image_path)
            
            if not self.client:
                raise RuntimeError("Engine not properly initialized (missing API key or google-genai package)")

            # Read image file to bytes
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            mime_type = "image/jpeg"
            if image_path.suffix.lower() == ".png":
                mime_type = "image/png"
            elif image_path.suffix.lower() == ".webp":
                mime_type = "image/webp"

            prompt = (
                "You are an advanced semantic OCR engine. Analyze the provided image and extract "
                "the exact verbatim text, preserving its paragraph structure and line breaks where appropriate. "
                "Additionally, classify the document type, provide a concise summary, extract key entities "
                "(people, companies, places), and list any implicit or explicit action items."
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=SemanticExtraction,
                    temperature=0.1, # Low temperature for more deterministic OCR
                ),
            )

            # Parse the JSON response
            raw_json = response.text
            extracted = SemanticExtraction.model_validate_json(raw_json)
            
            processing_time = time.time() - start_time
            
            # Construct metadata
            metadata = {
                "api": "gemini",
                "model": self.model_name,
                "document_type": extracted.document_type,
                "summary": extracted.summary,
                "entities": extracted.entities,
                "action_items": extracted.action_items
            }
            
            return OCRResult(
                text=extracted.verbatim_text,
                confidence=1.0, # Generative AI doesn't give a standard word-level confidence
                metadata=metadata,
                processing_time=processing_time,
                success=True
            )

        except Exception as e:
            self.logger.error(f"Error during Gemini OCR processing: {e}")
            processing_time = time.time() - start_time
            return OCRResult(
                text="",
                confidence=0.0,
                success=False,
                error=str(e),
                processing_time=processing_time
            )
