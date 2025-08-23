"""
Pattern-based natural language query processing for Promaia.

Replaces Vanna.ai with focused pattern recognition for common query types.
Optimized for the primary use case: complex time-based queries that are painful to type.
"""
import re
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class QueryType(Enum):
    """Types of queries for performance optimization."""
    METADATA_ONLY = "metadata"
    CONTENT_REQUIRED = "content"
    HYBRID = "hybrid"


@dataclass
class QueryIntent:
    """Structured representation of user intent."""
    pattern_type: str
    sources: List[str]
    time_constraints: Optional[Dict[str, Any]] = None
    search_terms: List[str] = None
    quantity_hint: Optional[str] = None
    person_filter: Optional[str] = None
    property_filters: Dict[str, str] = None
    content_search: bool = False

    def __post_init__(self):
        if self.search_terms is None:
            self.search_terms = []
        if self.property_filters is None:
            self.property_filters = {}


class PatternBasedNLProcessor:
    """
    Focus on painful-to-type patterns, not general NL.
    Handles the 20% of patterns that solve 80% of user needs.
    """
    
    # Core patterns that are painful to type manually
    COMMON_PATTERNS = {
        # Primary use case: "monthly journal entries since December 2024"
        "monthly_samples": r"(month|monthly).*(since|from)\s+(\w+\s+\d{4})",
        
        # Time-based patterns (order matters - specific patterns first)
        "weekly_samples": r"(week|weekly).*(since|from)\s+(\w+\s*\d*)",
        "last_timeframe": r"(last|past)\s+(week|month|day|year)",  # Must be before date_ranges
        "date_ranges": r"(last|past)\s+(\d+)\s+(days?|weeks?|months?)",
        "recent_content": r"(recent|latest|newest)\s+(\w+)",
        
        # Cross-database queries  
        "cross_source": r"(\w+)\s+and\s+(\w+).*(about|containing|related to)\s+(.+)",
        
        # Quantity-based sampling
        "quantity_based": r"(few|several|some|smattering|handful)\s+(.+?)(?:\s+from|\s+of|\s+in|$)",
        
        # Content vs metadata patterns
        "content_search": r"(contains?|containing|includes?|including|has|have)\s+(the\s+)?(word|phrase|sentence|text)?\s*[\"']([^\"']+)[\"']",
        "quoted_content": r"[\"']([^\"']{3,})[\"']",
        "metadata_search": r"(from|by|sent by|created by|authored by)\s+(\w+)",
        
        # Property filtering (Notion-style)
        "property_filter": r"(\w+)\s+with\s+(\w+)\s+(?:of\s+)?(?:is\s+)?(\w+)",
        "status_filter": r"(status|priority|category)\s+(?:of\s+)?(?:is\s+)?(\w+)",
    }
    
    # Quantity mappings
    QUANTITY_MAPPINGS = {
        "smattering": 5,
        "few": 3,
        "handful": 7,
        "several": 12,
        "some": 8,
        "couple": 2,
    }

    def __init__(self, db_path: str = "data/hybrid_metadata.db"):
        self.db_path = db_path

    def process_nl_query(self, query: str, scope_databases: List[str] = None) -> QueryIntent:
        """
        Main entry point: convert natural language to structured intent.
        
        Args:
            query: Natural language query string
            scope_databases: Databases from -b parameter (scope constraint)
            
        Returns:
            QueryIntent with structured query components
        """
        query = query.strip().lower()
        
        # Try pattern matching first (fast, predictable)
        for pattern_name, regex in self.COMMON_PATTERNS.items():
            if match := re.search(regex, query, re.IGNORECASE):
                return self._process_pattern(pattern_name, match, query, scope_databases)
        
        # Fallback: simple intent parsing
        return self._parse_simple_intent(query, scope_databases)

    def _process_pattern(self, pattern_name: str, match: re.Match, 
                        original_query: str, scope_databases: List[str]) -> QueryIntent:
        """Process recognized patterns into structured intent."""
        
        if pattern_name == "monthly_samples":
            return self._process_monthly_request(match, scope_databases)
        
        elif pattern_name == "weekly_samples":
            return self._process_weekly_request(match, scope_databases)
        
        elif pattern_name in ["date_ranges", "last_timeframe"]:
            return self._process_date_range_request(match, scope_databases, original_query)
            
        elif pattern_name == "cross_source":
            return self._process_cross_source_request(match, scope_databases)
            
        elif pattern_name == "quantity_based":
            return self._process_quantity_request(match, scope_databases)
            
        elif pattern_name in ["content_search", "quoted_content"]:
            return self._process_content_search(match, scope_databases, original_query)
            
        elif pattern_name == "metadata_search":
            return self._process_metadata_search(match, scope_databases)
            
        elif pattern_name in ["property_filter", "status_filter"]:
            return self._process_property_filter(match, scope_databases)
        
        # Default fallback
        return self._parse_simple_intent(original_query, scope_databases)

    def _process_monthly_request(self, match: re.Match, scope_databases: List[str]) -> QueryIntent:
        """Handle primary use case: monthly sampling since a date."""
        start_date_str = match.group(3)  # "December 2024"
        
        try:
            # Parse date string like "December 2024"
            start_date = datetime.strptime(start_date_str, "%B %Y")
        except ValueError:
            try:
                start_date = datetime.strptime(start_date_str, "%b %Y")
            except ValueError:
                # Fallback to current date - 3 months
                start_date = datetime.now() - timedelta(days=90)
        
        return QueryIntent(
            pattern_type="monthly_samples",
            sources=scope_databases or ["journal"],  # Default to journal if no scope
            time_constraints={
                "type": "monthly_samples",
                "start_date": start_date.isoformat(),
                "sample_per_month": 25  # Reasonable sample size
            },
            quantity_hint="monthly"
        )

    def _process_weekly_request(self, match: re.Match, scope_databases: List[str]) -> QueryIntent:
        """Handle weekly sampling requests."""
        return QueryIntent(
            pattern_type="weekly_samples", 
            sources=scope_databases or ["journal"],
            time_constraints={
                "type": "weekly_samples",
                "sample_per_week": 8
            },
            quantity_hint="weekly"
        )

    def _process_date_range_request(self, match: re.Match, scope_databases: List[str], original_query: str) -> QueryIntent:
        """Handle 'last N days/weeks/months' or 'last week/month' patterns."""
        # Handle both "last 2 weeks" and "last week" patterns
        groups = match.groups()
        
        if len(groups) >= 3 and groups[1] and groups[1].isdigit():
            # Pattern like "last 2 weeks"
            quantity = int(groups[1])
            unit = groups[2].rstrip('s') if groups[2] else "day"
        elif len(groups) >= 2:
            # Pattern like "last week"  
            quantity = 1
            unit = groups[1].rstrip('s') if groups[1] else "day"
        else:
            # Fallback
            quantity = 1
            unit = "day"
        
        if unit == "day":
            days_back = quantity
        elif unit == "week":
            days_back = quantity * 7
        elif unit == "month":
            days_back = quantity * 30
        elif unit == "year":
            days_back = quantity * 365
        else:
            days_back = 7  # Default fallback
        
        start_date = datetime.now() - timedelta(days=days_back)
        
        # Infer database from content type in query
        inferred_sources = []
        if "journal" in original_query.lower():
            inferred_sources = ["journal"]
        elif "email" in original_query.lower() or "gmail" in original_query.lower():
            inferred_sources = ["gmail"]
        elif "discord" in original_query.lower() or "message" in original_query.lower():
            inferred_sources = ["discord"]
        
        return QueryIntent(
            pattern_type="date_range",
            sources=scope_databases or inferred_sources,
            time_constraints={
                "type": "date_range",
                "start_date": start_date.isoformat(),
                "days_back": days_back
            },
            quantity_hint=f"last_{quantity}_{unit}s"
        )

    def _process_cross_source_request(self, match: re.Match, scope_databases: List[str]) -> QueryIntent:
        """Handle cross-database queries like 'emails and journal about X'."""
        source1 = match.group(1)
        source2 = match.group(2) 
        search_term = match.group(4)
        
        # Map common terms to database names
        source_mappings = {
            "email": "gmail", "emails": "gmail", "mail": "gmail",
            "journal": "journal", "journals": "journal",
            "discord": "discord", "messages": "discord",
            "notion": "notion", "notes": "notion", "stories": "notion"
        }
        
        mapped_sources = []
        for source in [source1, source2]:
            mapped_sources.append(source_mappings.get(source, source))
        
        return QueryIntent(
            pattern_type="cross_source",
            sources=scope_databases or mapped_sources,
            search_terms=[search_term.strip()],
            content_search=True  # Cross-source usually requires content search
        )

    def _process_quantity_request(self, match: re.Match, scope_databases: List[str]) -> QueryIntent:
        """Handle quantity-based requests like 'a few entries from each month'."""
        quantity_word = match.group(1)
        content_type = match.group(2)
        
        quantity = self.QUANTITY_MAPPINGS.get(quantity_word, 10)
        
        return QueryIntent(
            pattern_type="quantity_based",
            sources=scope_databases or [],
            quantity_hint=quantity_word,
            time_constraints={
                "type": "limited_sample",
                "max_results": quantity
            }
        )

    def _process_content_search(self, match: re.Match, scope_databases: List[str], 
                               original_query: str) -> QueryIntent:
        """Handle explicit content searches with quoted text."""
        # Extract quoted content
        if match.lastindex >= 4:
            search_text = match.group(4)  # From content_search pattern
        else:
            search_text = match.group(1)  # From quoted_content pattern
        
        return QueryIntent(
            pattern_type="content_search",
            sources=scope_databases or [],
            search_terms=[search_text],
            content_search=True  # Explicitly requires content search
        )

    def _process_metadata_search(self, match: re.Match, scope_databases: List[str]) -> QueryIntent:
        """Handle metadata-only searches like 'emails from John'."""
        person = match.group(2)
        
        return QueryIntent(
            pattern_type="metadata_search",
            sources=scope_databases or ["gmail"],  # Default to email for person searches
            person_filter=person,
            content_search=False  # Explicitly metadata-only
        )

    def _process_property_filter(self, match: re.Match, scope_databases: List[str]) -> QueryIntent:
        """Handle property filtering like 'notion stories with status archived'."""
        content_type = match.group(1)
        property_name = match.group(2) 
        property_value = match.group(3)
        
        return QueryIntent(
            pattern_type="property_filter",
            sources=scope_databases or [content_type],
            property_filters={property_name: property_value},
            content_search=False  # Property filtering is metadata-only
        )

    def _parse_simple_intent(self, query: str, scope_databases: List[str]) -> QueryIntent:
        """Fallback: simple intent parsing for unrecognized patterns."""
        # Extract any quoted strings as search terms
        quoted_terms = re.findall(r'["\']([^"\']+)["\']', query)
        
        # Look for time indicators
        time_indicators = re.findall(r'(last|past|recent|since)\s+(\w+)', query)
        
        # Basic content vs metadata classification
        content_indicators = ["contains", "containing", "has", "mentions", "says", "discusses"]
        content_search = any(indicator in query for indicator in content_indicators)
        
        return QueryIntent(
            pattern_type="simple_intent",
            sources=scope_databases or [],
            search_terms=quoted_terms if quoted_terms else [query],
            content_search=content_search
        )

    def classify_query_type(self, intent: QueryIntent) -> QueryType:
        """Determine if query needs content, metadata, or both for performance optimization."""
        
        # Explicit content search patterns
        if (intent.content_search or 
            intent.pattern_type in ["content_search", "cross_source"] or
            any(term for term in intent.search_terms if len(term) > 10)):  # Long search terms likely need content
            return QueryType.CONTENT_REQUIRED
        
        # Explicit metadata patterns
        if (intent.pattern_type in ["metadata_search", "property_filter", "monthly_samples"] or
            intent.person_filter or 
            intent.property_filters):
            return QueryType.METADATA_ONLY
        
        # Default to metadata for performance
        return QueryType.METADATA_ONLY