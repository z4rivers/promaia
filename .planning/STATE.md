# State: zBrain

## Current Position

Phase: Phase 4 — Full Platform Activation + Dashboard Design
Plan: Web dashboard as primary display layer (not Notion)
Status: 4.1-4.6 activated. Design system approved. Research complete. Implementation next.
Last activity: 2026-03-07 — Design brainstorming session: 6-skin Japanese dashboard system

## Session 2026-03-07 Accomplishments

### Commits (4 — clean working tree)
- `f7032f3` fix(web): dotenv load order and google-genai Content types
- `42f7bae` feat(agents): add agent prompts and CLI prompt sync stub
- `5647089` docs(4.x): update roadmap and state for phases 4.1-4.6 completion
- `47696ff` docs(zbrain): add Notion API reference and working session notes

### Research Completed (5 agents)
1. **Gmail sync** — `gmail_content` table already exists in schema. GmailConnector ready. Need: ingest daemon (`promaia/agents/gmail_ingest.py`), query tool in brain MCP, wire to agents. 3 components.
2. **MCP router** — Router exists at `promaia/web/routers/mcp.py` (339L). 95% done. Need: fix broken `get_mcp_server_configs()` import, register router in main.py, add brain server to mcp_servers.json. 3 fixes.
3. **Traditional Japanese design** — Full brief at `zbrain/japanese-design-brief.md` (700L). Muji, Yanagi, Fukasawa, Noguchi, Snow Peak, Nendo principles mapped to digital dashboard.
4. **Web architecture exploration** — Confirmed: Promaia web server is a thin REST API for mobile access. Notion+CLI were primary. CORS hints at planned Vite frontend (`localhost:5174`, `koiib.com`). We're completing the frontend slot.
5. **Young Japanese design** — Brief at `zbrain/young-japanese-design-brief.md` (may still be writing). DJ culture, Superflat, teamLab, cyberpunk HUD, Persona 5 typography.

### Major Design Decision: The Verizon Pivot
**Notion is NOT the display layer.** Notion's visual branding overwhelms content (the "Verizon problem" — everything in a Verizon store looks like Verizon, not like the products). Web dashboard via FastAPI is the user-facing display. Notion stays as agent workspace/backend.

Architecture:
```
Figma/Canva (visual design) -> Skin CSS (design tokens) -> HTML/Jinja2 templates -> FastAPI renders -> User sees on phone
                                                                                          |
Agents write to: Postgres (data) + Notion (workspace/journals/prompts)                    |
                      |                                                                    |
                      +------ dashboard.py router reads Postgres, renders templates -------+
```

### 6-Skin Design System (APPROVED)

Traditional:
1. **Stone Garden** (Sekitei) — Muji. Fog/stone/water. Sora + Noto Sans. Spacious.
2. **Ink Wash** (Sumie) — Yanagi. Pure monochrome. IBM Plex Mono + Sans. Editorial tight.
3. **Evening Garden** (Yutei) — Nendo. Cream/amber/wisteria. DM Sans + Noto Serif. Warm.

Young:
4. **Data Temple** (Deta-dera) — Ryoji Ikeda. Black void + cyan accent. Geist Mono + Outfit. Dense terminal.
5. **Superflat** — Murakami/Persona 5. White/black/red/yellow. Bebas Neue + DM Sans. Bold confrontation.
6. **Neo-Tokyo** — Ghost in the Shell. Navy/cyan/magenta. Exo 2 + Inter. Glow effects, HUD.

### What Gets Built (Implementation Plan)

```
promaia/web/
  templates/           <- Jinja2 HTML (Figma-designed, 5 pages)
    base.html          <- Shell: loads skin CSS, nav, layout
    dashboard.html     <- Root: briefing + actions + pulse
    projects.html      <- Domain overview
    email.html         <- Inbox intelligence
    profile.html       <- Personal dashboard
  static/
    skins/             <- 6 CSS files (one per skin, ~60-80 lines each)
      stone_garden.css
      ink_wash.css
      evening_garden.css
      data_temple.css
      superflat.css
      neo_tokyo.css
    fonts/             <- Custom typography
  routers/
    dashboard.py       <- Routes: read Postgres -> render templates
```

## Next Session: What to Do

### Priority 1: Write Design Doc + Implementation Plan
- Consolidate both design briefs into `docs/plans/2026-03-07-dashboard-design.md`
- Create implementation plan (writing-plans skill)
- Commit design doc

### Priority 2: Build Dashboard (the main event)
- `base.html` template with skin-switching CSS variables
- `dashboard.py` router reading from Postgres (brain memories, actions, contexts)
- Stone Garden skin first (default), then all 6
- 5 page templates

### Priority 3: Gmail Ingest Pipeline
- `promaia/agents/gmail_ingest.py` — daemon syncing Gmail -> gmail_content table
- `query_gmail` tool in brain MCP server
- Wire agents to real email data

### Priority 4: MCP Router (3 quick fixes)
- Fix `get_mcp_server_configs()` import in mcp_servers.py
- Register MCP router in main.py
- Add brain server entry to mcp_servers.json

### Priority 5: Remaining items
- CLI stubs (team_commands, conversation_commands)
- Export patches: `git format-patch feature/agent-scheduler..zbrain -o zbrain-patches/`
- Deploy web server externally for phone access
- Fix Anthropic chat bug in utils/ai.py

## Notion Page IDs (still valid — Notion stays as agent backend)
- Root: 31b72180-6675-8039-a701-f51c6423f11e
- Brain Dashboard: 31b72180-6675-8175-bd07-cfd6adf48f40
- Projects: 31b72180-6675-8171-ac01-cddba216788b
- Email Triage: 31b72180-6675-81ab-9da5-cbc2aabea6a0
- Profile: 31b72180-6675-8195-b4bf-c39367cb4525

## Previous Session Context (2026-03-06)

Phases 4.1-4.6 activated in one session. See git log for details.
Key: SDK mode fails inside Claude Code (CLAUDECODE env var). Legacy mode works.

## Phase History

See git log. Phases 1-4.1 documented in previous STATE.md versions.

## Git State

- Branch: `zbrain` (off `feature/agent-scheduler`)
- Latest commits: `47696ff` (2026-03-07 session)
- Working tree: clean (only `.claude/settings.local.json` untracked)

## Blockers

None.

## Upcoming Events

- **Promaia re-init (within ~1 week):** Export patches before: `git format-patch feature/agent-scheduler..zbrain -o zbrain-patches/`
