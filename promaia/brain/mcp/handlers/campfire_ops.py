"""
Campfire operations for MCP server.
Enables Claude to save and retrieve session snapshots.
"""
import json
import logging
from typing import Optional, List, Dict, Any
from promaia.brain.campfire import save_snapshot, get_latest_snapshots

logger = logging.getLogger(__name__)

async def handle_save_snapshot(args: Dict[str, Any]) -> Dict[str, Any]:
    """MCP handler for save_snapshot tool."""
    try:
        snapshot_id = await save_snapshot(
            agent=args.get("agent", "claude"),
            summary=args.get("summary"),
            session_id=args.get("session_id"),
            status=args.get("status", "complete"),
            topics=args.get("topics"),
            decisions=args.get("decisions"),
            next_steps=args.get("next_steps"),
            active_files=args.get("active_files"),
            branch=args.get("branch")
        )
        if snapshot_id > 0:
            return {"result": "success", "snapshot_id": snapshot_id}
        else:
            return {"result": "error", "message": "Failed to save snapshot"}
    except Exception as e:
        return {"result": "error", "message": str(e)}

async def handle_get_snapshots(args: Dict[str, Any]) -> Dict[str, Any]:
    """MCP handler for get_snapshots tool."""
    try:
        limit = args.get("limit", 5)
        snapshots = await get_latest_snapshots(limit=limit)
        return {"result": "success", "snapshots": snapshots}
    except Exception as e:
        return {"result": "error", "message": str(e)}
