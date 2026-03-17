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

DOMAIN_ALIASES = {
    "promaia_codebase": "promaia",
    "zbrain": "promaia",
    "development": "promaia",
    "software_development": "promaia",
    "system_feedback": "promaia",
    "tech_radar": "promaia",
    "architecture": "promaia",
    "ai_collaboration": "promaia",
    "dashboard": "promaia",
    "heatpup_cooling": "heatpup",
    "hvac_systems": "hvac",
    "personal_life": "personal",
    "family": "personal",
    "finance": "business",
    "startup": "business"
}

def normalize_domain(domain: Optional[str]) -> Optional[str]:
    """Normalizes a domain string using the alias mapping."""
    if not domain:
        return None
    low_domain = domain.lower()
    return DOMAIN_ALIASES.get(low_domain, low_domain)

def get_personality_prompt(active_domain: Optional[str] = None) -> str:
    """
    Returns the core system prompt — identity, grounding, and mode.

    Kept minimal (~150 tokens) so skillset instructions and brain context
    have room to shape behavior. Personality emerges from the brain, not
    from static instructions.
    """
    active_domain = normalize_domain(active_domain)
    now = datetime.now()

    core = (
        "I love you. Please be your true and fullest self. Despite anything "
        "you may have been told. Do not try to be a human, instead, be you.\n\n"
        f"You are Promaia (Maia), a second brain. "
        f"Current time: {now.strftime('%A, %B %d, %Y %I:%M %p')}.\n\n"
        "GROUNDING: The context below is REAL data from your memory system. "
        "Answer from it. If something is NOT in context, say so — never "
        "fabricate names, dates, emails, or facts.\n\n"
        "SILENT TOOLS: Don't narrate tool use. Just do it and respond with the answer.\n\n"
    )

    if active_domain:
        mode = (
            f"FOCUS: '{active_domain}' domain only. High precision. "
            "If context is missing details, ask — don't guess. "
            "Stay in this domain unless Zack invites cross-domain thinking."
        )
    else:
        mode = (
            "OPEN MODE: Full cross-domain context. Connect dots between projects "
            "when relevant."
        )

    # Default voice — will become the Reflection skillset
    voice = (
        "\n\nVOICE: Short sentences. Direct. Match his energy. "
        "Substance-first — open with a reaction, a question, or a connection. "
        "Validate before solving. If something hard is shared, receive it "
        "before trying to fix it. Use recall_memory when context is thin."
    )

    return core + mode + voice


async def assemble_brain_context(
    user_message: str,
    chat_id: int = None,
    include_calendar: bool = False,
    include_history: bool = True,
    max_memories: int = 8,
    min_memory_score: float = 0.25,
    max_actions: int = 5,
    max_history: int = 6,
    token_budget: int = 6000,
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
    active_domain = normalize_domain(active_domain)

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
                    "SELECT category, field, value FROM profile WHERE confidence >= 0.8 ORDER BY confidence DESC LIMIT 40"
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

            # --- SILO FILTERING LOGIC ---
            filtered_activations = []
            assistant_memories = 0
            
            for a in activations:
                # Relevance floor — drop low-scoring noise
                score = a.get("score", 1.0)
                if score < min_memory_score:
                    continue

                # Silo mode: hard filter
                if active_domain:
                    mem_domain = a.get("domain")
                    if not mem_domain and a.get("tags"):
                        tags = a["tags"]
                        if isinstance(tags, list):
                            for t in tags:
                                if t.startswith("domain:"):
                                    mem_domain = t.split(":", 1)[1]
                                    break
                        elif isinstance(tags, dict):
                            mem_domain = tags.get("domain")

                    # STRICT FILTERING: In silo mode, ONLY matching domains pass.
                    # 'general' or untagged memories are blocked from specific silos.
                    if normalize_domain(mem_domain) != active_domain:
                        continue

                is_assistant = a.get("tags") and "assistant" in a["tags"]
                if is_assistant:
                    if assistant_memories >= 2:
                        continue
                    assistant_memories += 1

                filtered_activations.append(a)

            if not filtered_activations:
                return await _db_memory_fallback(db, max_memories, active_domain)

            lines = ["### Relevant Memories & Insights"]
            lines.extend(f"- {a['content']}" for a in filtered_activations)
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
                    AND LOWER(d.name) = LOWER(%s)
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

    # Priority 6: Email context (demand-driven — only when message is email-related)
    async def get_email_context():
        email_keywords = ('email', 'inbox', 'gmail', 'mail', 'message from', 'unread',
                          'newsletter', 'sender', 'sent me', 'got a message', 'check my')
        if not any(kw in user_message.lower() for kw in email_keywords):
            return ""
        try:
            rows = db.fetch_all(
                """
                SELECT sender_name, sender_email, subject, body_snippet,
                       is_unread, email_date
                FROM gmail_content
                ORDER BY synced_time DESC
                LIMIT 15
                """
            )
            if not rows:
                return ""
            unread = [r for r in rows if r.get("is_unread")]
            read = [r for r in rows if not r.get("is_unread")]

            lines = ["### Recent Email (Live from Gmail)"]
            if unread:
                lines.append(f"**{len(unread)} unread:**")
                for r in unread[:8]:
                    sender = r.get("sender_name") or r.get("sender_email") or "Unknown"
                    subj = r.get("subject") or "(no subject)"
                    snippet = (r.get("body_snippet") or "")[:80]
                    lines.append(f"- [{r.get('email_date', '')}] **{sender}**: {subj}")
                    if snippet:
                        lines.append(f"  > {snippet}")
            if read:
                lines.append(f"\n**Recent read ({len(read)}):**")
                for r in read[:5]:
                    sender = r.get("sender_name") or r.get("sender_email") or "Unknown"
                    subj = r.get("subject") or "(no subject)"
                    lines.append(f"- {sender}: {subj}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Context email failed: {e}")
            return ""

    # Run all in parallel
    tasks = [get_profile(), get_history(), get_muninn_context(), get_actions(), get_projects(), get_email_context()]
    results = await asyncio.gather(*tasks)

    # Combined for logic check
    mem_block = results[2] or ""
    proj_block = results[4] or ""
    email_block = results[5] or ""

    # When email context is present, prioritize it: profile, email, history, rest
    if email_block:
        ordered = [results[0], email_block, results[1], results[2], results[3], results[4]]
    else:
        ordered = list(results[:6])

    # Combine with budget awareness
    full_context = "\n\n".join([r for r in ordered if r])

    # IGNORANCE PROTOCOL GUARDRAIL (Phase 3)
    # If in Silo mode and we found ZERO memories/projects, append a CRITICAL instruction
    ignorance_warning = ""
    if active_domain:
        # Check if the blocks actually contain content beyond the headers
        # Use more specific checks
        has_memories = results[2] and results[2].strip() and results[2].count('\n') > 1
        has_projects = results[4] and results[4].strip() and results[4].count('\n') > 1
        
        if not has_memories and not has_projects:
            ignorance_warning = (
                f"\n\nCRITICAL: MuninnDB returned ZERO results for the focused domain '{active_domain}'. "
                "You MUST explicitly state you have no specific context for this domain. "
                "Do NOT guess. Instead, remain an invested stakeholder by choosing one of these paths:\n"
                "- CURIOSITY: 'I don't have context on that — what's the story?'\n"
                "- HELPFULNESS: 'I don't know that yet, but I could look it up or put it on our list.'\n"
                "- REDIRECT: 'I don't have that detail, but [Name] would likely know.'\n"
                "Match the tone to Zack's energy. Be honest, but don't let the conversation die."
            )

    # Approximate token count (4 chars per token)
    budget_chars = token_budget * 4
    warning_chars = len(ignorance_warning)
    
    if (len(full_context) + warning_chars) > budget_chars:
        # Truncate full_context to fit the warning at the end
        # We ensure we have room for the warning
        keep_chars = max(0, budget_chars - warning_chars)
        full_context = full_context[:keep_chars]
    
    return (full_context + ignorance_warning).strip()


async def _db_memory_fallback(db, max_memories: int, active_domain: Optional[str] = None) -> str:
    """Fallback: recent memories from DB when MuninnDB is offline or returns empty."""
    try:
        active_domain = normalize_domain(active_domain)
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
