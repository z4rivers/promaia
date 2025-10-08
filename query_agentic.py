#!/usr/bin/env python3
"""
Interactive agentic NL query tester.
Test natural language queries with learning, validation, and retry.
"""
import sys
import os

# Setup
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from promaia.utils.config import load_environment
load_environment()

from promaia.ai.intelligent_nl_processor_agentic import AgenticNLQueryProcessor
from promaia.utils.display import print_text


def main():
    # Check for debug mode
    debug_mode = os.getenv("MAIA_DEBUG") == "1" or "--debug" in sys.argv
    
    print_text("\n🚀 Agentic NL Query System - Interactive Mode", style="bold cyan")
    if debug_mode:
        print_text("🐛 DEBUG MODE ENABLED - Chain of thought visible", style="yellow")
    print_text("=" * 60, style="dim")
    print_text("Try queries like:", style="white")
    print_text("  • 'gmail with term avask'", style="dim")
    print_text("  • 'trass gmail from last month'", style="dim")
    print_text("  • 'journal entries from last week'", style="dim")
    print_text("  • 'stories about international'", style="dim")
    print_text("\nType 'quit' or Ctrl+C to exit", style="dim")
    if not debug_mode:
        print_text("Tip: Run with --debug or set MAIA_DEBUG=1 to see chain of thought", style="dim")
    print_text("=" * 60 + "\n", style="dim")
    
    # Initialize processor once
    processor = AgenticNLQueryProcessor(debug=debug_mode)
    
    while True:
        try:
            # Get query from user
            query = input("\n🔍 Your query: ").strip()
            
            if not query:
                continue
            
            if query.lower() in ['quit', 'exit', 'q']:
                print_text("\n👋 Goodbye!\n", style="cyan")
                break
            
            # Process the query
            print()  # Extra line for readability
            result = processor.process_query(query, max_retries=2)
            
            if result['success']:
                print_text("\n✅ Query completed successfully!", style="bold green")
                
                # Show quick stats
                summary = result['summary']
                print_text(f"   📊 Found {summary['total_count']} entries", style="white")
                print_text(f"   🗄️  Databases: {', '.join(summary['databases'])}", style="white")
                
                if result.get('learned'):
                    print_text("   🧠 Pattern saved for future learning!", style="green")
                
                # Ask if they want to see sample results
                if summary['total_count'] > 0:
                    try:
                        show_samples = input("\n   Show sample results? (y/N): ").strip().lower()
                        if show_samples in ['y', 'yes']:
                            print_text("\n📄 Sample Results:", style="cyan")
                            for i, result_item in enumerate(summary['sample_results'][:10], 1):
                                title = result_item.get('title', 'Untitled')[:70]
                                db = result_item.get('database_name', 'unknown')
                                date = result_item.get('created_time', 'N/A')[:10]
                                print_text(f"   {i}. [{db}] {title}", style="white")
                                print_text(f"      Date: {date}", style="dim")
                    except (KeyboardInterrupt, EOFError):
                        pass
            else:
                print_text(f"\n❌ Query failed: {result.get('error', 'Unknown error')}", style="bold red")
                print_text("   Try rephrasing or broadening your search", style="dim")
        
        except (KeyboardInterrupt, EOFError):
            print_text("\n\n👋 Goodbye!\n", style="cyan")
            break
        except Exception as e:
            print_text(f"\n❌ Error: {e}", style="red")
            import traceback
            if os.getenv("DEBUG"):
                traceback.print_exc()


if __name__ == "__main__":
    main()

