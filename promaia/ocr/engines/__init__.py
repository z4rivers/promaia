"""OCR engines module for Promaia."""

from promaia.ocr.engines.base import BaseOCREngine, OCRResult, TextRegion
from promaia.ocr.engines.mock import MockOCREngine

# Optional engines
try:
    from promaia.ocr.engines.google_vision import GoogleVisionEngine
except ImportError:
    pass

try:
    from promaia.ocr.engines.gemini_semantic import GeminiSemanticEngine
except ImportError:
    pass

__all__ = [
    "BaseOCREngine",
    "OCRResult",
    "TextRegion",
    "MockOCREngine",
    "GoogleVisionEngine",
    "GeminiSemanticEngine",
]
