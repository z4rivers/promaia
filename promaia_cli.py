#!/usr/bin/env python
import argparse
import asyncio
import json
import sys
from datetime import datetime

from promaia.storage.postgres_db import get_postgres_db
from promaia.storage.vector_db import VectorDBManager
from promaia.brain.core.memory_pipeline import capture_memory

async def _do_capture(content: str, domain: str = None):
    db = get_postgres_db()
    vector_mgr = VectorDBManager()
    
    print(f"Capturing: {content}")
    results = await capture_memory(
        db=db,
        vector_mgr=vector_mgr,
        content=content,
        session_id="cli-session",
        domain_name=domain,
        source="cli"
    )
    
    action_count = results.get("action_count", 0)
    intel_counts = results.get("intel_counts", {})
    
    print("Capture complete!")
    if action_count > 0:
        print(f"-> Extracted {action_count} actionable items.")
    if sum(intel_counts.values()) > 0:
        print(f"-> Extracted intelligence: {intel_counts}")

def main():
    parser = argparse.ArgumentParser(description="Promaia CLI (Opus Interface)")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Capture command
    cap_parser = subparsers.add_parser("capture", help="Capture a memory or thought into Promaia's brain")
    cap_parser.add_argument("content", type=str, help="The content to remember")
    cap_parser.add_argument("--domain", "-d", type=str, help="Optional domain to tag this memory against", default=None)
    
    # Briefing command
    brief_parser = subparsers.add_parser("briefing", help="Get the current mental briefing")
    
    args = parser.parse_args()
    
    if args.command == "capture":
        asyncio.run(_do_capture(args.content, args.domain))
    elif args.command == "briefing":
        # We can reuse the MCP handler via direct import
        from promaia.brain.mcp.handlers.context_ops import _handle_briefing
        from promaia.brain.mcp.core_context import SESSION_ID
        print(f"Fetching briefing... [Session: {SESSION_ID}]")
        
        async def _run_briefing():
            res = await _handle_briefing({})
            for text_content in res:
                print(text_content.text)
                
        asyncio.run(_run_briefing())
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
