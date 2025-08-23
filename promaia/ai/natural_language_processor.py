"""
Complete natural language processing system for Promaia.
Replaces Vanna.ai with pattern-based processing and schema-aware SQL generation.
"""
import sqlite3
from typing import List, Dict, Any, Tuple
from .pattern_based_nl import PatternBasedNLProcessor, QueryIntent, QueryType
from .sql_generator import SchemaAwareSQLGenerator


class NaturalLanguageProcessor:
    """
    Main interface for natural language query processing.
    Combines pattern recognition, query classification, and SQL generation.
    """
    
    def __init__(self, db_path: str = "data/hybrid_metadata.db"):
        self.db_path = db_path
        self.pattern_processor = PatternBasedNLProcessor(db_path)
        self.sql_generator = SchemaAwareSQLGenerator(db_path)
    
    def process_query(self, nl_prompt: str, scope_databases: List[str] = None) -> Dict[str, Any]:
        """
        Main entry point: process natural language query and return results.
        
        Args:
            nl_prompt: Natural language query string
            scope_databases: Optional list of databases from -b parameter
            
        Returns:
            Dictionary with query results and metadata
        """
        try:
            # Step 1: Parse natural language into structured intent
            intent = self.pattern_processor.process_nl_query(nl_prompt, scope_databases)
            
            # Step 2: Classify query type for performance optimization  
            query_type = self.pattern_processor.classify_query_type(intent)
            
            # Step 3: Generate optimized SQL
            sql = self.sql_generator.generate_sql(intent, query_type)
            
            # Step 4: Execute query
            results = self._execute_sql(sql)
            
            # Step 5: Return structured response
            return {
                "success": True,
                "results": results,
                "intent": {
                    "pattern_type": intent.pattern_type,
                    "sources": intent.sources,
                    "query_type": query_type.value,
                    "content_search": intent.content_search
                },
                "sql": sql,
                "count": len(results)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "results": [],
                "intent": None,
                "sql": None,
                "count": 0
            }
    
    def _execute_sql(self, sql: str) -> List[Dict[str, Any]]:
        """Execute SQL query and return results as list of dictionaries."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row  # Enable column access by name
                cursor = conn.cursor()
                cursor.execute(sql)
                
                results = []
                for row in cursor.fetchall():
                    results.append(dict(row))
                
                return results
                
        except Exception as e:
            print(f"SQL execution error: {e}")
            print(f"SQL: {sql}")
            raise

    def validate_query_intent(self, intent: QueryIntent) -> Tuple[bool, str]:
        """Validate that the parsed intent makes sense."""
        
        # Check for required fields
        if not intent.pattern_type:
            return False, "No pattern type identified"
        
        # Validate time constraints for temporal queries
        if intent.pattern_type in ["monthly_samples", "weekly_samples", "date_range"]:
            if not intent.time_constraints:
                return False, f"Missing time constraints for {intent.pattern_type}"
        
        # Validate search terms for content queries
        if intent.content_search and not intent.search_terms:
            return False, "Content search requested but no search terms provided"
        
        # Validate property filters
        if intent.pattern_type == "property_filter" and not intent.property_filters:
            return False, "Property filter requested but no properties specified"
        
        return True, "Valid"

    def get_query_explanation(self, intent: QueryIntent, query_type: QueryType) -> str:
        """Generate human-readable explanation of what the query will do."""
        
        explanations = {
            "monthly_samples": f"Getting monthly samples from {', '.join(intent.sources or ['all databases'])} since {intent.time_constraints.get('start_date', 'specified date')}",
            "weekly_samples": f"Getting weekly samples from {', '.join(intent.sources or ['all databases'])}",
            "date_range": f"Getting content from the last {intent.time_constraints.get('days_back', 'N')} days",
            "content_search": f"Searching for '{', '.join(intent.search_terms)}' in content",
            "metadata_search": f"Finding items from {intent.person_filter} (metadata only)",
            "property_filter": f"Filtering by properties: {intent.property_filters}",
            "cross_source": f"Searching across {', '.join(intent.sources)} for '{', '.join(intent.search_terms)}'",
        }
        
        base_explanation = explanations.get(intent.pattern_type, f"Processing {intent.pattern_type} query")
        
        # Add performance note
        performance_note = ""
        if query_type == QueryType.METADATA_ONLY:
            performance_note = " (optimized: metadata only)"
        elif query_type == QueryType.CONTENT_REQUIRED:
            performance_note = " (includes full content search)"
        
        return base_explanation + performance_note


def process_natural_language_to_content(nl_prompt: str, workspace: str = None, 
                                      database_names: List[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Legacy compatibility function - replaces the old Vanna-based implementation.
    
    This function maintains the same interface as the old system for seamless migration.
    Returns a dictionary with database names as keys and lists of results as values.
    """
    processor = NaturalLanguageProcessor()
    
    # Convert legacy parameters to new scope format
    scope_databases = database_names or []
    
    # Process the query
    result = processor.process_query(nl_prompt, scope_databases)
    
    if result["success"]:
        print(f"✅ Natural language query processed: {result['count']} results")
        print(f"   Pattern: {result['intent']['pattern_type']}")
        print(f"   Type: {result['intent']['query_type']}")
        
        # Group results by database_name to match expected format
        grouped_results = {}
        for item in result["results"]:
            db_name = item.get("database_name", "unknown")
            if db_name not in grouped_results:
                grouped_results[db_name] = []
            grouped_results[db_name].append(item)
        
        return grouped_results
    else:
        print(f"❌ Natural language query failed: {result['error']}")
        return {}


# For backward compatibility during transition
class PatternBasedSQLGenerator:
    """Drop-in replacement for VannaSQLGenerator with same interface."""
    
    def __init__(self):
        self.processor = NaturalLanguageProcessor()
        self.initialized = True
    
    def generate_sql(self, question: str, database_names: List[str] = None) -> str:
        """Generate SQL from natural language - compatible with old interface."""
        intent = self.processor.pattern_processor.process_nl_query(question, database_names)
        query_type = self.processor.pattern_processor.classify_query_type(intent)
        return self.processor.sql_generator.generate_sql(intent, query_type)
    
    def execute_sql_and_get_data(self, sql: str) -> List[Dict[str, Any]]:
        """Execute SQL and return results - compatible with old interface."""
        return self.processor._execute_sql(sql)