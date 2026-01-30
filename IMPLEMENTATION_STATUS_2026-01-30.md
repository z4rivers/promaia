# Calendar-Triggered Agents: Implementation Status

**Date**: 2026-01-30
**Status**: ✅ Phase 1-4 Complete | Ready for Testing

---

## What We Built Tonight

### Core Architecture: Promaia ❤️ MCP

**Promaia Layer** (Unified Read):
- Pre-aggregates all data: Gmail, Calendar, Notion, Slack, Discord
- Agents query via: `query_sql`, `query_vector`, `query_source`
- One interface across all sources
- "I know what I don't know" - full visibility

**MCP Layer** (Write Actions):
- Gmail: Send, draft, reply
- Calendar: Create, update, delete events
- Notion: Full read/write (needs structure exploration)
- "I can act on what I know"

---

## Phase 1: MCP Query Tools ✅

**Problem**: Agents couldn't access Promaia's query tools
**Solution**: Launch MCP server subprocess per agent

**Implementation**: `promaia/agents/executor.py`
- Modified `_build_sdk_options()` to launch Promaia MCP server
- Each agent gets isolated subprocess with workspace + agent_id
- Proper permission enforcement via `source_access` config

**Result**:
```bash
✓ MCP Servers configured: 1
  promaia:
    Command: /path/to/python
    Args: ['-m', 'promaia.mcp.query_tools_server', '--workspace', 'koii', '--agent-id', 'test-calendar']
```

---

## Phase 2: Calendar Integration ✅

**Validation**: Calendar monitor already correctly implemented
- Passes event description as `run_request`
- Includes full metadata (event_id, start_time, summary, link)
- Triggers within 2-hour window before/after event
- Looks ahead 3 hours for upcoming events

**Code**: `promaia/gcal/agent_calendar_monitor.py:79-94`

---

## Phase 3: Gmail MCP Server ✅

**File**: `promaia/mcp/gmail_tools_server.py`

**Write-Only Tools** (reads via Promaia):
- `send_message` - Send new email
- `create_draft` - Create draft (not sent)
- `reply_to_message` - Reply to existing thread

**Why Write-Only?**
All Gmail data is pre-aggregated in Promaia's database. Agents query it via `query_sql`/`query_vector` alongside all other sources. No need for duplicate read APIs.

**Integration**: Auto-launched when agent has `"gmail"` in `mcp_tools`

---

## Phase 4: Calendar MCP Server ✅

**File**: `promaia/mcp/calendar_tools_server.py`

**Write-Only Tools** (reads via Promaia if synced):
- `create_event` - Create calendar event
- `update_event` - Modify existing event
- `delete_event` - Remove event

**Why Write-Only?**
Same reasoning as Gmail - calendar events can be pre-aggregated and queried through Promaia's unified layer.

**Integration**: Auto-launched when agent has `"calendar"` in `mcp_tools`

---

## Test Agent Created ✅

**Configuration** (`promaia.config.json`):
```json
{
  "name": "test-calendar-agent",
  "agent_id": "test-calendar",
  "workspace": "koii",
  "databases": ["journal:7", "stories:all"],
  "mcp_tools": ["promaia"],
  "sdk_enabled": true
}
```

**Next Steps for Testing**:
1. Add `calendar_id` to agent config
2. Create test calendar event 1-2 hours out
3. Run `maia agent calendar-monitor`
4. Watch logs for event detection → agent trigger → MCP tools usage

---

## Files Created/Modified

### Created
- ✅ `promaia/mcp/gmail_tools_server.py` (write-only)
- ✅ `promaia/mcp/calendar_tools_server.py` (write-only)

### Modified
- ✅ `promaia/agents/executor.py` - Added MCP server subprocess launching
- ✅ `promaia.config.json` - Added test agent

---

## Architecture Insights

### The "Whole Map" Principle

**Current**: Schema preview in system prompt (29KB+)
**Better**: Schema as single comprehensive MCP resource

```
promaia://workspace/complete-schema

Contains:
- All database schemas with types
- Sample rows for each database
- Statistics (row counts, date ranges)
- Cross-source relationships
```

**Why?**
- "I don't know what I don't know" ❌ Dangerous
- "I know what I don't know" ✅ Safe
- Agent sees full landscape, makes informed choices
- Like a map: give the whole thing, not one street at a time

**Status**: Planned for future phase

---

## Agent Capabilities Summary

With `mcp_tools: ["promaia", "gmail", "calendar"]`, agents can:

**Read** (via Promaia unified layer):
- ✅ Query journal entries, stories, tasks
- ✅ Search emails by sender, subject, content
- ✅ Find calendar events by date, participant
- ✅ Cross-source queries ("emails mentioning same topics as Slack messages")
- ✅ Semantic search with embeddings across ALL sources

**Write** (via MCP servers):
- ✅ Send emails, create drafts, reply to threads (Gmail)
- ✅ Create calendar events, update schedules (Calendar)
- ✅ Write journal entries (Promaia)
- ✅ Post to Slack/Discord (Promaia messaging)

---

## What's Next

### Ready Now
1. **End-to-End Testing**: Create calendar event → trigger agent → verify MCP tools work
2. **Add Gmail/Calendar to Agent**: Update test agent with `mcp_tools: ["promaia", "gmail", "calendar"]`
3. **Real Use Cases**: Email summaries, meeting scheduling, weekly reports

### Future Enhancements
1. **Schema as MCP Resource**: Move from system prompt to on-demand resource
2. **Notion Integration**: Already available via official Notion MCP + Promaia sync
3. **Orchestration Tools**: Plan/delegate for multi-agent workflows (Phase 5-6)

---

## Success Criteria Met

- ✅ Agents can access Promaia query tools via MCP subprocess
- ✅ Calendar monitor passes events to agents correctly
- ✅ Gmail write tools implemented (send, draft, reply)
- ✅ Calendar write tools implemented (create, update, delete)
- ✅ Proper subprocess isolation per agent
- ✅ Permission enforcement via agent config
- ✅ Write-only MCP architecture (reads via Promaia)
- ✅ Test agent ready for validation

---

## The Beautiful Part

Agents can now do things like:

**"Schedule a meeting with Federico next Tuesday at 2pm to discuss the topics from his recent emails"**

Agent flow:
1. Queries Promaia: `query_vector("emails from Federico about recent topics")`
2. Analyzes email content from pre-aggregated data
3. Calls Calendar MCP: `create_event(summary="Meeting with Federico", start="2026-02-04T14:00:00")`
4. Calls Gmail MCP: `send_message(to="federico@", body="Meeting scheduled...")`

**One unified read layer + targeted write actions = Powerful automation**

---

## Ready to Ship 🚀

The foundation is solid. Time to test with real calendar events and watch the agents come alive!
