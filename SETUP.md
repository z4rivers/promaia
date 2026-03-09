# zBrain Setup Guide

## Prerequisites

- **Python 3.11+** (tested on 3.14)
- **PostgreSQL** with pgvector extension (Supabase recommended -- free tier works)
- **Google AI API key** (for Gemini models and embeddings)
- **Telegram account** (for the bot -- optional but recommended)
- **Claude Code** with MCP support (for the brain MCP server)

## Architecture Overview

```
  Claude Code  <--MCP-->  Brain MCP Server  <-->  Postgres (Supabase)
                                                        |
  Telegram Bot  <--Gemini API-->  Conversation Engine ---+
                                                        |
  Agent Scheduler  --Gemini API-->  Agents (3x daily) --+
       |                                                |
  Event Router  --30s poll-->  brain.events  -->  Push to Telegram / Dashboard
       |
  Web Dashboard  <--FastAPI-->  Jinja2 templates  <-->  Postgres
```

**Services you run:**

| Service | Command | Purpose |
|---------|---------|---------|
| Brain MCP Server | Auto-started by Claude Code via MCP config | 16 brain tools for Claude sessions |
| Agent Scheduler | `python -m promaia.agents.scheduler` | Runs 3 agents on schedule, event router, Gmail check loop |
| Telegram Bot | `python -m promaia.telegram_cli start` | Mobile interface with commands, voice, chat |
| Web Dashboard | `python -m promaia dev` | Browser-based dashboard at localhost:8000 |

---

## Step 1: Clone and Install

```bash
git clone <repo-url>
cd promaia
git checkout zbrain

# Create virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Voice transcription (optional)
pip install deepgram-sdk==6.0.1

# Windows timezone support (required on Windows)
pip install tzdata
```

## Step 2: Database Setup

### Option A: Supabase (Recommended)

1. Create a project at [supabase.com](https://supabase.com) (free tier works)
2. Enable the pgvector extension: Dashboard -> Database -> Extensions -> search "vector" -> enable
3. Copy the session pooler connection string: Dashboard -> Project Settings -> Database -> Connection string -> Session mode

### Option B: Local PostgreSQL

1. Install PostgreSQL 15+
2. Install pgvector extension: `CREATE EXTENSION vector;`
3. Use `postgresql://user:pass@localhost:5432/dbname` as your DATABASE_URL

### Apply Schema

The brain schema is applied automatically on first run via `db_init.py`. All tables are created under a `brain` schema (no conflicts with existing `public` tables).

To apply manually:

```bash
psql $DATABASE_URL -f promaia/brain/schema.sql
```

## Step 3: Configure Environment

```bash
cp .env.example .env
# Edit .env with your actual values
```

**Minimum required:**
- `DATABASE_URL` -- Postgres/Supabase connection string
- `GOOGLE_API_KEY` -- Google AI API key

**For Telegram (highly recommended):**
- `TELEGRAM_BOT_TOKEN` -- Create via @BotFather in Telegram
- `TELEGRAM_WHITELIST` -- Your chat ID (get from @userinfobot)

**For voice (optional):**
- `DEEPGRAM_API_KEY` -- From console.deepgram.com ($200 free credits)

## Step 4: Seed the Brain

```bash
python -c "from promaia.brain.seed import seed_brain; seed_brain('YOUR_WORKSPACE_NAME')"
```

This creates:
- 10 life domains (personal, work, projects, etc.)
- 5 project contexts with standing directives
- Safe to re-run (idempotent)

## Step 5: Register the MCP Server

For Claude Code to access the brain tools:

```bash
claude mcp add brain -- python -m promaia.brain.mcp_server
```

This registers the brain MCP server at user level. Claude Code will auto-start it each session.

## Step 6: Set Up CLAUDE.md

```bash
cp CLAUDE.md.template CLAUDE.md
# Edit CLAUDE.md -- replace {USER_NAME} with your name
```

This file tells Claude Code how to interact with your brain: auto-briefing at session start, when to capture memories, onboarding interview behavior, relational conversation principles.

## Step 7: Start Services

### Agent Scheduler (background agents + event router)

```bash
python -m promaia.agents.scheduler
```

This starts:
- Morning briefing agent (6:00 AM ET)
- Email triage agent (every 8 hours)
- Evening digest agent (4:30 PM ET)
- Event router (30s polling for notifications)
- Gmail check loop (60s polling for new email)

### Telegram Bot

```bash
python -m promaia.telegram_cli start
# Check status:
python -m promaia.telegram_cli status
# Stop:
python -m promaia.telegram_cli stop
```

### Web Dashboard

```bash
python -m promaia dev
# Open http://localhost:8000
```

---

## Gmail OAuth Setup (Optional)

Required for email triage agent and Gmail scan.

1. Create a Google Cloud project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the Gmail API
3. Create OAuth 2.0 credentials (Desktop application type)
4. Download the credentials JSON
5. Place it at `credentials/YOUR_WORKSPACE/gmail_credentials.json`
6. Run the Gmail ingest to trigger OAuth flow:

```bash
python -m promaia.brain.gmail_ingest --workspace YOUR_WORKSPACE --days-back 30
```

This opens a browser for Google OAuth consent. The token is saved to `credentials/YOUR_WORKSPACE/gmail_token.json`.

---

## Troubleshooting

### "Connection refused" on DATABASE_URL
- On Windows, you MUST use the session pooler URL (port 5432), not the direct connection (port 6543). Direct connections fail due to IPv6 routing issues.

### "Module not found: brain"
- Make sure you're running from the project root directory
- Make sure the virtual environment is activated

### Telegram bot not responding
- Check TELEGRAM_WHITELIST contains your chat ID (get from @userinfobot)
- Check TELEGRAM_BOT_TOKEN is correct (get from @BotFather)
- Messages from non-whitelisted users are silently dropped (by design)

### Agent runs but output is empty
- Run `python -m promaia.brain.gmail_ingest --resync-bodies --workspace YOUR_WORKSPACE` to populate email bodies
- Check that brain.memories has data: `SELECT count(*) FROM brain.memories;`
- Check agent prompts exist in `prompts/agent_*.md`

### Voice notes say "not configured"
- Set DEEPGRAM_API_KEY in .env
- Install deepgram-sdk: `pip install deepgram-sdk==6.0.1`

### Budget guard blocking agent runs
- Check daily spend: use `brain_costs` MCP tool in Claude Code
- Default daily cap is $2.00. Agents cost ~$0.01 per cycle on Gemini Flash, so this should not be hit under normal use.

### MuninnDB errors
- MuninnDB is optional. The system works without it (Postgres handles all retrieval).
- If you want cognitive memory features (Hebbian learning, temporal decay), see `Phase 10` in `.planning/phases/10-memory-polish/`.

---

## What Each Service Does

### Brain MCP Server (`promaia.brain.mcp_server`)
16 tools exposed to Claude Code via MCP protocol. When you start a Claude Code session, it auto-loads the briefing and profile. You can capture memories, search, manage actions, update project contexts -- all through natural conversation.

### Agent Scheduler (`promaia.agents.scheduler`)
Runs three autonomous agents on Gemini Flash. Each agent:
1. Loads brain context (profile, actions, projects, memories)
2. Loads its prompt from `prompts/agent_*.md`
3. Calls Gemini API with context + prompt
4. Emits events to `brain.events` with urgency classification
5. Pushes output to Telegram (for scheduled agents)

The scheduler also runs the event router (polls `brain.events` every 30s) and a lightweight Gmail check loop (60s polling for new unread email).

### Telegram Bot (`promaia.telegram_cli`)
Mobile interface using aiogram. Commands query the brain directly. Free text is auto-captured. Voice notes are transcribed via Deepgram. The bot also receives push notifications from the event router (urgent emails, scheduled briefings).

### Web Dashboard (`promaia dev`)
FastAPI + Jinja2 rendering live brain data. Five pages: main dashboard (memories + actions), projects, email, profile. Notification badge polls for unrouted events every 60 seconds.

---

## Directory Structure (zBrain additions)

```
promaia/
  brain/                    # Core brain modules
    mcp_server.py           # 16-tool MCP server
    engine.py               # Mode detection, guardrails, staleness
    schema.sql              # 13 brain tables
    extraction.py           # Action extraction via Gemini
    onboarding.py           # Onboarding state machine
    gmail_ingest.py         # Gmail sync pipeline
    muninn.py               # MuninnDB client (optional)
    seed.py                 # Domain and context seeder
    channels/               # Onboarding channels
      question_bank.py      # 16 interview questions
      interview.py          # Question selection by coverage gaps
      pc_scan.py            # Local machine scan
      gmail_read.py         # Gmail pattern scan
  telegram/                 # Telegram bot
    bot.py                  # Dispatcher, polling, auto-reconnect
    auth.py                 # Whitelist middleware
    brain_ops.py            # Async brain operations
    conversation.py         # Gemini conversation engine
    formatting.py           # Message splitting
    channel.py              # Event bus notification channel
    handlers/
      commands.py           # /briefing, /search, /capture, etc.
      messages.py           # Free-text auto-capture
      voice.py              # Deepgram transcription
      replies.py            # Push notification reply handler
  events/                   # Event bus
    models.py               # Urgency enum, Event dataclass
    emitter.py              # Agent output -> events
    router.py               # Polling loop, quiet hours, dispatch
    channels.py             # Channel ABC, DashboardChannel
    rate_limiter.py         # SQL-backed rate limiting
  agents/                   # Agent infrastructure (new files)
    model_router.py         # Task-to-model mapping
    cost_tracker.py         # Per-call cost logging
    gemini_executor.py      # Gemini API wrapper
    budget_guard.py         # Budget caps, runaway detection
    agent_context.py        # Context loader, tool injection
  web/
    routers/dashboard.py    # Dashboard routes
    templates/*.html        # Jinja2 templates
    static/skins/*.css      # CSS skins
prompts/
  agent_morning_briefing.md # Morning briefing prompt
  agent_email_triage.md     # Email triage prompt
  agent_evening_digest.md   # Evening digest prompt
CLAUDE.md                   # Claude Code brain instructions
ZBRAIN.md                   # This documentation
SETUP.md                    # This setup guide
.env.example                # Environment variable template
```
- Add Desktop UI capabilities to manually edit/adjust notes and memories captured during audio mode (Step 11.5 Expansion)
