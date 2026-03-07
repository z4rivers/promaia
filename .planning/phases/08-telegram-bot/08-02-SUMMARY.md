---
phase: 08-telegram-bot
plan: 02
subsystem: telegram
tags: [deepgram, voice-transcription, aiogram, telegram, event-channel, notification]

# Dependency graph
requires:
  - phase: 08-telegram-bot plan 01
    provides: "Core bot infrastructure, brain_ops, auth, formatting, command/message handlers"
  - phase: 07-event-bus
    provides: "NotificationChannel ABC, EventRouter, brain.events table"
provides:
  - "Voice note transcription via Deepgram Nova-3 with auto-capture to brain"
  - "TelegramChannel implementing NotificationChannel for interrupt/digest event delivery"
  - "Event router integration -- Telegram registered as push channel when configured"
affects: [09-proactive-push, telegram-voice]

# Tech tracking
tech-stack:
  added: [deepgram-sdk 6.0.1]
  patterns: [deepgram-nova3-async-transcription, notification-channel-pattern, graceful-env-var-degradation]

key-files:
  created:
    - promaia/telegram/handlers/voice.py
    - promaia/telegram/channel.py
  modified:
    - promaia/telegram/bot.py
    - promaia/events/router.py

key-decisions:
  - "Deepgram Nova-3 for voice transcription (OGG Opus native, no conversion needed)"
  - "TelegramChannel creates its own Bot instance (decoupled from main bot process for scheduler use)"
  - "Event router conditionally registers TelegramChannel only when both TELEGRAM_BOT_TOKEN and TELEGRAM_WHITELIST are set"
  - "First whitelisted chat ID used as push target for event delivery"
  - "Voice router registered between commands and messages (prevents catch-all interception)"

patterns-established:
  - "Separate Bot instance per process: polling bot vs sending-only channel bot can share token"
  - "Graceful degradation on missing API keys: user-friendly message instead of crash"

requirements-completed: [TELE-06, TELE-07]

# Metrics
duration: 8min
completed: 2026-03-07
---

# Phase 8 Plan 2: Voice + Event Channel Summary

**Deepgram Nova-3 voice transcription with auto-capture, and TelegramChannel for interrupt/digest event delivery from the event bus**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-07T09:20:00Z
- **Completed:** 2026-03-07T09:28:00Z
- **Tasks:** 2 (1 auto + 1 human-verify)
- **Files created:** 2
- **Files modified:** 2

## Accomplishments
- Voice note transcription pipeline: download OGG from Telegram, transcribe via Deepgram Nova-3, show transcription, auto-capture to brain
- TelegramChannel implementing NotificationChannel ABC for delivering interrupt and digest events from the event bus to Telegram
- Event router conditionally registers TelegramChannel when env vars are present, with graceful degradation
- Human-verified complete Telegram bot: all text commands, free-text capture, and voice transcription confirmed working from phone

## Task Commits

Each task was committed atomically:

1. **Task 1: Voice handler + TelegramChannel + event router integration** - `4e3b59f` (feat)
2. **Task 2: Human verification of complete Telegram bot** - N/A (checkpoint: approved by user)

## Files Created/Modified
- `promaia/telegram/handlers/voice.py` - Voice note download, Deepgram Nova-3 transcription, auto-capture pipeline
- `promaia/telegram/channel.py` - TelegramChannel implementing NotificationChannel ABC for event delivery
- `promaia/telegram/bot.py` - Added voice.router registration between commands and messages
- `promaia/events/router.py` - Conditional TelegramChannel registration when env vars present

## Decisions Made
- Deepgram Nova-3 selected for STT (accepts OGG Opus natively, no audio conversion needed)
- TelegramChannel creates its own Bot instance internally, decoupled from the polling bot process (scheduler runs separately)
- First whitelisted chat ID used as the push target for event delivery
- Voice router registered between commands.router and messages.router to prevent catch-all interception
- Graceful degradation: missing DEEPGRAM_API_KEY returns user-friendly message, missing Telegram env vars skip channel registration

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required

**External services require manual configuration:**
- `DEEPGRAM_API_KEY` - Deepgram Console -> Settings -> API Keys (https://console.deepgram.com/) -- $200 free credits, no CC needed
- `pip install deepgram-sdk==6.0.1` if not already installed

Both the `TELEGRAM_BOT_TOKEN` and `TELEGRAM_WHITELIST` env vars (from Plan 01) plus `DEEPGRAM_API_KEY` must be set in `.env` for full functionality.

## Next Phase Readiness
- Phase 8 complete: full Telegram bot with text commands, free-text capture, voice transcription, and event channel
- Ready for Phase 9 (Proactive Push): TelegramChannel is registered in the event router, so agents can push interrupt/digest events to Telegram
- All 8 TELE requirements satisfied across Plans 01 and 02

## Self-Check: PASSED

All files verified present. Commit `4e3b59f` confirmed in git log.

---
*Phase: 08-telegram-bot*
*Completed: 2026-03-07*
