"""
Event models for the notification routing pipeline.

Defines the Urgency enum and Event dataclass used throughout
the event bus layer (07-01).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class Urgency(str, Enum):
    """How urgently an event should reach the user."""
    INTERRUPT = "interrupt"
    DIGEST = "digest"
    ARCHIVE = "archive"


@dataclass(frozen=True)
class Event:
    """A routable event emitted by an agent execution."""
    id: int
    type: str
    payload: dict
    source: str
    urgency: Urgency
    created_at: datetime
    held_until: Optional[datetime] = None
    routed_at: Optional[datetime] = None
    channel: Optional[str] = None
