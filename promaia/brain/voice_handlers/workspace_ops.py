import logging
import os
import subprocess
from datetime import datetime
from google.genai import types

logger = logging.getLogger(__name__)

async def handle(ft) -> types.FunctionResponse:
    if ft.name == "send_email_draft":
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

    elif ft.name == "query_workspace":
        args = ft.args
        query = args.get("query")
        workspace = args.get("workspace")
        logger.info(f"Querying workspace '{workspace}' with: {query}")
        try:
            from promaia.ai.nl_processor_wrapper import process_natural_language_to_content
            # Run the agentic processor
            results, metadata = process_natural_language_to_content(
                nl_prompt=query,
                workspace=workspace,
                verbose=False,
                skip_confirmation=True,
                return_metadata=True
            )
            
            # Format results concisely for voice
            if results:
                summary_lines = []
                total_items = 0
                for db_name, entries in results.items():
                    total_items += len(entries)
                    for entry in entries[:3]:  # Top 3 per DB
                        title = entry.get('title', entry.get('subject', 'Untitled'))
                        summary_lines.append(f"- [{db_name}] {title}")
                
                response_text = f"Found {total_items} items. Top matches:\n" + "\n".join(summary_lines)
                if total_items > len(summary_lines):
                    response_text += f"\n(and {total_items - len(summary_lines)} more...)"
                    
                return types.FunctionResponse(
                    name=ft.name,
                    id=ft.id,
                    response={"result": "query_successful", "summary": response_text}
                )
            else:
                return types.FunctionResponse(
                    name=ft.name,
                    id=ft.id,
                    response={"result": "no_results_found"}
                )
        except Exception as e:
            logger.error(f"Workspace query failed: {e}", exc_info=True)
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "error", "error": str(e)}
            )

    elif ft.name == "write_content":
        args = ft.args
        topic = args.get("topic")
        format_type = args.get("format_type")
        logger.info(f"Drafting content '{topic}' in format '{format_type}'")
        try:
            from promaia.ai.nl_orchestrator import PromaiLLMAdapter
            
            llm = PromaiLLMAdapter()
            prompt = f"Write a {format_type} about: {topic}. Keep it concise but professional."
            response = llm.invoke(prompt)
            
            # Save to drafts directory
            drafts_dir = os.path.join(os.getcwd(), "data", "drafts")
            os.makedirs(drafts_dir, exist_ok=True)
            
            safe_topic = "".join(c if c.isalnum() else "_" for c in topic)[:30]
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_topic}.md"
            filepath = os.path.join(drafts_dir, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# {topic}\n\n{response.content}")
                
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={
                    "result": "content_drafted_and_saved", 
                    "filepath": filepath,
                    "preview": response.content[:200] + "..."
                }
            )
        except Exception as e:
            logger.error(f"Failed to write content: {e}", exc_info=True)
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "error", "error": str(e)}
            )

    elif ft.name == "run_workspace_sync":
        args = ft.args
        target = args.get("target", "all").lower()
        logger.info(f"Triggering background sync for: {target}")
        try:
            import sys
            cmd = [sys.executable, "-m", "promaia", "database", "sync"]
            if target != "all":
                cmd.extend(["-s", target])
            # Run asynchronously so we don't block the voice bridge
            subprocess.Popen(cmd)
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "sync_started_in_background", "target": target}
            )
        except Exception as e:
            logger.error(f"Failed to trigger sync: {e}", exc_info=True)
            return types.FunctionResponse(
                name=ft.name,
                id=ft.id,
                response={"result": "error", "error": str(e)}
            )
