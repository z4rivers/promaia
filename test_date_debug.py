#!/usr/bin/env python3

import sys
sys.path.append('/Users/kb20250422/Documents/dev/promaia')

from promaia.ai.intelligent_nl_processor import IntelligentNaturalLanguageProcessor
from datetime import datetime

def test_date_parsing():
    """Test date constraint parsing in NL queries."""

    processor = IntelligentNaturalLanguageProcessor()

    # Test queries that should have date constraints
    test_queries = [
        "emails with felipe",
        "emails with felipe from the last 1.5 months",
        "emails containing mgm from last 1.5 months"
    ]

    for query in test_queries:
        print(f"\n=== Testing: '{query}' ===")

        try:
            # Test the full processor
            result = processor.process_query(query, ["gmail", "trass.gmail"])

            # Debug: Get the processor's graph state to see the SQL
            from promaia.ai.langgraph_query_system import IntelligentQueryProcessor
            from promaia.ai.intelligent_nl_processor import PromaiLLMAdapter
            llm = PromaiLLMAdapter()
            query_processor = IntelligentQueryProcessor(llm, "data/hybrid_metadata.db")

            # Manually run the graph to get the state
            initial_state = {
                "user_query": f"From databases ['gmail', 'trass.gmail']: {query}",
                "parsed_intent": None,
                "available_schemas": None,
                "execution_plan": None,
                "generated_sql": None,
                "execution_results": None,
                "errors": [],
                "retry_count": 0,
                "final_results": None
            }

            final_state = query_processor.graph.invoke(initial_state)
            print(f"Generated SQL: {final_state.get('generated_sql', 'No SQL generated')}")
            print(f"Errors: {final_state.get('errors', [])}")

            print(f"Intent: {result.get('intent', {}).get('user_goal', 'N/A')}")
            if result.get('intent', {}).get('time_constraints'):
                print(f"Time constraints: {result['intent']['time_constraints']}")
            else:
                print("Time constraints: None")
            print(f"SQL: {result.get('sql', 'N/A')}")

            if result.get("success"):
                print(f"✅ Query successful: {len(result.get('results', {}))} results")
            else:
                print(f"❌ Query failed: {result.get('errors', [])}")

        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_date_parsing()
