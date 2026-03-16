# Phase 4: Platform Activation Plan

**Date:** 2026-03-06 (revised)
**Status:** In progress — 4.1 complete, 4.2+ ready
**Branch:** zbrain (base: feature/agent-scheduler)

## Reality Check

Promaia is 50K+ lines of production code. Phase 4 is ACTIVATION — configure, test, and connect existing modules. No major implementation needed.

## What's Done

- libSQL/MuninnDB + pgvector on Railway Volumes (Phase 1)
- Brain schema + 15 MCP tools (Phase 2 + 3.1 + 4.1)
- MuninnDB cognitive memory sidecar (Phase 4.1)
- Gmail OAuth for 2 accounts (zachary4rivers, zackayak)
- Gmail scan channel (brain/channels/gmail_read.py)
- Notion API key configured, connectivity verified (bot "zbrain" in workspace "Promaia")

## Activation Order (revised for zero-blocker-first)

### 4.2: Email Pipeline Activation
**Why first:** No dependencies on Notion or Calendar. Gmail OAuth already working. Highest daily value — Zack gets email intelligence immediately.

**What exists:** 5,600 lines in mail/ — classifier, intent_detector, response_generator, draft_manager, context_builder, learning_system, gmail_sender. No Notion imports.

**Steps:**
1. Deploy mail schema (email_drafts table) to Railway Volumes
2. Verify prompts exist in prompts/ directory (classification + response)
3. Test classifier against live Gmail threads
4. Test intent_detector with sample messages
5. Wire gmail_read.py cleanup output into classifier for deeper categorization
6. Test draft generation for a real email

**Config needed:** libSQL/MuninnDB (done), ANTHROPIC_API_KEY (done), GOOGLE_API_KEY (done), Gmail OAuth (done)

---

### 4.3: Web Server Activation
**Why second:** Also no Notion/Calendar dependency. Quick win — start the server, verify chat works, opens path to iPhone access.

**What exists:** 2,327 lines — FastAPI app, multi-model chat (Gemini/Claude/GPT/Llama), MCP router with tool execution plumbing.

**Steps:**
1. Install FastAPI deps if missing (fastapi, uvicorn)
2. Start server: `python -m promaia.web.main`
3. Test chat endpoint with Gemini (default model)
4. Test MCP router — list available tools
5. Register brain MCP server in web config
6. Test brain tools from web interface (briefing, capture, search)

**Config needed:** GOOGLE_API_KEY (done), PORT/HOST (defaults fine)

---

### 4.4: Notion Dashboard Setup
**Why third:** Required for agent output visibility, but agents can technically run without it.

**What exists:** 4,300 lines — client, pages, schema, journal_router, notion_writer, notion_setup, notion_config. Bot "zbrain" connected to "Promaia" workspace.

**Steps:**
1. Create root pages in Notion and share with zbrain integration:
   - Brain Dashboard (daily briefings, agent outputs)
   - Projects (mirrors brain.contexts/domains)
2. Run `ensure_agents_database_exists("zbrain")` — duplicate template, store agents_database_id
3. Test NotionOutputWriter — append content to a test page
4. Wire brain events -> Notion updates
5. Store page/database IDs in promaia.config.json

**Config needed:** NOTION_ZACK_API_KEY (done), pages must be shared with integration

---

### 4.5: Google Calendar Setup
**Why fourth:** Quick OAuth setup, enables schedule-aware agents.

**What exists:** 540 lines — GoogleCalendarManager with full CRUD, MCP server (3 write tools).

**Steps:**
1. Enable Google Calendar API in Google Cloud Console (same project as Gmail)
2. Download OAuth desktop credentials to ~/.promaia/google_calendar_credentials.json
3. Run authenticate() — browser flow, token cached
4. Test: list calendars, get upcoming events
5. Register calendar MCP server with Claude if desired

**Config needed:** Google Cloud project (same as Gmail), OAuth creds

---

### 4.6: Agent Scheduler Activation
**Why fifth:** Depends on at least Notion (output pages) and Calendar (schedule awareness). This is THE heartbeat.

**What exists:** Complete scheduler daemon, executor with SDK + legacy mode, agent_config with JSON storage. CLI: `maia agent add`, `maia agent-scheduler-start`.

**Steps:**
1. Define first agent in promaia.config.json:
   - **Morning Briefing** — daily, reads email + calendar + brain actions, writes to Notion
2. Test single agent run: `maia agent run-scheduled morning-briefing`
3. Define additional agents:
   - **Email Triage** — every 2 hours, scans Gmail, surfaces attention items
   - **Evening Digest** — daily 9pm, summarizes day, suggests tonight's work
4. Start scheduler daemon: `maia agent-scheduler-start`
5. Configure Windows Task Scheduler for persistent running
6. Verify agent output appears in Notion

**Config needed:** All previous phases, plus agent definitions in config

---

### 4.7: Information Funneling (deferred)
**Why later:** Needs agents running first. Define sources, build ingestion, create brief templates.

### 4.8: Webflow CMS (when needed)
**Why last:** Only needed when Heatpup or another project needs web publishing.

## Dependency Graph

```
4.2 Email Pipeline ──────────────────────────┐
4.3 Web Server ──────────────────────────────┤
4.4 Notion Dashboard ───────┐                ├── 4.7 Info Funneling
4.5 Google Calendar ────────┼── 4.6 Agents ──┘
                            │
                     (output pages)
```

4.2 and 4.3 are independent — can run in parallel with anything.
4.4 and 4.5 are independent of each other.
4.6 depends on 4.4 + 4.5.
4.7 depends on 4.6.

## Key Principles

1. **Activate, don't implement** — the code exists, configure and test it
2. **Zero-blocker-first** — start with modules that can run today
3. **Dog-food everything** — Zack uses it through tool interfaces, not raw code
4. **Document the process** — every setup step reproducible for other users
5. **libSQL/MuninnDB stays king** — MuninnDB is a sidecar, not replacement
6. **Agents are the heartbeat** — system works autonomously, not just when asked
