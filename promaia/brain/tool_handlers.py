import logging
import asyncio
from datetime import datetime, timedelta, timezone
from google.genai import types

from promaia.brain.memory_pipeline import capture_memory, VectorDBManager
from promaia.db.connection import get_postgres_db

logger = logging.getLogger(__name__)

async def handle_tool_call(ft, websocket, staged_memories) -> types.FunctionResponse:
    """
    Executes a single tool call from the Gemini Live API and returns the FunctionResponse.
    Mutates staged_memories or interacts with the websocket if necessary.
    """
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
        
    elif ft.name == "create_calendar_event":
        args = ft.args
        try:
            from promaia.gcal.google_calendar import get_calendar_manager
            mgr = get_calendar_manager()
            if mgr.authenticate():
                event_body = {
                    'summary': args.get('summary'),
                    'start': {'dateTime': args.get('start_time'), 'timeZone': 'America/Los_Angeles'},
                    'end': {'dateTime': args.get('end_time'), 'timeZone': 'America/Los_Angeles'}
                }
                if args.get('description'):
                    event_body['description'] = args.get('description')
                
                if 'Z' in str(args.get('start_time')):
                    event_body['start']['timeZone'] = 'UTC'
                    event_body['end']['timeZone'] = 'UTC'

                event = mgr.service.events().insert(
                    calendarId='primary',
                    body=event_body
                ).execute()
                
                return types.FunctionResponse(
                    name=ft.name,
                    id=ft.id,
                    response={"result": "event_created", "event_id": event.get('id'), "link": event.get('htmlLink')}
                )
            else:
                return types.FunctionResponse(
                    name=ft.name,
                    id=ft.id,
                    response={"result": "authentication_failed", "error": "Google Calendar authentication failed"}
                )
        except Exception as e:
            logger.error(f"Failed to create calendar event: {e}", exc_info=True)
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "error_creating_event", "error": str(e)}
            )

    elif ft.name == "delete_calendar_event":
        args = ft.args
        try:
            from promaia.gcal.google_calendar import get_calendar_manager
            mgr = get_calendar_manager()
            if mgr.authenticate():
                search_summary = args.get('summary', '').lower()
                search_date = args.get('date')
                
                now_dt = datetime.now(timezone.utc)
                time_max = now_dt + timedelta(days=90)
                if search_date:
                    from datetime import date as date_type
                    try:
                        d = datetime.strptime(search_date, '%Y-%m-%d')
                        search_start = d.replace(hour=0, minute=0, second=0, tzinfo=timezone.utc)
                        time_max = d.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                        now_dt = search_start
                    except ValueError:
                        pass
                
                events_result = mgr.service.events().list(
                    calendarId='primary',
                    timeMin=now_dt.isoformat().replace('+00:00', 'Z'),
                    timeMax=time_max.isoformat().replace('+00:00', 'Z'),
                    singleEvents=True,
                    orderBy='startTime',
                    q=args.get('summary', '')
                ).execute()
                
                events = events_result.get('items', [])
                if events:
                    deleted = []
                    for ev in events:
                        if search_summary in ev.get('summary', '').lower():
                            mgr.service.events().delete(
                                calendarId='primary',
                                eventId=ev['id']
                            ).execute()
                            deleted.append(ev.get('summary'))
                    
                    if deleted:
                        return types.FunctionResponse(
                            name=ft.name,
                            id=ft.id,
                            response={"result": "events_deleted", "deleted": deleted}
                        )
                    else:
                        return types.FunctionResponse(
                            name=ft.name,
                            id=ft.id,
                            response={"result": "no_matching_events", "searched_for": args.get('summary')}
                        )
                else:
                    return types.FunctionResponse(
                        name=ft.name,
                        id=ft.id,
                        response={"result": "no_events_found", "searched_for": args.get('summary')}
                    )
            else:
                return types.FunctionResponse(
                    name=ft.name,
                    id=ft.id,
                    response={"result": "authentication_failed"}
                )
        except Exception as e:
            logger.error(f"Failed to delete calendar event: {e}", exc_info=True)
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "error_creating_event", "error": str(e)}
            )

    elif ft.name == "send_email_draft":
        args = ft.args
        try:
            from promaia.mail.email_send_helpers import EmailSendHelper
            helper = EmailSendHelper(workspace="zbrain")
            draft_id = helper.create_draft_from_info(
                recipient=args.get("to"),
                subject=args.get("subject"),
                message_body=args.get("body")
            )
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "draft_created", "draft_id": draft_id}
            )
        except Exception as e:
            logger.error(f"Failed to create email draft: {e}", exc_info=True)
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "error_creating_draft", "error": str(e)}
            )
            
    elif ft.name == "switch_cognitive_mode":
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
            db = get_postgres_db()
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
            db = get_postgres_db()
            db.execute(
                """
                INSERT INTO brain.actions (description, due_date, domain, status, created_at)
                VALUES (%s, %s, %s, 'pending', NOW())
                """,
                (args.get("description"), args.get("due_date"), args.get("domain"))
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
                    response={"result": "muninndb_offline"}
                )
        except Exception as e:
            logger.error(f"Failed to recall memory: {e}", exc_info=True)
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "error_recalling_memory"}
            )
            
    # Unhandled tools
    return types.FunctionResponse(
        name=ft.name,
        id=ft.id,
        response={"result": "error", "message": f"Tool {ft.name} not implemented in handler"}
    )
