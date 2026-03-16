# Phase 8: Telegram Bot - Research

**Researched:** 2026-03-07
**Domain:** Telegram Bot API, Speech-to-Text, Event-Driven Notification Channels
**Confidence:** HIGH

## Summary

Phase 8 connects Zack's brain to his phone via Telegram. The bot handles three distinct flows: (1) inbound text and commands that call brain tools directly via libSQL/MuninnDB, (2) inbound voice notes transcribed via Deepgram Nova-3 then processed as text, and (3) outbound event delivery by implementing the `NotificationChannel` ABC from Phase 7's event bus. The codebase is perfectly staged for this -- the channel abstraction, event router, and rate limiter are all in place.

The recommended stack is **aiogram 3.26.0** for the bot framework (fully async, matches the project's asyncio architecture) and **deepgram-sdk 6.0.1** for voice transcription ($0.0043/min pre-recorded, well within budget). The bot does NOT need an LLM for most commands -- `/briefing`, `/search`, `/capture`, `/projects`, `/actions` all map directly to existing brain libSQL/MuninnDB queries in `mcp_server.py`. Free-text messages are the one case where domain detection uses Gemini Flash (already wired in `extraction.py`).

**Primary recommendation:** Build the bot as a standalone daemon process (`promaia/telegram/bot.py`) that reuses brain libSQL/MuninnDB functions directly -- do NOT route through MCP protocol. Register `TelegramChannel` in the event router to receive interrupt/digest events. Use aiogram's built-in polling with backoff for auto-reconnect (TELE-08).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None -- all implementation decisions deferred to Claude's discretion.

### Claude's Discretion
All implementation decisions are deferred to Claude's judgment for the initial build:
- Conversation style and response formatting for mobile
- Command behavior, verbosity, and confirmation flows
- Voice note transcription UX (show transcription, correction handling)
- Daemon architecture (service type, logging, health checks)
- Multi-turn context handling within chat sessions
- Error messaging and edge case handling

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TELE-01 | Telegram bot responds to text messages from whitelisted chat IDs | aiogram 3 message handler with chat ID filter; brain tool functions called directly via libSQL/MuninnDB |
| TELE-02 | Bot silently ignores messages from non-whitelisted users | aiogram middleware or filter that checks `message.chat.id` against whitelist; non-matching messages dropped silently |
| TELE-03 | /briefing command triggers and returns morning briefing content | Reuse `_handle_briefing()` logic from mcp_server.py, format for Telegram 4096-char limit |
| TELE-04 | /search, /capture, /projects, /actions commands work against brain | Reuse corresponding `_handle_*()` functions from mcp_server.py as direct libSQL/MuninnDB calls |
| TELE-05 | Free-text messages auto-captured to brain with domain detection | Call `_handle_capture()` logic with domain from `engine.detect_mode()` or keyword heuristics |
| TELE-06 | Voice notes transcribed via Deepgram Nova-3 and processed as text | Download OGG Opus via aiogram `bot.download_file()`, send bytes to `AsyncDeepgramClient.listen.v1.media.transcribe_file()`, process transcript as text |
| TELE-07 | Bot registered as event router channel -- interrupt events pushed within 30s | Implement `TelegramChannel(NotificationChannel)` with `deliver()` that calls `bot.send_message(chat_id, text)` |
| TELE-08 | Bot runs as persistent daemon with auto-reconnect | aiogram `Dispatcher.start_polling()` with `BackoffConfig`; PID file management pattern from existing scheduler |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aiogram | 3.26.0 | Telegram Bot API framework | Fully async (asyncio + aiohttp), native Python 3.10-3.14 support, auto-reconnect via BackoffConfig, 200+ typed API methods, Pydantic models |
| deepgram-sdk | 6.0.1 | Voice note transcription | AsyncDeepgramClient for non-blocking STT, Nova-3 model with 5.26% WER, $0.0043/min pre-recorded, Python 3.8-3.15 support |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| aiohttp | 3.11.18 | HTTP client (aiogram dependency) | Already in project deps -- aiogram uses it internally |
| python-dotenv | 1.0.1 | Environment variable loading | Already in project deps -- loads TELEGRAM_BOT_TOKEN and DEEPGRAM_API_KEY |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| aiogram | python-telegram-bot | Synchronous by default, would need threading workaround; aiogram is native async matching project architecture |
| aiogram | telethon | Designed for user accounts not bots; overkill for Bot API |
| deepgram-sdk | openai whisper | Requires local GPU or API ($0.006/min OpenAI); Deepgram is cheaper and faster for pre-recorded |
| deepgram-sdk | google-cloud-speech | Requires service account setup; Deepgram is simpler with just API key |

**Installation:**
```bash
pip install aiogram==3.26.0 deepgram-sdk==6.0.1
```

## Architecture Patterns

### Recommended Project Structure
```
promaia/
  telegram/
    __init__.py
    bot.py              # Main bot: Dispatcher, Router, handlers
    handlers/
      __init__.py
      commands.py       # /briefing, /search, /capture, /projects, /actions
      messages.py       # Free-text message handler (auto-capture)
      voice.py          # Voice note download + transcription
    channel.py          # TelegramChannel(NotificationChannel) for event bus
    auth.py             # Whitelist filter middleware
    brain_ops.py        # Thin wrappers around brain libSQL/MuninnDB operations
    formatting.py       # Telegram-safe message formatting (4096 char limit, markdown)
  telegram_cli.py       # CLI entrypoint: start/stop/status (mirrors scheduler_cli.py)
```

### Pattern 1: Direct Brain Access (NOT MCP Protocol)

**What:** The Telegram bot calls brain functions directly via libSQL/MuninnDB, NOT through the MCP server protocol. The MCP server is designed for Claude Code's stdio transport -- the Telegram bot should extract the shared logic into importable functions.

**When to use:** All brain operations (briefing, capture, search, actions, etc.)

**Example:**
```python
# promaia/telegram/brain_ops.py
# Reuse the same libSQL/MuninnDB queries from mcp_server.py
# but return plain strings instead of TextContent objects

from promaia.storage.postgres_db import get_postgres_db
from promaia.brain.extraction import extract_actions
from promaia.storage.vector_db import VectorDBManager

async def get_briefing() -> str:
    """Return briefing text -- same logic as mcp_server._handle_briefing()."""
    db = get_postgres_db()
    lines = ["Session Briefing\n"]
    # ... same SQL queries as _handle_briefing ...
    return "\n".join(lines)

async def capture_memory(content: str, domain: str | None = None) -> str:
    """Capture text to brain -- same logic as mcp_server._handle_capture()."""
    db = get_postgres_db()
    # ... same insert + embedding + action extraction ...
    return "Captured."

async def search_brain(query: str, limit: int = 5) -> str:
    """Semantic search -- same logic as mcp_server._handle_search()."""
    # ... pgvector search, format results ...
```

### Pattern 2: Whitelist Filter (TELE-01, TELE-02)

**What:** A middleware or filter that checks every incoming message against a set of allowed Telegram chat IDs. Non-whitelisted messages are silently dropped (no response, no error).

**When to use:** Every incoming update before any handler runs.

**Example:**
```python
# promaia/telegram/auth.py
import os
from aiogram import BaseMiddleware
from aiogram.types import Message

class WhitelistMiddleware(BaseMiddleware):
    """Drop messages from non-whitelisted chat IDs silently."""

    def __init__(self):
        # Load from env: TELEGRAM_WHITELIST=123456789,987654321
        raw = os.getenv("TELEGRAM_WHITELIST", "")
        self.allowed_ids: set[int] = {
            int(cid.strip()) for cid in raw.split(",") if cid.strip()
        }

    async def __call__(self, handler, event: Message, data: dict):
        if event.chat.id not in self.allowed_ids:
            return  # Silent drop -- TELE-02
        return await handler(event, data)
```

### Pattern 3: TelegramChannel for Event Bus (TELE-07)

**What:** Implement the `NotificationChannel` ABC from Phase 7's `events/channels.py` so the event router pushes interrupt events to Telegram within 30 seconds (the router's poll interval).

**When to use:** Event delivery -- the router calls `deliver()` on all registered channels.

**Example:**
```python
# promaia/telegram/channel.py
from promaia.events.channels import NotificationChannel
from aiogram import Bot

class TelegramChannel(NotificationChannel):
    """Push events to Telegram chat."""

    def __init__(self, bot: Bot, chat_id: int):
        self._bot = bot
        self._chat_id = chat_id

    @property
    def name(self) -> str:
        return "telegram"

    def supports_urgency(self, urgency: str) -> bool:
        # Telegram receives both interrupt (immediate) and digest (batched)
        return urgency in ("interrupt", "digest")

    async def deliver(self, event: dict) -> bool:
        """Send event summary to Telegram chat."""
        try:
            payload = event.get("payload", {})
            summary = payload.get("summary", "New notification") if isinstance(payload, dict) else str(payload)
            event_type = event.get("type", "notification")
            urgency = event.get("urgency", "")

            # Format based on urgency
            if urgency == "interrupt":
                text = f"URGENT: {summary}"
            else:
                text = f"{summary}"

            await self._bot.send_message(self._chat_id, text)

            # Mark as routed
            from promaia.storage.postgres_db import get_postgres_db
            db = get_postgres_db()
            db.execute(
                "UPDATE brain.events SET routed_at = NOW(), channel = 'telegram' WHERE id = %s",
                (event["id"],),
            )
            return True
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Telegram delivery failed: {e}")
            return False
```

### Pattern 4: Voice Note Pipeline (TELE-06)

**What:** Download Telegram voice note (OGG Opus), transcribe via Deepgram Nova-3, then process the transcript as a regular text message.

**When to use:** Any incoming `message.voice` update.

**Example:**
```python
# promaia/telegram/handlers/voice.py
import io
from aiogram import Router, Bot
from aiogram.types import Message
from deepgram import AsyncDeepgramClient

router = Router()

@router.message(lambda msg: msg.voice is not None)
async def handle_voice(message: Message, bot: Bot):
    """Download voice note, transcribe, process as text."""
    # 1. Download OGG file from Telegram
    file = await bot.get_file(message.voice.file_id)
    buffer = io.BytesIO()
    await bot.download_file(file.file_path, buffer)
    audio_bytes = buffer.getvalue()

    # 2. Transcribe via Deepgram Nova-3
    dg = AsyncDeepgramClient()  # Uses DEEPGRAM_API_KEY env var
    response = await dg.listen.v1.media.transcribe_file(
        request=audio_bytes,
        model="nova-3",
        smart_format=True,
    )
    transcript = response.results.channels[0].alternatives[0].transcript

    if not transcript:
        await message.reply("Could not transcribe the voice note.")
        return

    # 3. Show transcription, then process as text
    await message.reply(f"Heard: {transcript}")

    # 4. Auto-capture to brain
    from promaia.telegram.brain_ops import capture_memory
    result = await capture_memory(transcript)
    await message.reply(result)
```

### Pattern 5: Daemon with Auto-Reconnect (TELE-08)

**What:** Run the bot as a persistent process with PID file management and auto-reconnect on network failure. Mirrors the existing `scheduler.py` daemon pattern.

**When to use:** Production deployment.

**Example:**
```python
# promaia/telegram/bot.py
import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.utils.backoff import BackoffConfig
from promaia.telegram.auth import WhitelistMiddleware
from promaia.telegram.handlers import commands, messages, voice

async def start_bot():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    bot = Bot(token=token)
    dp = Dispatcher()

    # Register middleware
    dp.message.middleware(WhitelistMiddleware())

    # Include routers
    dp.include_router(commands.router)
    dp.include_router(voice.router)
    dp.include_router(messages.router)  # Must be last (catch-all)

    # Start polling with auto-reconnect
    await dp.start_polling(
        bot,
        backoff_config=BackoffConfig(
            min_delay=1.0,
            max_delay=30.0,  # Wait up to 30s between retries
            factor=1.5,
            jitter=0.1,
        ),
        polling_timeout=30,
    )
```

### Anti-Patterns to Avoid
- **Routing through MCP protocol:** The MCP server uses stdio transport for Claude Code. Don't start an MCP client inside the bot. Extract the shared libSQL/MuninnDB logic into importable functions.
- **Synchronous blocking calls:** The project is fully asyncio. Never use `requests` or synchronous DB calls in handlers. Use `aiohttp` (already a dep) and asyncio-compatible patterns.
- **Monolithic handler file:** Split handlers by concern (commands, voice, free-text). Order matters -- register catch-all free-text handler LAST so commands are matched first.
- **Exposing error details to user:** If brain operations fail, send a friendly "Something went wrong" rather than tracebacks. Log the real error server-side.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Telegram Bot API client | Custom HTTP client | aiogram 3 | 200+ typed methods, update parsing, middleware, filters |
| Long-polling with reconnect | Custom polling loop | aiogram Dispatcher.start_polling() | Built-in BackoffConfig with exponential backoff and jitter |
| Voice transcription | Local Whisper model | Deepgram Nova-3 API | Sub-second latency, no GPU needed, $0.0043/min |
| Message chunking for 4096 limit | Custom string splitting | Utility function with paragraph-aware splitting | Already have a pattern in discord_bot/bot.py `_split_message()` |
| OGG Opus handling | FFmpeg conversion | Direct API send to Deepgram | Deepgram accepts OGG Opus natively, no conversion needed |
| Whitelist auth | Custom per-handler checks | aiogram Middleware | Applied once, runs before all handlers |

**Key insight:** Deepgram accepts OGG Opus audio directly -- no need to convert Telegram's voice note format. This eliminates FFmpeg as a dependency entirely.

## Common Pitfalls

### Pitfall 1: Handler Registration Order
**What goes wrong:** Free-text message handler catches `/command` messages before command handlers.
**Why it happens:** aiogram routers process handlers in registration order. A catch-all `@router.message()` registered before command handlers will intercept everything.
**How to avoid:** Register command handlers FIRST (in a separate router), voice handler SECOND, free-text handler LAST. Use `dp.include_router()` order to control precedence.
**Warning signs:** Commands stop working but free-text capture still works.

### Pitfall 2: Telegram Message Length Limit
**What goes wrong:** Bot crashes or silently truncates when sending messages over 4096 characters.
**Why it happens:** Telegram enforces a 4096-character limit per message. Briefings and search results can easily exceed this.
**How to avoid:** Build a `send_long_message()` utility that splits at paragraph boundaries, falling back to sentence boundaries. Send chunks sequentially. Existing `_split_message()` from discord_bot.py can be adapted (change 2000 to 4096).
**Warning signs:** `aiogram.exceptions.TelegramBadRequest: Bad Request: message is too long`

### Pitfall 3: Voice Note File Size Limits
**What goes wrong:** Large voice notes fail to download or transcribe.
**Why it happens:** Telegram Bot API limits file downloads to 20MB. Voice notes of 5+ minutes can approach this. Deepgram also has its own limits.
**How to avoid:** Check `message.voice.file_size` before download. Reject voice notes over ~10MB with a friendly message. Typical voice notes at Telegram's codec are ~1KB/sec (a 10-minute note is ~600KB), so this is rarely an issue in practice.
**Warning signs:** `aiogram.exceptions.TelegramBadRequest: Bad Request: file is too big`

### Pitfall 4: Blocking the Event Loop with libSQL/MuninnDB
**What goes wrong:** Database queries block the asyncio event loop, making the bot unresponsive.
**Why it happens:** `psycopg2` is synchronous. The existing codebase uses it synchronously in the MCP server (acceptable because MCP is serial). But in the bot, multiple users or events may arrive concurrently.
**How to avoid:** Wrap libSQL/MuninnDB calls in `asyncio.to_thread()` or use `asyncio.get_event_loop().run_in_executor()`. Note: the existing codebase uses synchronous `get_postgres_db()` in agents too, and this works fine for a single-user bot. Only optimize if latency becomes noticeable.
**Warning signs:** Bot feels slow to respond, especially during libSQL/MuninnDB-heavy operations like search.

### Pitfall 5: DEEPGRAM_API_KEY Not Set
**What goes wrong:** Voice transcription fails silently or with unhelpful error.
**Why it happens:** `AsyncDeepgramClient()` reads from `DEEPGRAM_API_KEY` env var. If not set, transcription fails.
**How to avoid:** Check at bot startup that `DEEPGRAM_API_KEY` is set. Log a clear warning if missing. Degrade gracefully: "Voice transcription unavailable -- API key not configured."
**Warning signs:** Voice notes get downloaded but transcription returns empty or errors.

### Pitfall 6: Event Router Integration Timing
**What goes wrong:** TelegramChannel registered but bot not yet connected, so `deliver()` fails.
**Why it happens:** The event router starts in the agent scheduler process. The Telegram bot runs as a separate process. They need to share the bot instance or the TelegramChannel needs its own Bot instance.
**How to avoid:** Two approaches: (a) run bot and event router in the same asyncio event loop (simpler), or (b) TelegramChannel creates its own `Bot` instance using the same token (stateless -- just needs token to send messages). Approach (b) is simpler and decoupled.
**Warning signs:** Events marked as routed to "telegram" but no message appears in chat.

## Code Examples

### Complete Command Handler
```python
# promaia/telegram/handlers/commands.py
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from promaia.telegram.brain_ops import get_briefing, search_brain, capture_memory, get_actions, get_projects
from promaia.telegram.formatting import send_long_message

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply(
        "Brain connected. Commands:\n"
        "/briefing -- morning briefing\n"
        "/search <query> -- search memories\n"
        "/capture <text> -- capture a thought\n"
        "/projects -- project status\n"
        "/actions -- pending actions\n\n"
        "Or just send a message -- I'll capture it."
    )

@router.message(Command("briefing"))
async def cmd_briefing(message: Message):
    text = await get_briefing()
    await send_long_message(message, text)

@router.message(Command("search"))
async def cmd_search(message: Message):
    query = message.text.replace("/search", "", 1).strip()
    if not query:
        await message.reply("Usage: /search <query>")
        return
    results = await search_brain(query, limit=5)
    await send_long_message(message, results)

@router.message(Command("capture"))
async def cmd_capture(message: Message):
    content = message.text.replace("/capture", "", 1).strip()
    if not content:
        await message.reply("Usage: /capture <text to remember>")
        return
    result = await capture_memory(content)
    await message.reply(result)

@router.message(Command("projects"))
async def cmd_projects(message: Message):
    text = await get_projects()
    await send_long_message(message, text)

@router.message(Command("actions"))
async def cmd_actions(message: Message):
    text = await get_actions()
    await send_long_message(message, text)
```

### Message Formatting Utility
```python
# promaia/telegram/formatting.py
from aiogram.types import Message

MAX_LENGTH = 4096

async def send_long_message(message: Message, text: str):
    """Send a message, splitting into chunks if over Telegram's limit."""
    if len(text) <= MAX_LENGTH:
        await message.reply(text)
        return

    chunks = _split_message(text, MAX_LENGTH)
    for chunk in chunks:
        await message.reply(chunk)

def _split_message(text: str, max_length: int = 4096) -> list[str]:
    """Split text at paragraph boundaries, falling back to line boundaries."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    current = ""

    for paragraph in text.split("\n\n"):
        if len(current) + len(paragraph) + 2 <= max_length:
            current += paragraph + "\n\n"
        else:
            if current:
                chunks.append(current.strip())
            if len(paragraph) > max_length:
                # Split long paragraph by lines
                for line in paragraph.split("\n"):
                    if len(current) + len(line) + 1 <= max_length:
                        current += line + "\n"
                    else:
                        if current:
                            chunks.append(current.strip())
                        current = line + "\n"
            else:
                current = paragraph + "\n\n"

    if current.strip():
        chunks.append(current.strip())

    return chunks
```

### CLI Entrypoint (mirrors scheduler_cli.py)
```python
# promaia/telegram_cli.py
"""
Telegram bot CLI.

Usage:
    python -m promaia.telegram_cli start    # Start bot
    python -m promaia.telegram_cli stop     # Stop bot
    python -m promaia.telegram_cli status   # Check status
"""
import sys
import asyncio
from pathlib import Path

PID_FILE = Path.home() / ".promaia" / "telegram_bot.pid"

def cmd_start():
    from promaia.telegram.bot import start_bot
    # PID file management same as scheduler.py
    import os
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))
    try:
        asyncio.run(start_bot())
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| python-telegram-bot (sync) | aiogram 3.x (async) | aiogram 3.0 stable 2023 | Native asyncio, better performance for I/O-bound bots |
| OpenAI Whisper API ($0.006/min) | Deepgram Nova-3 ($0.0043/min) | Nova-3 launched 2025 | 28% cheaper, lower latency, better accuracy (5.26% WER) |
| Webhook-based bots | Long polling with backoff | aiogram 3.x default | Simpler deployment (no public URL needed), auto-reconnect |
| discord.py pattern (bot subclass) | aiogram pattern (dispatcher + routers) | aiogram 3.x | Cleaner separation of concerns, middleware chain |

**Deprecated/outdated:**
- aiogram 2.x: Significantly different API, not compatible with 3.x imports
- deepgram-sdk 3.x/4.x: Major API changes in 5.x/6.x, use `listen.v1.media` not old `transcription` namespace

## Open Questions

1. **Telegram Bot Token Creation**
   - What we know: Need a bot token from @BotFather on Telegram
   - What's unclear: Whether Zack has already created a bot
   - Recommendation: Add a setup step in plan wave 0 that checks for TELEGRAM_BOT_TOKEN in .env, with instructions for @BotFather if missing

2. **Deepgram API Key**
   - What we know: Deepgram offers $200 free credits, no credit card needed
   - What's unclear: Whether Zack has a Deepgram account
   - Recommendation: Include Deepgram signup as a prerequisite in wave 0; voice can be disabled gracefully if key is missing

3. **Bot Process vs Scheduler Process**
   - What we know: The agent scheduler already runs as a daemon with the event router. The bot needs to receive events AND process user messages.
   - What's unclear: Whether to run bot in the same process as the scheduler or separately
   - Recommendation: Run separately. The TelegramChannel in the event router can create its own `Bot(token)` instance to send messages. The user-facing bot runs its own polling loop. Two processes, same token, no conflict (Telegram allows multiple API calls with the same token; only one can poll for updates).

4. **Payload Parsing for Event Delivery**
   - What we know: Event payloads are JSONB with `summary`, `agent_name`, `execution_id` fields
   - What's unclear: Whether the current payload structure gives enough context for a useful Telegram notification
   - Recommendation: Start with the `summary` field (already capped at 500 chars by emitter.py). Refine formatting in Phase 9 when proactive push is built.

## Sources

### Primary (HIGH confidence)
- [aiogram PyPI](https://pypi.org/project/aiogram/) - Version 3.26.0, Python 3.10+ requirement
- [aiogram documentation](https://docs.aiogram.dev/en/latest/) - Router, Dispatcher, BackoffConfig, file download APIs
- [deepgram-sdk PyPI](https://pypi.org/project/deepgram-sdk/) - Version 6.0.1, Python 3.8+
- [Deepgram docs](https://developers.deepgram.com/docs/pre-recorded-audio) - transcribe_file() API, Nova-3 model
- [Deepgram pricing](https://deepgram.com/pricing) - $0.0043/min pre-recorded, $200 free credits

### Secondary (MEDIUM confidence)
- [aiogram GitHub](https://github.com/aiogram/aiogram) - Verified async architecture, aiohttp dependency
- [Telegram Bot API docs](https://core.telegram.org/bots/api) - Voice message format (OGG Opus), 20MB file limit, 4096 char message limit
- [Deepgram Nova-3 announcement](https://deepgram.com/learn/introducing-nova-3-speech-to-text-api) - 47.4% WER reduction, multilingual support

### Tertiary (LOW confidence)
- [aiogram vs python-telegram-bot comparison](https://www.restack.io/p/best-telegram-bot-frameworks-ai-answer-python-telegram-bot-vs-aiogram-cat-ai) - Qualitative comparison, no benchmarks

## Codebase Integration Points

These are the specific files and patterns the planner must account for:

| Integration Point | File | What Needs to Happen |
|-------------------|------|---------------------|
| Event channel registration | `promaia/events/router.py` line 30 | Add `TelegramChannel` to `self.channels` list |
| Channel ABC | `promaia/events/channels.py` | Import `NotificationChannel` base class |
| Brain operations | `promaia/brain/mcp_server.py` | Extract shared libSQL/MuninnDB query logic into importable functions |
| Domain detection | `promaia/brain/engine.py` | Use `detect_mode()` for free-text domain inference |
| Action extraction | `promaia/brain/extraction.py` | Reuse `extract_actions()` for captured text |
| Environment loading | `promaia/utils/config.py` | Add TELEGRAM_BOT_TOKEN, TELEGRAM_WHITELIST, DEEPGRAM_API_KEY to env loading |
| libSQL/MuninnDB connection | `promaia/storage/postgres_db.py` | Reuse `get_postgres_db()` -- already lazy-initialized singleton |
| Vector search | `promaia/storage/vector_db.py` | Reuse `VectorDBManager` for search command |
| PID file pattern | `promaia/agents/scheduler.py` | Reuse PID_FILE pattern for bot daemon management |
| Message splitting | `promaia/discord_bot/bot.py` line 317 | Adapt `_split_message()` pattern (change 2000 to 4096) |

## Environment Variables Required

| Variable | Purpose | Required? | Default |
|----------|---------|-----------|---------|
| TELEGRAM_BOT_TOKEN | Bot API token from @BotFather | Yes | None (bot won't start) |
| TELEGRAM_WHITELIST | Comma-separated allowed chat IDs | Yes | None (no messages processed) |
| DEEPGRAM_API_KEY | Deepgram API key for voice transcription | No | None (voice disabled gracefully) |

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - aiogram 3.26.0 and deepgram-sdk 6.0.1 both verified on PyPI with current versions and Python 3.14 support
- Architecture: HIGH - Event channel ABC, event router, and brain libSQL/MuninnDB functions all exist and are well-documented in the codebase
- Pitfalls: HIGH - Based on direct analysis of codebase patterns (sync libSQL/MuninnDB, handler ordering) and verified Telegram API limits (4096 chars, 20MB files)
- Integration points: HIGH - Every file and line number verified by reading actual source code

**Research date:** 2026-03-07
**Valid until:** 2026-04-07 (stable libraries, unlikely to change significantly)
