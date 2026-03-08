# Model & Version Update Plan

*Created: 2026-03-08*
*Status: READY TO EXECUTE*

## Available Current Models (from API listing 2026-03-08)

**Gemini:**
- `gemini-3.1-pro-preview` — top tier reasoning/audit
- `gemini-3-flash-preview` — cost-effective conversation/agents
- `gemini-3.1-flash-lite-preview` — cheapest extraction
- `gemini-2.5-pro` / `gemini-2.5-flash` — previous gen (GA, still valid)

**Claude (from system info):**
- `claude-opus-4-6` — top tier
- `claude-sonnet-4-6` — balanced
- `claude-haiku-4-5-20251001` — fast/cheap

**OpenAI:** Need to verify current model IDs via API check.

## Files to Update

### Group 1: Our Code (zBrain layer) — FIX NOW

| File | Line | Current | Update To | Notes |
|------|------|---------|-----------|-------|
| `ai/models.py` | 14 | `gemini-2.5-pro-preview-05-06` | `gemini-2.5-pro` | GA alias |
| `ai/models.py` | 15 | `gemini-2.5-flash-preview-05-20` | `gemini-2.5-flash` | GA alias |
| `ai/models.py` | 50-51 | display names for old preview IDs | match new IDs | |
| `telegram/handlers/voice.py` | 57 | `gemini-2.5-flash` | `gemini-3-flash-preview` | upgrade gen |
| `brain/mcp_server.py` | docstring | `"""Enumerate all 13 brain tools."""` | `16` | wrong count |

### Group 2: Josie's Platform Code — FIX (we maintain this fork)

| File | Line | Current | Update To |
|------|------|---------|-----------|
| `web/routers/nodes.py` | 180 | `gemini-1.5-pro-latest` | `gemini-3-flash-preview` |
| `scrubber.py` | 166 | `gpt-3.5-turbo-0125` | `gpt-4o-mini` |
| `mail/intent_detector.py` | 146 | `claude-3-5-haiku-20241022` | `claude-haiku-4-5-20251001` |
| `mail/intent_detector.py` | 153 | `gpt-4o-mini` | verify current |
| `mail/classifier.py` | 150 | `claude-sonnet-4-20250514` | `claude-sonnet-4-6` |
| `mail/response_generator.py` | 297,305,415 | `claude-sonnet-4-20250514` | `claude-sonnet-4-6` |
| `ai/nl_orchestrator.py` | 110 | `claude-sonnet-4-20250514` | `claude-sonnet-4-6` |
| `chat/interface.py` | 5607,8099 | `gemini-2.5-pro-short/long` | route through models.py |
| `chat/interface.py` | 501,728,730 | various Claude fallbacks | verify current |
| `agent/sdk_adapter.py` | 327 | `claude-sonnet-4-5-20250929` | `claude-sonnet-4-6` |
| `agent/agent_manager.py` | 60 | `claude-sonnet-4-5-20250929` | `claude-sonnet-4-6` |
| `agent/sdk_adapter_simple.py` | 87 | `claude-sonnet-4-5-20250929` | `claude-sonnet-4-6` |
| `agents/executor.py` | 1813 | `claude-sonnet-4-5-20250929` | `claude-sonnet-4-6` |
| `write/interface.py` | 473 | `claude-sonnet-4-5-20250929` | `claude-sonnet-4-6` |

### Group 3: Backup/Duplicate Files — DELETE

These are old copies with spaces in filenames. Not imported anywhere:
- `ai/nl_orchestrator 2.py`
- `chat/interface 2.py` (if exists as separate file)
- `write/interface 2.py`
- `write/interface 3.py`
- `mail/classifier 2.py`
- `mail/intent_detector 2.py`
- `mail/response_generator 2.py`
- `storage/vector_db 2.py`
- `utils/image_processing 2.py`
- `utils/image_processing 3.py`

### Group 4: Pricing Tables — VERIFY

| File | Current Pricing | Action |
|------|----------------|--------|
| `agents/model_router.py` | Flash $0.15/$0.60 per 1M | Verify against current Gemini pricing |
| `utils/ai.py` | gemini-3-flash, gemini-2.5-pro pricing | Verify and update |
| `telegram/conversation.py` | Flash $0.15/$0.60 per 1M | Verify |

### Group 5: ROADMAP Checkboxes — FIX

| File | Issue |
|------|-------|
| `ROADMAP.md` Phase 7 | Plans 07-01, 07-02, 07-03 checkboxes unchecked despite phase complete |

### Group 6: Skill & Plugin Version Audit

- Check GSD skill version (currently 4.3.1) against latest available
- Check superpowers skill versions
- Check Gemini MCP server/tools for updates
- Check any other installed skills for newer versions
- This is a NEW standing instruction: model-selection skill should audit skill/plugin versions alongside model IDs
- For any updated or new skills found: evaluate how they could benefit Promaia and include recommendations in the project brief (PROJECT.md)

## Execution Order

1. Delete backup files (Group 3) — clean the noise
2. Fix our code (Group 1) — safe, we own it
3. Fix platform code (Group 2) — systematic, file by file
4. Verify pricing (Group 4) — check Gemini pricing page
5. Fix ROADMAP (Group 5) — quick
6. Audit skill/plugin versions (Group 6) — check for updates
7. Run auditor again to confirm clean

## Change Log

| File | Old | New | Date |
|------|-----|-----|------|
| ai/models.py | gemini-2.5-pro-preview-05-06 | gemini-2.5-pro | 2026-03-07 |
| ai/models.py | gemini-2.5-flash-preview-05-20 | gemini-2.5-flash | 2026-03-07 |
| ai/models.py | display names for old IDs | matched new IDs | 2026-03-07 |
| telegram/handlers/voice.py | gemini-2.5-flash | gemini-3-flash-preview | 2026-03-07 |
| web/routers/nodes.py | gemini-1.5-pro-latest | gemini-3-flash-preview | 2026-03-07 |
| web/routers/nodes.py | gpt-3.5-turbo example | gpt-4o-mini | 2026-03-07 |
| scrubber.py | gpt-3.5-turbo-0125 | gpt-4o-mini | 2026-03-07 |
| mail/intent_detector.py | claude-3-5-haiku-20241022 | claude-haiku-4-5-20251001 | 2026-03-07 |
| mail/classifier.py | claude-sonnet-4-20250514 | claude-sonnet-4-6 | 2026-03-07 |
| mail/response_generator.py (x2) | claude-sonnet-4-20250514 | claude-sonnet-4-6 | 2026-03-07 |
| ai/nl_orchestrator.py | claude-sonnet-4-20250514 | claude-sonnet-4-6 | 2026-03-07 |
| agent/sdk_adapter.py | claude-sonnet-4-5-20250929 | claude-sonnet-4-6 | 2026-03-07 |
| agent/agent_manager.py | claude-sonnet-4-5-20250929 | claude-sonnet-4-6 | 2026-03-07 |
| agent/sdk_adapter_simple.py | claude-sonnet-4-5-20250929 | claude-sonnet-4-6 | 2026-03-07 |
| agents/executor.py | claude-sonnet-4-5-20250929 | claude-sonnet-4-6 | 2026-03-07 |
| write/interface.py | claude-sonnet-4-5-20250929 fallback | claude-sonnet-4-6 | 2026-03-07 |
| chat/interface.py (x3) | claude-sonnet-4-5/opus-4-5 fallbacks | claude-sonnet-4-6/opus-4-6 | 2026-03-07 |
| utils/ai.py | claude-sonnet-4-5-20250929 default | claude-sonnet-4-6 | 2026-03-07 |
| utils/ai.py | model_mapping missing new IDs | added 4.6 mappings | 2026-03-07 |
| ROADMAP.md | Phase 7 plans unchecked | checked [x] | 2026-03-07 |
| 52 backup files | " 2.py" / " 3.py" files | DELETED | 2026-03-07 |
| 5 custom skills | old format | writing-skills best practices | 2026-03-07 |
