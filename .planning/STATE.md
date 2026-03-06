# State: zBrain

## Current Position

Phase: Phase 4 — Full Platform Activation
Status: Dashboard live, brain wired, agents ready, 10 projects mapped.
Last activity: 2026-03-08 — Dashboard + agent brain integration + project portfolio corrected

## What's Built & Working

### Web Dashboard (LIVE)
- **Server:** `python -m promaia.web.main` → `http://localhost:8000`
- **5 pages:** `/` `/dashboard` `/projects` `/email` `/profile`
- **6 CSS skins:** stone-garden, ink-wash, evening-garden, data-temple, superflat, neo-tokyo
- **All pages pull live Postgres data** — no stubs
- Skin switching via `?skin=neo-tokyo` on any page
- Navigation links between all pages

### Brain Layer (LIVE)
- 15 MCP tools via `mcp__brain__*`
- 49+ memories, 10 domains, 10 contexts, 98 profile traits
- Action extraction via Gemini Flash (needs paid tier — free quota exhausted)
- `jsonref` installed to fix instructor import chain

### Agent Scheduler (BUILT, not yet run live)
- `promaia/agents/scheduler.py` — full asyncio daemon with PID management
- 3 agents configured in `promaia.config.json`:
  - `morning-briefing` (daily) — calendar, priority emails, brain state
  - `email-triage` (every 2hr) — classify and surface attention items
  - `evening-digest` (daily) — day recap, momentum, suggestions
- Prompt files exist: `prompts/agent_*.md`
- **Brain context now injected** — agents see pending actions, project states, recent memories
- Brain MCP server registered in `mcp_servers.json`
- SDK mode fails inside Claude Code (CLAUDECODE env var) — run as standalone daemon

### Gmail Pipeline (BUILT)
- `promaia/brain/gmail_ingest.py` — syncs Gmail → gmail_content table
- `gmail_query` MCP tool (#15) in brain server
- Run: `python -m promaia.brain.gmail_ingest --account zachary4rivers`

### Patches (EXPORTED)
- 68 patches in `zbrain-patches/` — safety net before Josie/Rose re-init

## 10 Projects (corrected 2026-03-08)

| P | Project | Status | What |
|---|---------|--------|------|
| 1 | zBrain | Active | Zack's Promaia instance. Brain layer, dashboard, agents. |
| 2 | Promaia | Active | Josie's platform. Zack is dad-contributor, guinea pig, cherry-pick features. |
| 2 | Personal | Waiting | 2nd brain: thoughts, life, health, time, money. Open Claw-style. Most curious about. |
| 3 | Heatpup | Resting | THE big project. 775 commits. Paused for better tools. |
| 4 | HVAC Leads | Concept | Portland HVAC specialist marketing. Generate own leads. |
| 5 | PURRfoot | Research | Cat-themed product line. MaybeCat + Hopecookie are marketing arms. |
| 5 | MaybeCat | Concept | Viral marketing site for PURRfoot. |
| 5 | Hopecookie | Concept | Cat-shaped fortune cookie for coffee/tea. MaybeCat as literal cookie. |
| 6 | Catpool | Concept | NOT standalone. Shared answer repo between MaybeCat & Hopecookie. |
| 7 | PetalPolicy | Concept | Flower subscriptions as relationship insurance. |

## Next Session: What to Do

### 1. Agent Scheduler — First Real Run
- Start daemon: `python -m promaia.agents.scheduler` (outside Claude Code)
- Or single agent test: executor has `execute_agent_sync()`
- Watch for: SDK availability, MCP server resolution, Notion output
- Key file: `promaia/agents/executor.py` (1616L) — dual-mode SDK + legacy

### 2. Personal Domain — Start Using It
- This is what Zack is most curious about
- The brain has 98 profile traits — start using them for proactive suggestions
- Health, finances, time, life management
- Open question: how aggressive/autonomous should it be?

### 3. Deploy for iPhone
- FastAPI server needs external hosting for mobile access
- Options: Render, Railway, VPS, ngrok for testing
- All 6 skins are mobile-responsive

### 4. Remaining
- Gemini routing (Phase 3 — model router)
- Fix Anthropic chat bug in utils/ai.py
- Gemini free tier → paid tier for action extraction

## Architecture Reference

```
Figma/Canva → Skin CSS → Jinja2 templates → FastAPI → User (phone/desktop)
                                                |
Agents → Postgres (brain.*) + Notion (workspace) → dashboard.py reads & renders
           |
           +→ brain.memories, brain.actions, brain.contexts, brain.profile
           +→ gmail_content (email pipeline)
```

## Key Files

| File | What |
|------|------|
| `promaia/web/main.py` | FastAPI app, all routers registered |
| `promaia/web/routers/dashboard.py` | All 5 page routes + live DB queries |
| `promaia/web/templates/*.html` | 5 Jinja2 templates |
| `promaia/web/static/skins/*.css` | 6 CSS skin files |
| `promaia/brain/mcp_server.py` | 15 brain MCP tools |
| `promaia/brain/gmail_ingest.py` | Gmail sync pipeline |
| `promaia/agents/scheduler.py` | Daemon scheduler |
| `promaia/agents/executor.py` | Agent execution (SDK + legacy + brain context) |
| `promaia.config.json` | 3 agent configs |
| `mcp_servers.json` | Brain MCP server registered |
| `.planning/ROADMAP.md` | Phase tracker |

## Git State

- Branch: `zbrain` (off `feature/agent-scheduler`)
- Working tree: clean
- Latest: `a5f92fe` feat(agents): wire brain context into agent executor
- Patches: 68 exported to `zbrain-patches/`

## Known Issues

- Gemini 2.0 Flash free tier quota exhausted — action auto-extraction returns empty
- SDK mode fails inside Claude Code (CLAUDECODE env var blocks it)
- gmail_content table has 0 rows until ingest is run

## Notion Page IDs (agent backend)
- Root: 31b72180-6675-8039-a701-f51c6423f11e
- Brain Dashboard: 31b72180-6675-8175-bd07-cfd6adf48f40
- Projects: 31b72180-6675-8171-ac01-cddba216788b
- Email Triage: 31b72180-6675-81ab-9da5-cbc2aabea6a0
- Profile: 31b72180-6675-8195-b4bf-c39367cb4525
