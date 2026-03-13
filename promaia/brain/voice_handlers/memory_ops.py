import logging
from google.genai import types
from promaia.brain.core.memory_pipeline import capture_memory
from promaia.storage.vector_db import VectorDBManager
from promaia.storage.postgres_db import get_postgres_db

logger = logging.getLogger(__name__)

async def handle(ft, staged_memories) -> types.FunctionResponse:
    if ft.name == "save_conversation_memory":
        args = ft.args
        staged_memories.append({
            "content": args.get("summary"),
            "domain": args.get("memory_type", "user"),
            "confidence": 0.8
        })
        logger.info(f"Memory explicitly staged by Gemini: {args.get('summary')}")
        return types.FunctionResponse(
            name=ft.name,
            id=ft.id,
            response={"result": "staged_successfully", "total_staged_count": len(staged_memories)}
        )
    
    elif ft.name == "commit_staged_memories":
        if staged_memories:
            for m in staged_memories:
                m['confidence'] = min(1.0, m['confidence'] + 0.1)
            
            try:
                db = get_postgres_db()
                vector_mgr = VectorDBManager()
                for m in staged_memories:
                    await capture_memory(
                        db=db,
                        vector_mgr=vector_mgr,
                        content=m['content'],
                        session_id="voice-session",
                        domain_name=m.get('domain'),
                        source="voice",
                        confidence=m['confidence']
                    )
                logger.info(f"Successfully COMMITTED {len(staged_memories)} memories through pipeline after user confirmation.")
                staged_memories.clear()
                return types.FunctionResponse(
                    name=ft.name,
                    id=ft.id,
                    response={"result": "committed_successfully"}
                )
            except Exception as e:
                logger.error(f"Failed to commit batch through pipeline: {e}", exc_info=True)
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
                    response={"result": "no_memories_found", "note": "Memory search temporarily unavailable. Use conversation context instead."}
                )
        except Exception as e:
            logger.error(f"Failed to recall memory: {e}", exc_info=True)
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "error_recalling_memory"}
            )
