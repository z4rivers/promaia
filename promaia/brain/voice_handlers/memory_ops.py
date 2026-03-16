import logging
import asyncio
from google.genai import types
from promaia.brain.core.memory_pipeline import capture_memory
from promaia.storage.vector_db import VectorDBManager
from promaia.storage.db_factory import get_db

logger = logging.getLogger(__name__)

async def handle(ft, _staged_memories_list=None) -> types.FunctionResponse:
    """
    Handles memory-related tool calls from the Voice Agent.
    Now uses the persistent 'staged_memories' DB table instead of an in-memory list.
    """
    db = get_db()
    
    if ft.name == "save_conversation_memory":
        args = ft.args
        content = args.get("summary")
        domain = args.get("memory_type", "user")
        
        if not content:
            return types.FunctionResponse(
                name=ft.name, id=ft.id,
                response={"result": "error", "error": "Missing summary"}
            )

        def _save_staged():
            return db.execute(
                """
                INSERT INTO staged_memories (surface, content, domain, confidence)
                VALUES ('voice', %s, %s, 0.8)
                """,
                (content, domain)
            )
        
        await asyncio.to_thread(_save_staged)
        
        # Get count of currently staged memories for this user/surface
        def _get_count():
            res = db.fetch_one(
                "SELECT COUNT(*) as count FROM staged_memories WHERE status = 'staged' AND surface = 'voice'"
            )
            return res['count'] if res else 0
            
        count = await asyncio.to_thread(_get_count)
        
        logger.info(f"Memory explicitly staged to DB: {content}")
        return types.FunctionResponse(
            name=ft.name,
            id=ft.id,
            response={"result": "staged_successfully", "total_staged_count": count}
        )
    
    elif ft.name == "commit_staged_memories":
        # Fetch all staged memories for this surface
        def _fetch_staged():
            return db.fetch_all(
                "SELECT id, content, domain, confidence FROM staged_memories WHERE status = 'staged' AND surface = 'voice'"
            )
        
        staged_rows = await asyncio.to_thread(_fetch_staged)
        
        if staged_rows:
            try:
                vector_mgr = VectorDBManager()
                commit_count = 0
                for row in staged_rows:
                    # Boost confidence on commit as per original logic
                    new_confidence = min(1.0, (row['confidence'] or 0.8) + 0.1)
                    
                    await capture_memory(
                        db=db,
                        vector_mgr=vector_mgr,
                        content=row['content'],
                        session_id="voice-session",
                        domain_name=row.get('domain'),
                        source="voice",
                        confidence=new_confidence
                    )
                    
                    # Mark as committed
                    db.execute(
                        "UPDATE staged_memories SET status = 'committed' WHERE id = %s",
                        (row['id'],)
                    )
                    commit_count += 1
                    
                logger.info(f"Successfully COMMITTED {commit_count} memories from DB via pipeline.")
                return types.FunctionResponse(
                    name=ft.name,
                    id=ft.id,
                    response={"result": "committed_successfully", "count": commit_count}
                )
            except Exception as e:
                logger.error(f"Failed to commit staged memories from DB: {e}", exc_info=True)
                return types.FunctionResponse(
                    name=ft.name,
                    id=ft.id,
                    response={"result": "error_committing"}
                )
        else:
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "no_staged_memories_found"}
            )

    elif ft.name == "recall_memory":
        args = ft.args
        query = args.get("query")
        try:
            from promaia.brain.muninn import get_muninn
            muninn = await get_muninn()
            if muninn:
                res = await muninn.activate([query], max_results=3)
                activations = res.get("activations", [])
                if activations:
                    mem_text = "\n".join(f"- {a['content']}" for a in activations)
                    return types.FunctionResponse(
                        name=ft.name,
                        id=ft.id,
                        response={"result": "memory_recalled", "memories": mem_text}
                    )
                else:
                    return types.FunctionResponse(
                        name=ft.name,
                        id=ft.id,
                        response={"result": "no_memories_found"}
                    )
            else:
                return types.FunctionResponse(
                    name=ft.name,
                    id=ft.id,
                    response={"result": "no_memories_found", "note": "Memory search temporarily unavailable."}
                )
        except Exception as e:
            logger.error(f"Failed to recall memory: {e}", exc_info=True)
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "error_recalling_memory"}
            )
