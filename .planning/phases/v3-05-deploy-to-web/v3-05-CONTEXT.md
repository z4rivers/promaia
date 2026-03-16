# v3.0 Plan 5: Deploy to Web

## Goal
Dashboard and brain API accessible from anywhere — phone, other devices — not just localhost. Protected by authentication. Survives PC being off.

## Depends On
- Phase 9 (Proactive Push) — complete
- v3.0 Quick Wins (Plans 0.5a-4) — shipped: auth middleware, config, Procfile, Procfile / Railway config, webhook support all exist

## What Already Exists
- `promaia/web/auth.py` — HMAC session cookies, Bearer token, opt-in via DASHBOARD_PASSWORD
- `promaia/web/config.py` — HOST, PORT, CORS_ORIGINS, TELEGRAM_WEBHOOK_URL from env
- `promaia/web/templates/login.html` — login page matching Superflat skin
- `Procfile` — `web: python -m promaia dev`
- `Procfile / Railway config` — Railway blueprint with all env var declarations
- `runtime.txt` — python-3.12.8
- `.env.example` — all env vars documented

## What Remains
1. Fix deployment blockers in requirements.txt (uvloop is Linux-only, needs conditional or removal)
2. Push zbrain branch to GitHub (not currently on remote)
3. Deploy to hosting platform (Railway recommended — Procfile / Railway config exists, $7/mo Starter for always-on)
4. Set env vars on hosting platform
5. Verify: dashboard loads from phone, Telegram webhook works, scheduler fires agents
6. Optional: custom domain

## Platform Decision
Railway Starter ($7/mo) — always-on, auto-deploy from GitHub, Procfile / Railway config blueprint ready.
Free tier sleeps after 15 min — breaks scheduler and Telegram bot. Must be paid.

## Requirements Traced
- From v3.0 Plan 5: accessible from phone, auth, cloud hosting, webhook mode
