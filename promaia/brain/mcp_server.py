"""
Brain MCP Server — 17 tools for zBrain.

Exposes Claude's persistent memory system as MCP tools over Streamable HTTP.
Runs as an always-on daemon (default: 127.0.0.1:8751) with bearer token auth.
Claude calls these tools to get briefings, capture thoughts, search memories,
manage project context, track actions, maintain a personal profile,
manage the onboarding flow, run data ingestion channels, and perform
cognitive retrieval via MuninnDB.

Tools:
    briefing        — stale projects + pending actions + recent heartbeat activity
    capture         — store memory with embedding, auto-extract actions (dual-writes to MuninnDB)
    search          — semantic vector search + MuninnDB ACTIVATE (parallel trial)
    recall          — recent memories filtered by domain or time range
    context         — read a domain's directive and current state
    update_context  — write/upsert a domain's context
    actions         — list or mark-done brain actions
    profile         — read personal profile (all or by category)
    update_profile  — set a profile field with value, confidence, and source
    onboard         — manage the onboarding flow (start/status/channel_update/complete)
    pc_scan         — scan local git repos, files, and apps for profile data
    gmail_scan      — scan Gmail inbox for contacts, patterns, and topics
    gmail_query     — search stored Gmail content by sender, subject, or full-text
    activate        — MuninnDB cognitive retrieval via ACTIVATE pipeline
    timeline        — reference timeline of life events (add/list/query)
    brain_costs     — daily/weekly agent cost summary (ask "what am I spending?")

Usage:
    python -m promaia.brain.mcp_server
"""
import asyncio
import contextlib
import json
import logging
import os
import secrets
import sys
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv, set_key

# Load .env from the project root (walk up from this file to find it)
_project_root = Path(__file__).resolve().parents[2]
_env_path = _project_root / ".env"
load_dotenv(_env_path)

import numpy as np

try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent
except ImportError:
    print("ERROR: mcp package not installed. Install with: pip install 'mcp>=1.26.0'", file=sys.stderr)
    sys.exit(1)

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send

from promaia.storage.db_factory import get_db
from promaia.storage.vector_db import VectorDBManager
from promaia.brain import engine
from promaia.brain.extraction import extract_actions, extract_insights
from promaia.brain.core.memory_pipeline import capture_memory
from promaia.brain.onboarding import (
    start_onboarding, get_onboarding_status,
    mark_channel_progress, get_profile_coverage,
    complete_onboarding, EXPECTED_FIELDS,
)
from promaia.brain.channels.interview import (
    get_interview_state,
    get_next_question,
    mark_question_answered,
)
from promaia.brain.muninn import get_muninn

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Server + session state
# ---------------------------------------------------------------------------
server = Server("zbrain-brain")

from promaia.brain.mcp.core_context import get_db, get_vector_mgr


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[Tool]:
    """Enumerate all 17 brain tools."""
    return [
        Tool(
            name="briefing",
            description=(
                "Return a session briefing: stale projects, pending actions, "
                "and recent heartbeat activity from the last 24 hours. "
                "Call this at the start of every session. "
                "IMPORTANT: This brain uses the 'Along For The Ride' standard with two halves: "
                "(1) CAPTURE: Proactively use 'capture' whenever something substantive happens — "
                "decisions, insights, discoveries, context shifts, or preferences revealed. "
                "(2) RETRIEVE: When the user brings up a topic, idea, or reference that might "
                "connect to existing memories, call 'activate' with their context BEFORE responding. "
                "If you find relevant associated information, offer it naturally — 'this sounds like "
                "our discussion about...', 'is this related to...?', 'would you like me to save this "
                "with...?' Don't assume the user forgot — you're offering connections, not correcting "
                "memory. The brain should feel like a partner who was there for every conversation, "
                "not a search engine that waits to be queried."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="capture",
            description=(
                "Store a thought, note, or observation as a persistent memory. "
                "Automatically extracts actionable items, decisions, insights, "
                "preferences, and secondary elements (asides) — storing each as "
                "an independent tagged memory for MuninnDB's cognitive graph. "
                "USE PROACTIVELY: Under the 'Along For The Ride' standard, capture "
                "substantively throughout conversations — not just when asked. "
                "Capture decisions made, technical discoveries, architecture shifts, "
                "revealed preferences, and valuable tangents. The cognitive engine "
                "handles relevance sorting via Hebbian learning and temporal decay; "
                "your job is to feed it richly. Domain tagging is critical for "
                "cross-session pattern discovery."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The text to store as a memory."
                    },
                    "domain": {
                        "type": "string",
                        "description": "Optional domain name (e.g. 'promaia', 'heatpup')."
                    }
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="search",
            description=(
                "Semantic vector search across all brain memories. "
                "Returns the most relevant memories ranked by cosine similarity. "
                "CRITICAL: Always check the timestamp of returned results. If the data is old, verify it is still accurate before acting."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default 10).",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="recall",
            description=(
                "Retrieve recent memories, optionally filtered by domain and time range. "
                "Set has_media=true to ONLY return memories that contain attached files (images/audio/docs). "
                "CRITICAL: Always check the timestamp of returned results. If the data is old, verify it is still accurate before acting."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Filter by domain name (optional)."
                    },
                    "days": {
                        "type": "integer",
                        "description": "How many days back to look (default 30).",
                        "default": 30
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default 20).",
                        "default": 20
                    },
                    "has_media": {
                        "type": "boolean",
                        "description": "If true, only returns memories that have attached files.",
                        "default": False
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="context",
            description=(
                "Read the standing directive and current state for a domain. "
                "Use this to understand what's happening in a specific project. "
                "CRITICAL: Look at the 'Last updated' field. If the context is stale, search for newer information before acting."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name to look up (e.g. 'promaia')."
                    }
                },
                "required": ["domain"]
            }
        ),
        Tool(
            name="update_context",
            description=(
                "Write or update the standing directive and current state for a domain. "
                "Creates the domain and context if they don't exist yet."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name to update."
                    },
                    "directive": {
                        "type": "string",
                        "description": "Standing directive for this domain (optional)."
                    },
                    "current_state": {
                        "type": "string",
                        "description": "Current status or state of this domain (optional)."
                    },
                    "priority": {
                        "type": "integer",
                        "description": "Priority 1-10 (1=highest). Default 5 (optional)."
                    }
                },
                "required": ["domain"]
            }
        ),
        Tool(
            name="actions",
            description=(
                "List pending actions, optionally filtered by domain. "
                "Pass mark_done with an action ID to mark it complete."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status: 'pending', 'done', 'stale' (default 'pending').",
                        "default": "pending"
                    },
                    "domain": {
                        "type": "string",
                        "description": "Filter by domain name (optional)."
                    },
                    "mark_done": {
                        "type": "integer",
                        "description": "Action ID to mark as completed (optional)."
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="profile",
            description=(
                "Read the user's personal profile. Returns all dimensions or "
                "a specific category. Use mode='narrative' for a synthesized "
                "portrait (~1500 tokens vs ~10k for full dump). "
                "Categories include: identity, cognitive_style, "
                "energy_patterns, emotional_landscape, values_and_motivation, "
                "communication, work_patterns, relationships, neurodivergence."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Filter by category (optional). Leave empty for full profile."
                    },
                    "query": {
                        "type": "string",
                        "description": "Semantic search across profile (optional). E.g. 'what motivates me'"
                    },
                    "mode": {
                        "type": "string",
                        "description": (
                            "Output mode: 'narrative' returns a synthesized ~1500-token portrait "
                            "(cached, regenerated on profile changes). 'full' returns all structured "
                            "rows. Default returns all rows (same as 'full')."
                        )
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="update_profile",
            description=(
                "Set or update a personal profile field. Each field has a category, "
                "name, value, confidence score (0.0-1.0), and source "
                "(declared=user said it, inferred=AI observed it, confirmed=user verified inference). "
                "Use this during onboarding interviews, when learning about the user, "
                "or when the user corrects a previous inference."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Profile category (e.g. 'cognitive_style', 'communication', 'values_and_motivation')."
                    },
                    "field": {
                        "type": "string",
                        "description": "Field name (e.g. 'decision_making', 'humor_type', 'chronotype')."
                    },
                    "value": {
                        "description": "The value — can be string, number, array, or object."
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence 0.0-1.0 (default 0.8 for declared, 0.5 for inferred)."
                    },
                    "source": {
                        "type": "string",
                        "description": "Source: 'declared', 'inferred', or 'confirmed' (default 'declared')."
                    }
                },
                "required": ["category", "field", "value"]
            }
        ),
        Tool(
            name="onboard",
            description=(
                "Manage the onboarding flow. Actions: "
                "'start' begins or resumes onboarding, "
                "'status' returns current progress and profile coverage gaps, "
                "'next_question' returns the next interview question to ask based on profile gaps, "
                "'channel_update' marks a channel's progress, "
                "'complete' finalizes onboarding. "
                "Call 'next_question' at session start to get a natural question to weave into conversation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "One of: start, status, next_question, channel_update, complete",
                        "enum": ["start", "status", "next_question", "channel_update", "complete"]
                    },
                    "channel": {
                        "type": "string",
                        "description": "Channel name (for channel_update): interview, pc_scan, gmail, photos"
                    },
                    "channel_status": {
                        "type": "string",
                        "description": "New status (for channel_update): in_progress, complete, skipped"
                    },
                    "fields_populated": {
                        "type": "integer",
                        "description": "Number of profile fields this channel contributed (for channel_update)"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Free-form notes about what was covered (for channel_update)"
                    }
                },
                "required": ["action"]
            }
        ),
        Tool(
            name="pc_scan",
            description=(
                "Run the PC digital fingerprint scan. Analyzes local git repos, "
                "file structure, and installed apps to infer profile data. "
                "Results are stored in profile with source='inferred'. "
                "Safe to run multiple times — results are upserted."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="gmail_scan",
            description=(
                "Scan Gmail inbox for cleanup, triage, and intelligence extraction. "
                "Supports multiple accounts. Modes: 'cleanup' (categorize junk vs real), "
                "'triage' (surface emails needing attention), 'intelligence' (extract contacts "
                "and patterns for profile), or 'full' (all layers). "
                "Never stores raw email content."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "account": {
                        "type": "string",
                        "description": (
                            "Account label or partial match (e.g. 'zackayak'). "
                            "Omit to scan all connected accounts."
                        ),
                    },
                    "days_back": {
                        "type": "integer",
                        "description": "How many days of email to scan (default 30).",
                        "default": 30
                    },
                    "max_emails": {
                        "type": "integer",
                        "description": "Maximum emails per account to process (default 200).",
                        "default": 200
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["cleanup", "triage", "intelligence", "full"],
                        "description": (
                            "Scan mode. 'cleanup': categorize junk/newsletters/human mail. "
                            "'triage': find emails needing attention. "
                            "'intelligence': extract contacts/patterns for brain profile. "
                            "'full': all of the above. Default: 'full'."
                        ),
                        "default": "full"
                    },
                    "before": {
                        "type": "string",
                        "description": (
                            "Only scan emails before this date (YYYY/MM/DD). "
                            "Use with days_back to scan historical windows."
                        ),
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="gmail_query",
            description=(
                "Search stored Gmail content in the database. "
                "Query by sender, subject keywords, date range, or full-text search. "
                "Returns matching emails with subject, sender, date, and snippet. "
                "Use this to find specific emails or review communication history."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Full-text search across subject and message content.",
                    },
                    "sender": {
                        "type": "string",
                        "description": "Filter by sender email (partial match).",
                    },
                    "days_back": {
                        "type": "integer",
                        "description": "Only search emails from the last N days.",
                        "default": 30
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default 20).",
                        "default": 20
                    },
                },
                "required": []
            }
        ),
        Tool(
            name="activate",
            description=(
                "MuninnDB cognitive retrieval using the ACTIVATE pipeline. "
                "Uses context-based associative recall with Hebbian learning, "
                "temporal decay, and graph traversal -- different from vector search. "
                "Returns memories ranked by cognitive relevance, not just similarity. "
                "USE PROACTIVELY: When the user mentions a topic, project, person, or idea "
                "that might relate to past conversations or stored knowledge, call this "
                "with their context to check for connections BEFORE responding. Offer "
                "relevant associated information naturally — don't wait to be asked. "
                "This is the 'recognition' half of the Along For The Ride standard."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "context": {
                        "type": "string",
                        "description": "Natural language context for cognitive retrieval. Describe what you're thinking about."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results (default 10).",
                        "default": 10
                    },
                    "threshold": {
                        "type": "number",
                        "description": "Minimum activation score 0.0-1.0 (default 0.1, lower = more results).",
                        "default": 0.1
                    }
                },
                "required": ["context"]
            }
        ),
        Tool(
            name="timeline",
            description=(
                "Reference timeline of life events. Add milestones, query chronologically, "
                "or find events near a date. Categories: life, career, relationship, education, "
                "health, location, project, milestone. Significance 1-10 (10=most significant). "
                "Supports fuzzy dates (month/year precision)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["add", "list", "around"],
                        "description": (
                            "'add': record a life event. "
                            "'list': list events (optional category/date filters). "
                            "'around': find events near a specific date."
                        )
                    },
                    "event_date": {
                        "type": "string",
                        "description": "Date as YYYY-MM-DD, YYYY-MM, or YYYY. Required for 'add' and 'around'."
                    },
                    "title": {
                        "type": "string",
                        "description": "Short label for the event (e.g. 'Moved to Portland'). Required for 'add'."
                    },
                    "description": {
                        "type": "string",
                        "description": "Longer description of the event. Optional."
                    },
                    "category": {
                        "type": "string",
                        "enum": ["life", "career", "relationship", "education", "health", "location", "project", "milestone"],
                        "description": "Event category. Default: 'life'."
                    },
                    "significance": {
                        "type": "integer",
                        "description": "1-10 importance (10=most significant). Default: 5."
                    },
                    "domain": {
                        "type": "string",
                        "description": "Optional domain link (e.g. 'heatpup', 'promaia')."
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for filtering."
                    },
                    "range_days": {
                        "type": "integer",
                        "description": "For 'around': how many days before/after to search (default 365).",
                        "default": 365
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results for 'list'/'around' (default 20).",
                        "default": 20
                    }
                },
                "required": ["action"]
            }
        ),
        Tool(
            name="brain_costs",
            description=(
                "Show agent API costs: today's spend and daily breakdown "
                "for the last N days. Ask 'what am I spending?' to see "
                "a table of costs per agent per day."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "How many days of cost history to return (default 7).",
                        "default": 7
                    }
                },
                "required": []
            }
        ),

        Tool(
            name="message_send",
            description="Send a message to an agent (or broadcast if to=null).",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "type": {"type": "string", "description": "request, response, correction, heads_up, handoff"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "context": {"type": "string", "description": "JSON payload of state (active_files, etc)"},
                    "priority": {"type": "string", "description": "normal, high, urgent"}
                },
                "required": ["type", "subject"]
            }
        ),
        Tool(
            name="message_check",
            description="Check for new messages addressed to me.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="message_pickup",
            description="Mark a message as in_progress and update presence. Pass active_files as JSON array to lock files.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "active_files": {"type": "string", "description": "JSON array of file paths"}
                },
                "required": ["id"]
            }
        ),
        Tool(
            name="message_respond",
            description="Reply to a message (threads via reply_to).",
            inputSchema={
                "type": "object",
                "properties": {
                    "reply_to": {"type": "integer"},
                    "body": {"type": "string"},
                    "type": {"type": "string", "default": "response"},
                    "context": {"type": "string"}
                },
                "required": ["reply_to", "body"]
            }
        ),
        Tool(
            name="message_thread",
            description="View full conversation thread.",
            inputSchema={"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}
        ),
        Tool(
            name="message_done",
            description="Mark a thread resolved.",
            inputSchema={"type": "object", "properties": {"id": {"type": "integer"}}, "required": ["id"]}
        ),
        Tool(
            name="presence_who",
            description="Who is online right now and what are they working on?",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="ide_activity_broadcast",
            description=(
                "Broadcast a status message to the Promaia dashboard's Active Session feed. "
                "Use this to natively report what you are doing in the IDE (e.g. 'Writing test cases for X')."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The activity text to broadcast."
                    }
                },
                "required": ["text"]
            }
        ),
    ]


# ---------------------------------------------------------------------------
# Activity tracking — lets the health endpoint report what the brain is doing
# ---------------------------------------------------------------------------
_active_calls: list[str] = []

# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Dispatch tool calls to handler functions."""
    logger.info(f"Brain tool call: {name}")
    _active_calls.append(name)
    try:
        if name == "briefing":
            return await _handle_briefing(arguments)
        elif name == "capture":
            return await _handle_capture(arguments)
        elif name == "search":
            return await _handle_search(arguments)
        elif name == "recall":
            return await _handle_recall(arguments)
        elif name == "context":
            return await _handle_context(arguments)
        elif name == "update_context":
            return await _handle_update_context(arguments)
        elif name == "actions":
            return await _handle_actions(arguments)
        elif name == "profile":
            return await _handle_profile(arguments)
        elif name == "update_profile":
            return await _handle_update_profile(arguments)
        elif name == "onboard":
            return await _handle_onboard(arguments)
        elif name == "pc_scan":
            return await _handle_pc_scan(arguments)
        elif name == "gmail_scan":
            return await _handle_gmail_scan(arguments)
        elif name == "gmail_query":
            return await _handle_gmail_query(arguments)
        elif name == "activate":
            return await _handle_activate(arguments)
        elif name == "timeline":
            return await _handle_timeline(arguments)
        elif name == "brain_costs":
            return await _handle_brain_costs(arguments)

        elif name == "message_send": return await _handle_message_send(arguments)
        elif name == "message_check": return await _handle_message_check(arguments)
        elif name == "message_pickup": return await _handle_message_pickup(arguments)
        elif name == "message_respond": return await _handle_message_respond(arguments)
        elif name == "message_thread": return await _handle_message_thread(arguments)
        elif name == "message_done": return await _handle_message_done(arguments)
        elif name == "presence_who": return await _handle_presence_who(arguments)
        elif name == "ide_activity_broadcast":
            import httpx
            async with httpx.AsyncClient() as client:
                try:
                    await client.post("http://localhost:8000/api/brain/broadcast", json={"text": arguments["text"]}, timeout=3.0)
                except Exception as ex:
                    logger.warning(f"Failed to broadcast IDE activity: {ex}")
            return [TextContent(type="text", text="Broadcast sent to dashboard.")]
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error in {name}: {str(e)}")]
    finally:
        try:
            _active_calls.remove(name)
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
from promaia.brain.mcp.handlers.capture_ops import _handle_capture, _handle_search, _handle_recall
from promaia.brain.mcp.handlers.context_ops import _handle_briefing, _handle_context, _handle_update_context, _handle_actions
from promaia.brain.mcp.handlers.profile_ops import _handle_profile, _handle_update_profile, _handle_onboard, _handle_pc_scan, _handle_timeline
from promaia.brain.mcp.handlers.gmail_ops import _handle_gmail_scan, _handle_gmail_query
from promaia.brain.mcp.handlers.muninn_ops import _handle_activate
from promaia.brain.mcp.handlers.signal_ops import _handle_message_send, _handle_message_check, _handle_message_pickup, _handle_message_respond, _handle_message_thread, _handle_message_done, _handle_presence_who

from promaia.brain.mcp.handlers.metrics_ops import _handle_brain_costs

# ---------------------------------------------------------------------------
# Auth + Health
# ---------------------------------------------------------------------------
def _get_token() -> str:
    """Read BRAIN_MCP_TOKEN from env, auto-generate if missing."""
    token = os.environ.get("BRAIN_MCP_TOKEN", "").strip()
    if not token:
        token = secrets.token_urlsafe(32)
        # Persist to .env so it survives restarts
        try:
            set_key(str(_env_path), "BRAIN_MCP_TOKEN", token)
        except Exception:
            pass  # .env might not be writable — log and continue
        os.environ["BRAIN_MCP_TOKEN"] = token
        logger.info("Auto-generated BRAIN_MCP_TOKEN (saved to .env)")
    return token


async def _health_endpoint(request: Request) -> JSONResponse:
    """Unauthenticated health check for dashboard polling."""
    return JSONResponse({
        "status": "ok",
        "service": "zbrain-brain",
        "active": len(_active_calls) > 0,
        "active_count": len(_active_calls),
        "tools": list(_active_calls),
    })


def _bearer_auth_middleware(app):
    """Wrap an ASGI app with bearer token verification."""
    async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            request = Request(scope, receive)
            auth_header = request.headers.get("authorization", "")
            expected = f"Bearer {_get_token()}"
            if not secrets.compare_digest(auth_header, expected):
                response = Response("Unauthorized", status_code=401)
                await response(scope, receive, send)
                return
        await app(scope, receive, send)
    return middleware


# ---------------------------------------------------------------------------
# Starlette app factory
# ---------------------------------------------------------------------------
def create_app() -> Starlette:
    """Build the Starlette ASGI app with MCP session manager."""
    session_manager = StreamableHTTPSessionManager(app=server)

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            logger.info("Brain MCP daemon ready")
            yield

    app = Starlette(
        routes=[
            Route("/health", _health_endpoint),
            Mount("/mcp", app=_bearer_auth_middleware(session_manager.handle_request)),
        ],
        lifespan=lifespan,
    )
    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run_selftest():
    """Run diagnostics to verify MCP server dependencies before launching."""
    print("Running zBrain MCP Server Self-Test...\n")
    success = True

    # 1. Database Check
    try:
        from promaia.storage.db_factory import get_db
        db = get_db()
        db.execute("SELECT 1")
        print("  Database Connection: OK")
    except Exception as e:
        print(f"  Database Connection: FAILED ({e})")
        success = False

    # 2. Vector DB Check
    try:
        from promaia.storage.vector_db import VectorDBManager
        mgr = VectorDBManager()
        print("  Vector DB Manager: OK")
    except Exception as e:
        print(f"  Vector DB Manager: FAILED ({e})")
        success = False

    # 3. MuninnDB Check
    try:
        from promaia.brain.muninn import get_muninn
        import asyncio
        m = asyncio.run(get_muninn())
        if m is not None:
            print("  MuninnDB Access: OK")
        else:
            print("  MuninnDB Access: FAILED (Returned None - Server may be down)")
            success = False
    except Exception as e:
        print(f"  MuninnDB Access: FAILED ({e})")
        success = False

    # 4. LLM API Keys
    import os
    keys = {"ANTHROPIC": os.getenv("ANTHROPIC_API_KEY"), "OPENAI": os.getenv("OPENAI_API_KEY"), "GEMINI": os.getenv("GOOGLE_API_KEY")}
    found = [k for k, v in keys.items() if v]
    if found:
        print(f"  LLM API Keys: OK ({', '.join(found)})")
    else:
        print("  LLM API Keys: FAILED (No core generation keys found)")
        success = False

    # 5. Bearer token check
    token = _get_token()
    print(f"  Bearer Token: OK (first 8 chars: {token[:8]}...)")

    print(f"\nSelf-Test {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        run_selftest()
    else:
        import uvicorn

        host = os.environ.get("BRAIN_MCP_HOST", "127.0.0.1")
        port = int(os.environ.get("BRAIN_MCP_PORT", "8751"))
        log_level = os.environ.get("BRAIN_LOG_LEVEL", "info").lower()

        logger.info(f"Starting zBrain MCP daemon on {host}:{port}")
        try:
            uvicorn.run(
                create_app(),
                host=host,
                port=port,
                log_level=log_level,
            )
        except KeyboardInterrupt:
            logger.info("Brain MCP daemon stopped")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)
        finally:
            try:
                from promaia.storage.db_factory import get_db
                get_db().close_pool()
            except Exception as e:
                logger.error(f"Failed to close database connection pool: {e}")
