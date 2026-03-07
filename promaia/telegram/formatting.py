"""
Telegram message formatting utilities.

Handles splitting long messages at the 4096-character Telegram limit,
preferring paragraph and line boundaries for clean splits.
"""
import logging
from typing import List

from aiogram.types import Message

logger = logging.getLogger(__name__)

# Telegram maximum message length
MAX_MESSAGE_LENGTH = 4096


def _split_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> List[str]:
    """
    Split a long message into chunks that fit Telegram's character limit.

    Splits at paragraph boundaries first, then line boundaries, then hard-cuts
    as a last resort.

    Args:
        text: Text to split.
        max_length: Maximum length per chunk (default: 4096).

    Returns:
        List of message chunks.
    """
    if len(text) <= max_length:
        return [text]

    chunks: List[str] = []
    current_chunk = ""

    # Split by paragraphs first
    paragraphs = text.split("\n\n")

    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 <= max_length:
            current_chunk += para + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())

            # If paragraph itself exceeds max_length, split by lines
            if len(para) > max_length:
                lines = para.split("\n")
                current_chunk = ""
                for line in lines:
                    if len(current_chunk) + len(line) + 1 <= max_length:
                        current_chunk += line + "\n"
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        # If a single line exceeds max_length, hard-cut it
                        if len(line) > max_length:
                            while line:
                                chunks.append(line[:max_length])
                                line = line[max_length:]
                            current_chunk = ""
                        else:
                            current_chunk = line + "\n"
            else:
                current_chunk = para + "\n\n"

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


async def send_long_message(message: Message, text: str) -> None:
    """
    Send text to a Telegram chat, splitting into multiple messages if needed.

    Args:
        message: The incoming aiogram Message to reply to.
        text: The text to send (may exceed 4096 chars).
    """
    chunks = _split_message(text)
    for chunk in chunks:
        await message.answer(chunk)
