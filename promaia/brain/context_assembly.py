"""
Shared context assembly for all brain surfaces (Telegram, Web, Voice).
Ensures consistent retrieval and token-efficient reasoning.

Supports two modes:
- OPEN MODE (active_domain=None): Rich, connected, cross-domain retrieval.
  MuninnDB activates freely. Dot-connecting across domains is welcome.
- SILO MODE (active_domain="promaia"): Hard domain boundaries.
  Only domain-matching memories/actions/projects pass through.
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from promaia.storage.db_factory import get_db
from promaia.brain.muninn import get_muninn

logger = logging.getLogger(__name__)

# Profile categories that shape HOW Maia communicates — always relevant
_ESSENTIAL_PROFILE_CATEGORIES = ('communication', 'personality', 'work', 'identity')


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
    active_domain: Optional[str] = None,
) -> str:
    """
    Gathers profile, history, MuninnDB activations, actions, and projects.
    Respects a token budget and priority order.

    active_domain:
        None = open mode (cross-domain, fully connected)
        "promaia" / "hvac" / etc = silo mode (hard domain filter)
    """
    db = get_db()

    # Priority 1: Profile (Who is Zack? How does he communicate?)
    async def get_profile():
        try:
            if active_domain:
                # Silo mode: essential communication/personality traits only (~200 tokens)
                rows = db.fetch_all(
                    """SELECT category, field, value FROM profile
                    WHERE category IN ('communication', 'personality', 'work', 'identity')
                    AND confidence > 0.6
                    ORDER BY confidence DESC LIMIT 10"""
                )
            else:
                # Open mode: broader profile for richer context
                rows = db.fetch_all(
                    "SELECT category, field, value FROM profile WHERE confidence > 0.7 ORDER BY category"
                )
            if not rows:
                return ""
            lines = ["### User Profile"]
            for r in rows:
                lines.append(f"- {r['category']}.{r['field']}: {r['value']}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Context profile failed: {e}")
            return ""

    # Priority 2: History (What were we just talking about?)
    async def get_history():
        if not include_history or not chat_id:
            return ""
        try:
            rows = db.fetch_all(
                "SELECT role, content FROM conversations WHERE chat_id = %s ORDER BY created_at DESC LIMIT %s",
                (chat_id, max_history)
            )
            if not rows:
                return ""
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

            # Build query from conversation history + current message
            # (restores the old _assemble_context pattern of passing recent messages)
            query_parts = []
            if chat_id:
                try:
                    history_rows = db.fetch_all(
                        "SELECT role, content FROM conversations WHERE chat_id = %s ORDER BY created_at DESC LIMIT 3",
                        (chat_id,)
                    )
                    if history_rows:
                        query_parts = [h['content'] for h in reversed(history_rows)]
                except Exception as e:
                    logger.warning(f"History fetch for MuninnDB query failed: {e}")

            query_parts.append(user_message)
            if context_hints:
                query_parts.extend(context_hints)

            # Add domain hint for silo mode
            if active_domain:
                query_parts.append(f"domain:{active_domain}")

            if not muninn:
                # MuninnDB offline — fall back to database
                return await _db_memory_fallback(db, max_memories, active_domain)

            res = await muninn.activate(query_parts, max_results=max_memories)
            activations = res.get("activations", [])

            if not activations:
                # MuninnDB returned nothing — fall back to database
                return await _db_memory_fallback(db, max_memories, active_domain)

            lines = ["### Relevant Memories & Insights"]
            # Apply retrieval penalty to assistant memories and cap at 2
            assistant_memories = 0
            for a in activations:
                # Silo mode: hard filter — drop memories from other domains
                if active_domain:
                    mem_domain = a.get("domain") or a.get("tags", {}).get("domain")
                    if mem_domain and mem_domain.lower() != active_domain.lower():
                        continue

                is_assistant = a.get("tags") and "assistant" in a["tags"]
                if is_assistant:
                    if assistant_memories >= 2:
                        continue
                    assistant_memories += 1

                lines.append(f"- {a['content']}")

            if len(lines) <= 1:
                # All memories were filtered out in silo mode
                return await _db_memory_fallback(db, max_memories, active_domain)

            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Context muninn failed: {e}")
            return await _db_memory_fallback(db, max_memories, active_domain)

    # Priority 4: Pending Actions
    async def get_actions():
        try:
            if active_domain:
                # Silo mode: hard filter by domain
                rows = db.fetch_all(
                    """
                    SELECT a.description, d.name as domain_name
                    FROM actions a
                    LEFT JOIN domains d ON d.id = a.domain_id
                    WHERE a.status = 'pending'
                    AND d.id = (SELECT id FROM domains WHERE LOWER(name) = LOWER(%s))
                    ORDER BY a.extracted_at DESC LIMIT %s
                    """, (active_domain, max_actions)
                )
            else:
                rows = db.fetch_all(
                    """
                    SELECT a.description, d.name as domain_name
                    FROM actions a
                    LEFT JOIN domains d ON d.id = a.domain_id
                    WHERE a.status = 'pending'
                    ORDER BY a.extracted_at DESC LIMIT %s
                    """, (max_actions,)
                )
            if not rows:
                return ""
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
            if active_domain:
                # Silo mode: only the focused domain's project
                rows = db.fetch_all(
                    """
                    SELECT d.name, c.current_state, c.directive
                    FROM contexts c
                    JOIN domains d ON d.id = c.domain_id
                    WHERE LOWER(d.name) = LOWER(%s)
                    LIMIT 1
                    """, (active_domain,)
                )
            else:
                rows = db.fetch_all(
                    """
                    SELECT d.name, c.current_state, c.directive
                    FROM contexts c
                    JOIN domains d ON d.id = c.domain_id
                    ORDER BY c.priority ASC LIMIT 5
                    """
                )
            if not rows:
                return ""
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

    # Combine with budget awareness
    full_context = "\n\n".join([r for r in results if r])

    # Approximate token count (4 chars per token)
    if len(full_context) / 4 > token_budget:
        logger.info(f"Context exceeds budget ({len(full_context)/4:.0f} tokens), truncating...")
        full_context = full_context[:token_budget * 4]

    return full_context


async def _db_memory_fallback(db, max_memories: int, active_domain: Optional[str] = None) -> str:
    """Fallback: recent memories from DB when MuninnDB is offline or returns empty."""
    try:
        if active_domain:
            rows = db.fetch_all(
                """SELECT content, domain FROM memories
                WHERE COALESCE(source, '') != 'youtube'
                AND LOWER(COALESCE(domain, '')) = LOWER(%s)
                ORDER BY created_at DESC LIMIT %s""",
                (active_domain, max_memories)
            )
        else:
            rows = db.fetch_all(
                """SELECT content, domain FROM memories
                WHERE COALESCE(source, '') != 'youtube'
                ORDER BY created_at DESC LIMIT %s""",
                (max_memories,)
            )
        if rows:
            lines = ["### Recent Memories"]
            lines.extend(f"- [{r.get('domain') or 'general'}] {r['content'][:200]}" for r in rows)
            return "\n".join(lines)
    except Exception as e:
        logger.warning(f"DB memory fallback failed: {e}")
    return ""
