"""
Image processing utilities for chat with vision models.

This module provides functionality to handle image inputs for all supported AI models:
- OpenAI GPT-4o (vision)
- Anthropic Claude Sonnet 4 (vision) 
- Google Gemini 2.5 Pro (multimodal)
- Local Llama (vision models like LLaVA)
"""

import base64
import io
from typing import List, Dict, Any, Optional, Union, Tuple
from PIL import Image
import mimetypes
import os
from pathlib import Path

# Supported image formats
SUPPORTED_FORMATS = {
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
    'image/webp': ['.webp'],
    'image/gif': ['.gif']  # Non-animated only for most models
}

# Maximum image size (in bytes) - 20MB
MAX_IMAGE_SIZE = 20 * 1024 * 1024

# Maximum image dimensions
MAX_IMAGE_DIMENSIONS = (4096, 4096)

def validate_image_format(filename: str, media_type: str = None) -> str:
    """
    Validate that the image format is supported.
    
    Args:
        filename: The filename of the image
        media_type: Optional MIME type override
        
    Returns:
        The validated MIME type
        
    Raises:
        ValueError: If the format is not supported
    """
    if media_type:
        if media_type not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported image format: {media_type}")
        return media_type
    
    # Try to determine from filename
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type or mime_type not in SUPPORTED_FORMATS:
        # Try by extension
        ext = Path(filename).suffix.lower()
        for supported_type, extensions in SUPPORTED_FORMATS.items():
            if ext in extensions:
                return supported_type
        
        raise ValueError(f"Unsupported image format for file: {filename}")
    
    return mime_type

def encode_image_from_path(image_path: str, max_size: Optional[Tuple[int, int]] = None) -> Dict[str, str]:
    """
    Encode an image from file path to base64.
    
    Args:
        image_path: Path to the image file
        max_size: Optional maximum dimensions (width, height)
        
    Returns:
        Dict with 'data' (base64) and 'media_type' keys
        
    Raises:
        FileNotFoundError: If the image file doesn't exist
        ValueError: If the image format is not supported or file is too large
        IOError: If the image cannot be processed
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")
    
    # Check file size
    file_size = os.path.getsize(image_path)
    if file_size > MAX_IMAGE_SIZE:
        raise ValueError(f"Image file too large: {file_size} bytes (max: {MAX_IMAGE_SIZE})")
    
    # Validate format
    media_type = validate_image_format(image_path)
    
    try:
        # Open and process image
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (for JPEG compatibility)
            if img.mode in ('RGBA', 'LA', 'P'):
                if media_type == 'image/jpeg':
                    # Convert RGBA to RGB with white background for JPEG
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
            
            # Resize if needed
            if max_size or img.size[0] > MAX_IMAGE_DIMENSIONS[0] or img.size[1] > MAX_IMAGE_DIMENSIONS[1]:
                target_size = max_size or MAX_IMAGE_DIMENSIONS
                img.thumbnail(target_size, Image.Resampling.LANCZOS)
            
            # Save to bytes
            img_bytes = io.BytesIO()
            format_map = {
                'image/jpeg': 'JPEG',
                'image/png': 'PNG', 
                'image/webp': 'WEBP',
                'image/gif': 'GIF'
            }
            img.save(img_bytes, format=format_map[media_type], quality=85, optimize=True)
            img_bytes.seek(0)
            
            # Encode to base64
            base64_data = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
            
            return {
                'data': base64_data,
                'media_type': media_type
            }
            
    except Exception as e:
        raise IOError(f"Failed to process image {image_path}: {str(e)}")

def encode_image_from_bytes(image_data: bytes, filename: str = None, media_type: str = None) -> Dict[str, str]:
    """
    Encode an image from bytes to base64.
    
    Args:
        image_data: Raw image bytes
        filename: Optional filename for format detection
        media_type: Optional MIME type override
        
    Returns:
        Dict with 'data' (base64) and 'media_type' keys
        
    Raises:
        ValueError: If the image format is not supported or data is too large
        IOError: If the image cannot be processed
    """
    if len(image_data) > MAX_IMAGE_SIZE:
        raise ValueError(f"Image data too large: {len(image_data)} bytes (max: {MAX_IMAGE_SIZE})")
    
    try:
        # Open image from bytes to validate
        img = Image.open(io.BytesIO(image_data))
        
        # Try to determine media type
        if not media_type:
            if filename:
                media_type = validate_image_format(filename)
            else:
                # Try to detect from image format
                format_to_mime = {
                    'JPEG': 'image/jpeg',
                    'PNG': 'image/png',
                    'WEBP': 'image/webp',
                    'GIF': 'image/gif'
                }
                media_type = format_to_mime.get(img.format, 'image/jpeg')
        
        validate_image_format("", media_type)  # Validate the detected type
        
        # Process similar to file encoding
        if img.mode in ('RGBA', 'LA', 'P'):
            if media_type == 'image/jpeg':
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
        
        # Resize if needed
        if img.size[0] > MAX_IMAGE_DIMENSIONS[0] or img.size[1] > MAX_IMAGE_DIMENSIONS[1]:
            img.thumbnail(MAX_IMAGE_DIMENSIONS, Image.Resampling.LANCZOS)
        
        # Save to bytes
        img_bytes = io.BytesIO()
        format_map = {
            'image/jpeg': 'JPEG',
            'image/png': 'PNG',
            'image/webp': 'WEBP', 
            'image/gif': 'GIF'
        }
        img.save(img_bytes, format=format_map[media_type], quality=85, optimize=True)
        img_bytes.seek(0)
        
        # Encode to base64
        base64_data = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
        
        return {
            'data': base64_data,
            'media_type': media_type
        }
        
    except Exception as e:
        raise IOError(f"Failed to process image data: {str(e)}")

def format_image_for_openai(base64_data: str, media_type: str) -> Dict[str, Any]:
    """
    Format image data for OpenAI GPT-4o Vision API.
    
    Args:
        base64_data: Base64 encoded image data
        media_type: MIME type of the image
        
    Returns:
        Formatted message content for OpenAI API
    """
    return {
        "type": "image_url",
        "image_url": {
            "url": f"data:{media_type};base64,{base64_data}",
            "detail": "high"  # Can be "low", "high", or "auto"
        }
    }

def format_image_for_anthropic(base64_data: str, media_type: str) -> Dict[str, Any]:
    """
    Format image data for Anthropic Claude API.
    
    Args:
        base64_data: Base64 encoded image data
        media_type: MIME type of the image
        
    Returns:
        Formatted message content for Anthropic API
    """
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64_data
        }
    }

def format_image_for_gemini(base64_data: str, media_type: str) -> Dict[str, str]:
    """
    Format image data for Google Gemini API.
    
    Args:
        base64_data: Base64 encoded image data  
        media_type: MIME type of the image
        
    Returns:
        Formatted image data for Gemini API
    """
    return {
        "mime_type": media_type,
        "data": base64_data
    }

def format_image_for_llama(base64_data: str, media_type: str) -> Dict[str, Any]:
    """
    Format image data for local Llama models (like LLaVA).
    This follows the OpenAI-compatible format used by many local inference servers.
    
    Args:
        base64_data: Base64 encoded image data
        media_type: MIME type of the image
        
    Returns:
        Formatted message content for Llama API
    """
    return {
        "type": "image_url", 
        "image_url": {
            "url": f"data:{media_type};base64,{base64_data}"
        }
    }

def is_vision_supported(model_type: str) -> bool:
    """
    Check if the given model type supports vision/image inputs.
    
    Args:
        model_type: The model type ('openai', 'anthropic', 'gemini', 'llama')
        
    Returns:
        True if vision is supported, False otherwise
    """
    # All the configured models support vision
    vision_models = {'openai', 'anthropic', 'gemini', 'llama'}
    return model_type.lower() in vision_models

def get_model_image_limits(model_type: str) -> Dict[str, Any]:
    """
    Get image processing limits for a specific model.
    
    Args:
        model_type: The model type
        
    Returns:
        Dict with 'max_images', 'max_size', and 'supported_formats' keys
    """
    limits = {
        'openai': {
            'max_images': 10,  # Per message
            'max_size': MAX_IMAGE_SIZE,
            'supported_formats': list(SUPPORTED_FORMATS.keys())
        },
        'anthropic': {
            'max_images': 5,   # Per message  
            'max_size': MAX_IMAGE_SIZE,
            'supported_formats': ['image/jpeg', 'image/png', 'image/webp']
        },
        'gemini': {
            'max_images': 16,  # Per message
            'max_size': MAX_IMAGE_SIZE, 
            'supported_formats': list(SUPPORTED_FORMATS.keys())
        },
        'llama': {
            'max_images': 1,   # Most vision models support 1 image
            'max_size': MAX_IMAGE_SIZE,
            'supported_formats': ['image/jpeg', 'image/png']
        }
    }
    
    return limits.get(model_type.lower(), limits['openai'])  # Default to OpenAI limits
