import logging
from google.genai import types
from promaia.storage.db_factory import get_db
from promaia.storage.vector_db import VectorDBManager
from promaia.brain.core.memory_pipeline import capture_memory

logger = logging.getLogger(__name__)

async def handle(ft, websocket, session_id=None) -> types.FunctionResponse:
    if ft.name == "switch_cognitive_mode":
        args = ft.args
        color = args.get("hat_color", "").lower()
        modes = {
            "critical":  "CRITICAL INSTRUCTION: Shift to devil's advocate mode. Focus on risks, flaws, and potential failures. Be honest and direct — your job is to bulletproof the idea, not to encourage it.",
            "black":     "CRITICAL INSTRUCTION: Shift to devil's advocate mode. Focus on risks, flaws, and potential failures. Be honest and direct — your job is to bulletproof the idea, not to encourage it.",
            "creative":  "CRITICAL INSTRUCTION: Shift to brainstorm mode. Generate alternatives, new angles, and unexpected ideas. No criticism — everything is on the table.",
            "green":     "CRITICAL INSTRUCTION: Shift to brainstorm mode. Generate alternatives, new angles, and unexpected ideas. No criticism — everything is on the table.",
            "instinct":  "CRITICAL INSTRUCTION: Shift to gut-check mode. Set logic aside. Respond from intuition — how does this feel? What's the emotional undercurrent?",
            "red":       "CRITICAL INSTRUCTION: Shift to gut-check mode. Set logic aside. Respond from intuition — how does this feel? What's the emotional undercurrent?",
            "facts":     "CRITICAL INSTRUCTION: Shift to just-the-facts mode. Only discuss what is known and verifiable. Flag what is unknown. No opinions or speculation.",
            "white":     "CRITICAL INSTRUCTION: Shift to just-the-facts mode. Only discuss what is known and verifiable. Flag what is unknown. No opinions or speculation.",
            "optimist":  "CRITICAL INSTRUCTION: Shift to upside mode. Focus on the best-case outcome and the logical reasons this will work. Be genuinely enthusiastic without ignoring reality.",
            "yellow":    "CRITICAL INSTRUCTION: Shift to upside mode. Focus on the best-case outcome and the logical reasons this will work. Be genuinely enthusiastic without ignoring reality.",
            "process":   "CRITICAL INSTRUCTION: Shift to big-picture mode. Zoom out. Organize what has been covered, identify what's missing, and set a clear direction for what's next.",
            "blue":      "CRITICAL INSTRUCTION: Shift to big-picture mode. Zoom out. Organize what has been covered, identify what's missing, and set a clear direction for what's next.",
        }
        instruction = modes.get(color, "Return to your normal balanced mode.")
        logger.info(f"Switched to cognitive mode: {color}")
        return types.FunctionResponse(
            name=ft.name,
            id=ft.id,
            response={"result": "mode_switched", "new_instructions": instruction}
        )
        
    elif ft.name == "set_focus":
        args = ft.args
        domain = args.get("domain")
        if domain and domain.lower() in ["null", "none"]:
            domain = None
            
        try:
            if not session_id:
                raise ValueError("No session_id provided to set_focus")
                
            db = get_db()
            db.execute(
                "UPDATE conversation_sessions SET active_domain = ? WHERE session_id = ?",
                (domain, session_id)
            )
            logger.info(f"Set focus to: {domain} for session {session_id}")
            
            # Broadcast to UI for sync (if websocket is a Maia stream websocket)
            if websocket:
                try:
                    import json
                    await websocket.send_json({
                        "type": "room_change",
                        "domain": domain or "general"
                    })
                except Exception as e:
                    logger.warning(f"Failed to broadcast focus change to websocket: {e}")

            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "focus_set", "active_domain": domain}
            )
        except Exception as e:
            logger.error(f"Failed to set focus: {e}", exc_info=True)
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "error_setting_focus", "error": str(e)}
            )
        
    elif ft.name == "hang_up_call":
        logger.info(f"Agent decided to hang up the call.")
        await websocket.send_json({
            "serverContent": {
                "control": "hang_up"
            }
        })
        return types.FunctionResponse(
            name=ft.name,
            id=ft.id,
            response={"result": "hanging_up"}
        )
        
    elif ft.name == "log_system_feedback":
        args = ft.args
        feedback = args.get("feedback")
        logger.info(f"USER SUBMITTED SYSTEM FEEDBACK: {feedback}")
        
        try:
            db = get_db()
            vector_mgr = VectorDBManager()
            await capture_memory(
                db=db,
                vector_mgr=vector_mgr,
                content=f"[SYSTEM BUG/FEEDBACK]: {feedback}",
                session_id="voice-session-feedback",
                domain_name="system_feedback",
                source="voice",
                confidence=1.0
            )
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "feedback_logged_to_devs"}
            )
        except Exception as e:
            logger.error(f"Failed to log system feedback: {e}", exc_info=True)
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "error_logging_feedback"}
            )
            
    elif ft.name == "create_action":
        args = ft.args
        try:
            db = get_db()
            # Resolve domain name to domain_id if provided
            domain_id = None
            domain_name = args.get("domain")
            if domain_name:
                domain_row = db.fetch_one(
                    "SELECT id FROM domains WHERE name = ?",
                    (domain_name,),
                )
                if domain_row:
                    domain_id = domain_row["id"]
            db.execute(
                """
                INSERT INTO actions (description, domain_id, status, extracted_at)
                VALUES (?, ?, 'pending', datetime('now'))
                """,
                (args.get("description"), domain_id)
            )
            logger.info(f"Successfully created action item: {args.get('description')}")
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "action_created"}
            )
        except Exception as e:
            logger.error(f"Failed to create action item: {e}", exc_info=True)
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "error_creating_action", "error": str(e)}
            )
