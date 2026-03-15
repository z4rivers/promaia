# Brain Activity Indicator — Three-State Dashboard UX

**Date:** 2026-03-15
**Status:** Approved
**Scope:** Brain daemon activity tracking + dashboard indicator upgrade

## Problem

The dashboard has a binary connected/disconnected brain indicator. When the brain daemon is processing a tool call (capture, search, etc.), blocking sync operations starve the `/health` endpoint, causing the dashboard to show "disconnected" even though the brain is actively working. This is misleading and anxiety-inducing.

## Solution

### 1. Activity Tracking (mcp_server.py)

Add a process-level dict tracking in-flight tool calls:

```python
_active_tools: dict[str, float] = {}  # tool_name -> start_timestamp
_active_lock = asyncio.Lock()
```

Wrap `call_tool` dispatcher: add entry on tool start, remove on exit (success or error).

### 2. Unblock Health Endpoint

Wrap the heaviest synchronous operations with `asyncio.to_thread()`:
- `generate_embedding()` in capture_ops, profile_ops (500ms-2s)
- `extract_actions()`, `extract_insights()` in capture pipeline (2-15s Gemini API)
- `run_pc_scan()` in profile_ops (5-30s)
- `run_gmail_scan()` in gmail_ops (10-60s)

Replace `urllib.request.urlopen()` in context_ops with async `httpx.AsyncClient`.

Sync DB calls (<100ms) are left as-is — not worth the complexity.

### 3. Health Endpoint Response

```json
{
  "status": "ok",
  "service": "zbrain-brain",
  "active": true,
  "active_count": 1,
  "tools": ["capture"]
}
```

### 4. Dashboard Proxy (dashboard.py)

No change needed — already spreads extra keys via `**data`.

### 5. Dashboard UI (dashboard.html)

Three static states, no animations:

| State | Dot | Label |
|-------|-----|-------|
| Idle | `#4ade80` (green) | Brain: connected |
| Active | `#fbbf24` (amber) | Brain: active |
| Disconnected | `#f87171` (red) | Brain: disconnected |

All pulse animations removed. Subtle color shift only.

## Files Changed

| File | Change |
|------|--------|
| `promaia/brain/mcp_server.py` | Activity tracking + enriched health endpoint |
| `promaia/brain/mcp/handlers/capture_ops.py` | `to_thread` wrappers |
| `promaia/brain/mcp/handlers/context_ops.py` | async httpx replacement |
| `promaia/brain/mcp/handlers/profile_ops.py` | `to_thread` wrappers |
| `promaia/brain/mcp/handlers/gmail_ops.py` | `to_thread` wrappers |
| `promaia/web/templates/dashboard.html` | Three-state indicator, remove animations |

## Design Principles

- Soft, non-attention-grabbing indicator — no pulsing, no flashing
- Minimal change surface — enrich what exists rather than adding infrastructure
- Fix the root cause (event loop blocking) alongside the UX improvement
