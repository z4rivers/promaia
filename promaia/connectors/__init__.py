"""
Database connectors for Maia.

This module provides a plugin-based architecture for connecting to different data sources.
"""

from .base import BaseConnector, ConnectorRegistry
from .notion_connector import NotionConnector

# Try to import Gmail connector (optional dependency)
try:
    from .gmail_connector import GmailConnector
    ConnectorRegistry.register("gmail", GmailConnector)
    gmail_available = True
except ImportError:
    gmail_available = False

# Register available connectors
ConnectorRegistry.register("notion", NotionConnector)

__all__ = [
    'BaseConnector',
    'ConnectorRegistry',
    'NotionConnector'
]

if gmail_available:
    __all__.append('GmailConnector') 