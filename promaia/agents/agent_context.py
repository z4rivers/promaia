"""
AgentContext: Standardized awareness context for all agents.

Provides a consistent view of user identity, temporal state, pending actions,
and active projects. Loaded once per scheduler cycle via load_from_brain()
and shared across all agent runs (smart batching -- ROUTE-05).

The to_prompt_block() method renders a ~200-300 token text block suitable
for injection into agent system prompts as the dynamic context tier.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# Per-agent MCP tool mappings (ROUTE-04)
# Each agent only gets documentation for tools it actually uses,
# reducing prompt size and avoiding confusion.
AGENT_TOOL_REGISTRY: dict[str, list[dict[str, str]]] = {
    "morning-briefing": [
        {"name": "brain_search", "description": "Search memories by keyword or semantic similarity"},
        {"name": "brain_context", "description": "Get standing directive and current state for a project"},
        {"name": "profile", "description": "Read user profile traits and preferences"},
    ],
    "email-triage": [
        {"name": "brain_search", "description": "Search memories by keyword or semantic similarity"},
        {"name": "gmail_list", "description": "List recent emails from Gmail accounts"},
        {"name": "gmail_read", "description": "Read full email content by message ID"},
        {"name": "gmail_labels", "description": "List Gmail labels and categories"},
    ],
    "evening-digest": [
        {"name": "brain_search", "description": "Search memories by keyword or semantic similarity"},
        {"name": "brain_context", "description": "Get standing directive and current state for a project"},
        {"name": "brain_actions", "description": "List pending actions with optional domain filter"},
    ],
}


@dataclass
class AgentContext:
    """Standardized awareness context for all agents.

    Fields are populated either manually (for testing) or via the
    load_from_brain() classmethod which queries Postgres brain tables.
    """

    # User identity
    user_name: str
    user_profile_summary: str  # ~200 tokens from brain.profile top traits

    # Temporal
    current_time: datetime
    day_of_week: str
    is_office_day: bool

    # Goals and state
    pending_actions: list[dict] = field(default_factory=list)
    active_projects: list[dict] = field(default_factory=list)
    recent_memories: list[dict] = field(default_factory=list)

    # Domain-specific (populated per agent)
    domain_state: dict = field(default_factory=dict)

    def to_prompt_block(self) -> str:
        """Render as a prompt-injectable text block (~200-300 tokens).

        This output is placed in the context tier (bottom) of the agent
        prompt, after the stable anchor and tools tiers.
        """
        # Determine timezone label from current_time
        tz_label = self.current_time.strftime("%Z") or "UTC"

        parts = [
            "## User Context",
            f"Current time: {self.current_time.strftime('%Y-%m-%d %H:%M')} {tz_label} ({self.day_of_week})",
            f"User: {self.user_name}",
            f"Profile: {self.user_profile_summary}",
        ]

        if self.is_office_day:
            parts.append("Office day: Yes (8am-12pm)")
        else:
            parts.append("Office day: No")

        # Pending actions
        if self.pending_actions:
            parts.append(f"Pending actions: {len(self.pending_actions)} items")
            for action in self.pending_actions[:3]:
                desc = action.get("description", "Unknown action")
                parts.append(f"  - {desc}")
        else:
            parts.append("Pending actions: None")

        # Active projects
        if self.active_projects:
            project_names = [p.get("name", "Unknown") for p in self.active_projects]
            parts.append(f"Active projects: {', '.join(project_names)}")
        else:
            parts.append("Active projects: None")

        # Recent activity
        if self.recent_memories:
            parts.append("Recent activity:")
            for mem in self.recent_memories[:3]:
                summary = mem.get("summary") or mem.get("content", "")
                if len(summary) > 80:
                    summary = summary[:77] + "..."
                parts.append(f"  - {summary}")

        # Domain state
        if self.domain_state:
            domain_parts = []
            for key, value in self.domain_state.items():
                domain_parts.append(f"{key.replace('_', ' ')}: {value}")
            if domain_parts:
                parts.append("Domain: " + ", ".join(domain_parts))

        return "\n".join(parts)

    @classmethod
    def load_from_brain(cls, domain_state: Optional[dict] = None) -> "AgentContext":
        """Load context from brain Postgres tables.

        This is the smart batching mechanism: call once per scheduler cycle,
        pass the result to all 3 agents rather than each agent querying
        independently.

        Args:
            domain_state: Optional per-agent domain data (e.g., {"unread_emails": 5}).

        Returns:
            Populated AgentContext instance.
        """
        from promaia.storage.postgres_db import get_postgres_db

        db = get_postgres_db()

        # Load user name
        user_name = "Zack"  # default
        try:
            row = db.fetch_one(
                "SELECT value FROM brain.profile WHERE field = 'name' LIMIT 1"
            )
            if row and row.get("value"):
                val = row["value"]
                # value is JSONB, could be string or wrapped
                if isinstance(val, str):
                    user_name = val
                elif isinstance(val, dict):
                    user_name = val.get("value", val.get("name", "Zack"))
                else:
                    user_name = str(val)
        except Exception as e:
            logger.warning("Could not load user name from brain.profile: %s", e)

        # Build profile summary from top traits
        user_profile_summary = "No profile data available"
        try:
            rows = db.fetch_all(
                """SELECT category, field, value, confidence
                   FROM brain.profile
                   ORDER BY confidence DESC
                   LIMIT 10"""
            )
            if rows:
                trait_parts = []
                for r in rows:
                    val = r.get("value", "")
                    if isinstance(val, dict):
                        val = val.get("value", str(val))
                    trait_parts.append(f"{r['field']}: {val}")
                user_profile_summary = "; ".join(trait_parts[:8])
                # Truncate if too long
                if len(user_profile_summary) > 500:
                    user_profile_summary = user_profile_summary[:497] + "..."
        except Exception as e:
            logger.warning("Could not load profile summary: %s", e)

        # Load pending actions
        pending_actions: list[dict] = []
        try:
            rows = db.fetch_all(
                """SELECT id, description, status, extracted_at
                   FROM brain.actions
                   WHERE status = 'pending'
                   ORDER BY extracted_at DESC
                   LIMIT 5"""
            )
            pending_actions = rows
        except Exception as e:
            logger.warning("Could not load pending actions: %s", e)

        # Load active project contexts
        active_projects: list[dict] = []
        try:
            rows = db.fetch_all(
                """SELECT c.id, d.name, c.directive, c.current_state, c.priority
                   FROM brain.contexts c
                   JOIN brain.domains d ON c.domain_id = d.id
                   WHERE d.is_project = true
                   ORDER BY c.priority ASC, c.last_updated DESC
                   LIMIT 5"""
            )
            active_projects = rows
        except Exception as e:
            logger.warning("Could not load active projects: %s", e)

        # Load recent memories
        recent_memories: list[dict] = []
        try:
            rows = db.fetch_all(
                """SELECT id, content, summary, domain, created_at
                   FROM brain.memories
                   ORDER BY created_at DESC
                   LIMIT 5"""
            )
            recent_memories = rows
        except Exception as e:
            logger.warning("Could not load recent memories: %s", e)

        # Temporal awareness
        now = datetime.now(timezone.utc)
        day_name = now.strftime("%A")

        # Determine if office day (Thursday per Zack's schedule)
        is_office = day_name == "Thursday"

        return cls(
            user_name=user_name,
            user_profile_summary=user_profile_summary,
            current_time=now,
            day_of_week=day_name,
            is_office_day=is_office,
            pending_actions=pending_actions,
            active_projects=active_projects,
            recent_memories=recent_memories,
            domain_state=domain_state or {},
        )


def get_agent_tools_docs(agent_name: str) -> str:
    """Return tool documentation relevant to a specific agent (ROUTE-04).

    Each agent only sees documentation for tools it actually uses,
    reducing prompt size. The actual tool schemas are loaded at runtime
    by the executor -- this controls which tool docs go into the system
    prompt.

    Args:
        agent_name: One of 'morning-briefing', 'email-triage', 'evening-digest'.

    Returns:
        Formatted string listing tool names and descriptions.
    """
    tools = AGENT_TOOL_REGISTRY.get(agent_name, [])

    if not tools:
        return f"No tools registered for agent '{agent_name}'."

    lines = [f"## Available Tools ({agent_name})"]
    lines.append("")
    for tool in tools:
        name = tool["name"]
        desc = tool.get("description", "Available at runtime")
        lines.append(f"- **{name}**: {desc}")

    lines.append("")
    lines.append("Tool schemas are injected at runtime by the executor.")

    return "\n".join(lines)
