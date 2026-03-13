import logging
from google.genai import types

from promaia.brain.voice_handlers import (
    memory_ops,
    calendar_ops,
    workspace_ops,
    youtube_ops,
    system_ops
)

logger = logging.getLogger(__name__)

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
