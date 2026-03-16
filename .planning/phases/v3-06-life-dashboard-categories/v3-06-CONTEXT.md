# v3.0 Plan 6: Life Dashboard Categories

## Goal
Dashboard becomes a life command center with category tabs (All | Projects | Health | Finance | Email), interactive elements, and drill-down project views.

## Depends On
- Phase 9 (Proactive Push) — complete
- v3.0 Quick Wins — dashboard nav, health indicator, notification badge all exist

## What Already Exists
- `promaia/web/routers/dashboard.py` — 5 routes, queries libSQL/MuninnDB directly
- `promaia/web/templates/` — base.html, dashboard.html, projects.html, email.html, profile.html
- `promaia/web/static/skins/superflat.css` — CSS custom properties design system
- Brain schema: brain.memories, brain.actions, brain.contexts (projects), brain.domains, brain.profile
- 10 life domains in brain.domains
- Notification badge with 60s polling
- Nav bar with active page highlighting

## What Needs Building
1. Category tab system (All | Projects | Health | Finance | Email) with client-side JS filtering
2. Enhanced project cards with status indicators + drill-down `/projects/<slug>`
3. Health domain: new brain.health_metrics table, metric cards (sleep/exercise/stress/energy), quick-log form
4. Finance domain: new brain.finance_entries table, subscription tracker, agent cost summary
5. Interactive elements: action completion checkboxes, quick capture bar, project status updates
6. New API endpoints: /api/capture, /api/actions/<id>/complete, /api/dashboard/category/<name>, /api/health/log, /api/finance/log

## Design Constraints
- Superflat CSS custom properties only
- Responsive (phone-accessible)
- Vanilla JS (no frameworks)
- Readability first

## Requirements Traced
- From v3.0 Plan 6: category tabs, interactive dashboard, health/finance domains
