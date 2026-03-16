"""
Shared context assembly for all brain surfaces (Telegram, Web, Voice).
Ensures consistent retrieval and token-efficient reasoning.
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from promaia.storage.db_factory import get_db
from promaia.brain.muninn import get_muninn

logger = logging.getLogger(__name__)

async def assemble_brain_context(
    user_message: str,
    chat_id: int = None,
    include_calendar: bool = False,
    include_history: bool = True,
    max_memories: int = 15,
    max_actions: int = 5,
    max_history: int = 10,
    token_budget: int = 4000,
    context_hints: Optional[List[str]] = None,
) -> str:
    """
    Gathers profile, history, MuninnDB activations, actions, and projects.
    Respects a token budget and priority order.
    """
    db = get_db()
    
    # Priority 1: Profile (Who is Zack?)
    async def get_profile():
        try:
            rows = db.fetch_all("SELECT category, field, value FROM profile WHERE confidence > 0.7 ORDER BY category")
            if not rows: return ""
            lines = ["### User Profile"]
            for r in rows:
                lines.append(f"- {r['category']}.{r['field']}: {r['value']}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Context profile failed: {e}")
            return ""

    # Priority 2: History (What were we just talking about?)
    async def get_history():
        if not include_history or not chat_id: return ""
        try:
            rows = db.fetch_all(
                "SELECT role, content FROM conversations WHERE chat_id = %s ORDER BY created_at DESC LIMIT %s",
                (chat_id, max_history)
            )
            if not rows: return ""
            rows.reverse()
            lines = ["### Recent Conversation History"]
            for r in rows:
                lines.append(f"{r['role'].upper()}: {r['content']}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Context history failed: {e}")
            return ""

    # Priority 3: Cognitive Context (MuninnDB Activations)
    async def get_muninn_context():
        try:
            muninn = await get_muninn()
            if not muninn: return ""
            
            # Combine user message with hints for retrieval
            query_parts = [user_message]
            if context_hints:
                query_parts.extend(context_hints)
            
            res = await muninn.activate(query_parts, max_results=max_memories)
            activations = res.get("activations", [])
            if not activations: return ""
            
            lines = ["### Relevant Memories & Insights"]
            # Apply retrieval penalty to assistant memories (Phase 2 requirement)
            # and cap them at 2
            assistant_memories = 0
            for a in activations:
                is_assistant = a.get("tags") and "assistant" in a["tags"]
                if is_assistant:
                    if assistant_memories >= 2: continue
                    assistant_memories += 1
                
                lines.append(f"- {a['content']}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Context muninn failed: {e}")
            return ""

    # Priority 4: Pending Actions
    async def get_actions():
        try:
            rows = db.fetch_all(
                """
                SELECT a.description, d.name as domain_name
                FROM actions a
                LEFT JOIN domains d ON d.id = a.domain_id
                WHERE a.status = 'pending'
                ORDER BY a.extracted_at DESC LIMIT %s
                """, (max_actions,)
            )
            if not rows: return ""
            lines = ["### Pending Actions"]
            for r in rows:
                domain = f" [{r['domain_name']}]" if r['domain_name'] else ""
                lines.append(f"- {r['description']}{domain}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Context actions failed: {e}")
            return ""

    # Priority 5: Active Projects
    async def get_projects():
        try:
            rows = db.fetch_all(
                """
                SELECT d.name, c.current_state, c.directive
                FROM contexts c
                JOIN domains d ON d.id = c.domain_id
                ORDER BY c.priority ASC LIMIT 5
                """
            )
            if not rows: return ""
            lines = ["### Active Projects"]
            for r in rows:
                state = r['current_state'] or r['directive']
                lines.append(f"- {r['name']}: {state}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Context projects failed: {e}")
            return ""

    # Run all in parallel
    tasks = [get_profile(), get_history(), get_muninn_context(), get_actions(), get_projects()]
    results = await asyncio.gather(*tasks)
    
    # Combine with budget awareness (very basic truncation for now)
    # Future: use a real tokenizer to enforce token_budget
    full_context = "\n\n".join([r for r in results if r])
    
    # Approximate token count (4 chars per token)
    if len(full_context) / 4 > token_budget:
        logger.info(f"Context exceeds budget ({len(full_context)/4:.0f} tokens), truncating...")
        full_context = full_context[:token_budget * 4]
        
    return full_context
