import logging
import os
from google.genai import types

from promaia.brain.voice_handlers import (
    memory_ops,
    calendar_ops,
    workspace_ops,
    youtube_ops,
    system_ops
)

logger = logging.getLogger(__name__)

# Project root for read_file tool
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def _handle_read_file(ft) -> types.FunctionResponse:
    """Read a file from the project repo and return its contents."""
    args = ft.args
    rel_path = args.get("path", "").strip()
    max_lines = int(args.get("max_lines", 500))

    if not rel_path:
        return types.FunctionResponse(
            name=ft.name, id=ft.id,
            response={"result": "error", "error": "No path provided"}
        )

    # Security: block path traversal
    full_path = os.path.normpath(os.path.join(_PROJECT_ROOT, rel_path))
    if not full_path.startswith(_PROJECT_ROOT):
        return types.FunctionResponse(
            name=ft.name, id=ft.id,
            response={"result": "error", "error": "Path traversal not allowed"}
        )

    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        total = len(lines)
        content = "".join(lines[:max_lines])
        truncated = total > max_lines
        return types.FunctionResponse(
            name=ft.name, id=ft.id,
            response={
                "result": "success",
                "path": rel_path,
                "total_lines": total,
                "truncated": truncated,
                "content": content
            }
        )
    except FileNotFoundError:
        return types.FunctionResponse(
            name=ft.name, id=ft.id,
            response={"result": "error", "error": f"File not found: {rel_path}"}
        )
    except Exception as e:
        return types.FunctionResponse(
            name=ft.name, id=ft.id,
            response={"result": "error", "error": str(e)}
        )


async def handle_tool_call(ft, websocket, staged_memories) -> types.FunctionResponse:
    """
    Executes a single tool call from the Gemini Live API and returns the FunctionResponse.
    Routes requests to specialized voice handler modules based on the domain.
    """
    try:
        if ft.name in ["save_conversation_memory", "commit_staged_memories", "recall_memory"]:
            return await memory_ops.handle(ft, staged_memories)
            
        elif ft.name in ["create_calendar_event", "delete_calendar_event"]:
            return await calendar_ops.handle(ft)
            
        elif ft.name == "read_file":
            return await _handle_read_file(ft)

        elif ft.name in ["send_email_draft", "query_workspace", "write_content", "run_workspace_sync"]:
            return await workspace_ops.handle(ft)
            
        elif ft.name in ["sync_youtube_context", "query_youtube_transcript"]:
            return await youtube_ops.handle(ft)
            
        elif ft.name in ["switch_cognitive_mode", "hang_up_call", "log_system_feedback", "create_action"]:
            return await system_ops.handle(ft, websocket)
            
        # Unhandled tools
        return types.FunctionResponse(
            name=ft.name,
            id=ft.id,
            response={"result": "error", "message": f"Tool {ft.name} not implemented in handler"}
        )
    except Exception as e:
        logger.error(f"Error handling tool {ft.name}: {e}", exc_info=True)
        return types.FunctionResponse(
            name=ft.name,
            id=ft.id,
            response={"result": "error", "message": f"Internal error executing {ft.name}: {str(e)}"}
        )
