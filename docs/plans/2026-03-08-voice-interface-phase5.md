# Phase 5: Hands-Free Voice Interface — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A web page on Zack's phone where he taps a mic button, talks to Promaia hands-free, and hears the response read back — with full brain context, conversation persistence, and session synthesis.

**Architecture:** New `/talk` route serving `talk.html` (extends base.html, same skin system). New `/api/brain/chat` and `/api/brain/transcribe` endpoints that wire into the existing conversation engine (`telegram/conversation.py`). Browser-side Web Audio API for recording, Web Speech API for TTS. PWA manifest so it installs as a home screen app.

**Tech Stack:** FastAPI, Jinja2, Gemini 3 Flash (conversation + transcription), Web Audio API, Web Speech API, existing brain Postgres schema, existing conversation.py engine.

---

### Task 1: Adapt conversation engine for web use

The conversation engine (`promaia/telegram/conversation.py`) currently takes a Telegram `chat_id` (integer). We need it to work with a web session identifier too.

**Files:**
- Modify: `promaia/telegram/conversation.py`
- Modify: `promaia/telegram/brain_ops.py`

**Step 1: Check brain_ops.py for chat_id usage**

Read `promaia/telegram/brain_ops.py` to understand how `chat_id` flows through `get_or_create_session`, `save_conversation_message`, `get_conversation_history`. The chat_id is used as a grouping key — we need it to accept a string identifier (like `"web-zack"`) in addition to Telegram integer IDs.

**Step 2: Update brain_ops to accept string-or-int chat_id**

In `brain_ops.py`, change `chat_id` parameter types from `int` to `int | str`. The Postgres column is likely `bigint` — if so, we use a hash or a dedicated web user ID. Alternatively, if the column is already text-compatible, just pass a string.

The simplest approach: use Zack's Telegram chat_id (`6269250506`) for web conversations too, so all context is shared. This means web and Telegram conversations share history — which is correct, it's one brain.

**Step 3: Create a thin wrapper for web callers**

Create `promaia/web/brain_chat.py`:

```python
"""
Thin adapter: web endpoints -> conversation engine.

Uses the same conversation.py that powers Telegram.
Web sessions use the whitelisted Telegram chat_id so all
conversations (web + Telegram) share context.
"""
import os
import logging
from promaia.telegram.conversation import generate_response, reset_synthesis_timer

logger = logging.getLogger(__name__)

# Web conversations use the same identity as Telegram
WEB_CHAT_ID = int(os.environ.get("TELEGRAM_WHITELIST", "6269250506"))


async def chat(message: str) -> str:
    """Send a message to the brain and get a response."""
    response = await generate_response(WEB_CHAT_ID, message)
    await reset_synthesis_timer(WEB_CHAT_ID)
    return response


async def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
    """Transcribe audio bytes via Gemini."""
    from google import genai
    from google.genai import types
    from promaia.ai.models import GOOGLE_MODELS

    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    response = await client.aio.models.generate_content(
        model=GOOGLE_MODELS["flash"],
        contents=[
            types.Content(parts=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                types.Part(text="Transcribe this voice note exactly. Return only the transcription, no commentary."),
            ])
        ],
        config=types.GenerateContentConfig(temperature=0.0),
    )
    if response.candidates and response.candidates[0].content.parts:
        return response.text.strip()
    return ""
```

**Step 4: Commit**

```bash
git add promaia/web/brain_chat.py
git commit -m "feat(phase5): web brain chat adapter — shares context with Telegram"
```

---

### Task 2: Create API endpoints for brain chat and voice

**Files:**
- Create: `promaia/web/routers/brain.py`
- Modify: `promaia/web/main.py` (register router)

**Step 1: Create the brain router**

Create `promaia/web/routers/brain.py`:

```python
"""
Brain chat + voice API endpoints for the web interface.

POST /api/brain/chat     — text message in, response out
POST /api/brain/voice    — audio blob in, transcription + response out
POST /api/brain/tts      — text in, audio out (Gemini TTS)
"""
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from promaia.web.brain_chat import chat, transcribe_audio

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    transcript: str | None = None


@router.post("/chat", response_model=ChatResponse)
async def brain_chat(req: ChatRequest):
    """Send a text message, get a brain-powered response."""
    try:
        reply = await chat(req.message)
        return ChatResponse(reply=reply)
    except Exception as e:
        logger.error(f"Brain chat failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Brain unavailable")


@router.post("/voice", response_model=ChatResponse)
async def brain_voice(audio: UploadFile = File(...)):
    """Send recorded audio, get transcription + brain response."""
    audio_bytes = await audio.read()
    if len(audio_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio too large (max 10MB)")

    mime = audio.content_type or "audio/webm"

    # Transcribe
    transcript = await transcribe_audio(audio_bytes, mime)
    if not transcript:
        raise HTTPException(status_code=422, detail="Could not transcribe audio")

    # Generate response from transcript
    reply = await chat(transcript)
    return ChatResponse(reply=reply, transcript=transcript)
```

**Step 2: Register in main.py**

In `promaia/web/main.py`, after the existing router includes, add:

```python
from promaia.web.routers import brain as brain_router
app.include_router(brain_router.router, prefix="/api/brain", tags=["Brain"])
```

**Step 3: Commit**

```bash
git add promaia/web/routers/brain.py promaia/web/main.py
git commit -m "feat(phase5): brain chat + voice API endpoints"
```

---

### Task 3: Create the Talk page template

**Files:**
- Create: `promaia/web/templates/talk.html`
- Modify: `promaia/web/routers/dashboard.py` (add /talk route)
- Modify: `promaia/web/templates/base.html` (add Talk to nav)

**Step 1: Create talk.html**

Extends base.html. Design principles:
- Single giant mic button, center of screen (thumb-reachable on phone)
- Message area scrolls up as conversation grows
- Text input at bottom as fallback
- Status indicator: "Listening...", "Thinking...", "Speaking..."
- Uses all CSS custom properties from skin system

```html
{% extends "base.html" %}

{% block title %}Talk — Promaia{% endblock %}

{% block head %}
<style>
    .talk-container {
        display: flex;
        flex-direction: column;
        height: calc(100vh - 120px);
        max-width: 640px;
        margin: 0 auto;
    }

    .talk-messages {
        flex: 1;
        overflow-y: auto;
        padding: var(--space-md, 16px) 0;
        display: flex;
        flex-direction: column;
        gap: var(--space-sm, 8px);
    }

    .talk-msg {
        max-width: 85%;
        padding: var(--space-sm, 8px) var(--space-md, 16px);
        border-radius: 12px;
        font-size: 0.95rem;
        line-height: 1.5;
        word-wrap: break-word;
    }

    .talk-msg--user {
        align-self: flex-end;
        background: var(--accent-primary, #E63946);
        color: #fff;
    }

    .talk-msg--assistant {
        align-self: flex-start;
        background: var(--bg-card, #fff);
        color: var(--text-primary, #2C2C2C);
        border: 1px solid var(--border-subtle, #e0ddd5);
    }

    .talk-msg--status {
        align-self: center;
        font-family: var(--font-mono, 'JetBrains Mono', monospace);
        font-size: 0.75rem;
        color: var(--text-muted, #999);
    }

    .talk-controls {
        padding: var(--space-md, 16px) 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: var(--space-md, 16px);
    }

    .mic-btn {
        width: 80px;
        height: 80px;
        border-radius: 50%;
        border: 3px solid var(--accent-primary, #E63946);
        background: transparent;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 200ms ease;
        position: relative;
    }

    .mic-btn:hover { background: var(--accent-primary, #E63946); }
    .mic-btn:hover .mic-icon { fill: #fff; }

    .mic-btn.recording {
        background: var(--accent-primary, #E63946);
        animation: pulse 1.5s ease-in-out infinite;
    }
    .mic-btn.recording .mic-icon { fill: #fff; }

    @keyframes pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(230, 57, 70, 0.4); }
        50% { box-shadow: 0 0 0 20px rgba(230, 57, 70, 0); }
    }

    .mic-icon {
        width: 32px;
        height: 32px;
        fill: var(--accent-primary, #E63946);
        transition: fill 200ms ease;
    }

    .talk-text-input {
        display: flex;
        gap: var(--space-sm, 8px);
        width: 100%;
        max-width: 640px;
    }

    .talk-text-input input {
        flex: 1;
        padding: 10px 16px;
        border: 1px solid var(--border-subtle, #e0ddd5);
        border-radius: 8px;
        background: var(--bg-card, #fff);
        color: var(--text-primary, #2C2C2C);
        font-family: var(--font-body, sans-serif);
        font-size: 0.9rem;
        outline: none;
    }

    .talk-text-input input:focus {
        border-color: var(--accent-primary, #E63946);
    }

    .talk-text-input button {
        padding: 10px 20px;
        border: 2px solid var(--accent-primary, #E63946);
        border-radius: 8px;
        background: var(--accent-primary, #E63946);
        color: #fff;
        font-family: var(--font-body, sans-serif);
        font-weight: 600;
        cursor: pointer;
    }

    .talk-status {
        font-family: var(--font-mono, 'JetBrains Mono', monospace);
        font-size: 0.75rem;
        color: var(--text-muted, #999);
        min-height: 1.2em;
    }
</style>
{% endblock %}

{% block content %}
<div class="talk-container">
    <div class="talk-messages" id="messages">
        <!-- Messages appear here -->
    </div>

    <div class="talk-controls">
        <div class="talk-status" id="status"></div>

        <button class="mic-btn" id="mic-btn" title="Hold to talk">
            <svg class="mic-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
            </svg>
        </button>

        <div class="talk-text-input">
            <input type="text" id="text-input" placeholder="Or type here..." autocomplete="off">
            <button id="send-btn">Send</button>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script src="/static/js/talk.js"></script>
{% endblock %}
```

**Step 2: Add /talk route to dashboard.py**

Add to `promaia/web/routers/dashboard.py`:

```python
@router.get("/talk", response_class=HTMLResponse)
async def talk_page(request: Request):
    return templates.TemplateResponse("talk.html", {
        "request": request,
        "skin": SKIN,
        "active_page": "talk",
    })
```

**Step 3: Add Talk link to base.html nav**

In `base.html`, inside `.top-nav__links`, add before Projects:

```html
<a href="/talk" class="{% if active_page == 'talk' %}active{% endif %}">Talk</a>
```

**Step 4: Commit**

```bash
git add promaia/web/templates/talk.html promaia/web/routers/dashboard.py promaia/web/templates/base.html
git commit -m "feat(phase5): Talk page — mic button, message area, text fallback"
```

---

### Task 4: Create the Talk page JavaScript

**Files:**
- Create: `promaia/web/static/js/talk.js`

This handles: mic recording (Web Audio API → MediaRecorder), sending audio to `/api/brain/voice`, sending text to `/api/brain/chat`, displaying messages, TTS playback (Web Speech API), and status updates.

```javascript
(function() {
    const messagesEl = document.getElementById('messages');
    const micBtn = document.getElementById('mic-btn');
    const statusEl = document.getElementById('status');
    const textInput = document.getElementById('text-input');
    const sendBtn = document.getElementById('send-btn');

    let mediaRecorder = null;
    let audioChunks = [];
    let isRecording = false;

    // --- Messages ---
    function addMessage(text, role) {
        const div = document.createElement('div');
        div.className = 'talk-msg talk-msg--' + role;
        div.textContent = text;
        messagesEl.appendChild(div);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function setStatus(text) {
        statusEl.textContent = text;
    }

    // --- TTS ---
    function speak(text) {
        if (!('speechSynthesis' in window)) return;
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        // Pick a natural voice if available
        const voices = window.speechSynthesis.getVoices();
        const preferred = voices.find(v => v.name.includes('Samantha') || v.name.includes('Google') || v.name.includes('Natural'));
        if (preferred) utterance.voice = preferred;
        window.speechSynthesis.speak(utterance);
    }

    // --- Text send ---
    async function sendText(message) {
        if (!message.trim()) return;
        addMessage(message, 'user');
        textInput.value = '';
        setStatus('Thinking...');

        try {
            const res = await fetch('/api/brain/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: message }),
            });
            const data = await res.json();
            if (data.reply) {
                addMessage(data.reply, 'assistant');
                speak(data.reply);
            }
        } catch (e) {
            addMessage('Connection error. Try again.', 'status');
        }
        setStatus('');
    }

    sendBtn.addEventListener('click', () => sendText(textInput.value));
    textInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') sendText(textInput.value);
    });

    // --- Voice recording ---
    async function startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
            audioChunks = [];

            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) audioChunks.push(e.data);
            };

            mediaRecorder.onstop = async () => {
                stream.getTracks().forEach(t => t.stop());
                const blob = new Blob(audioChunks, { type: 'audio/webm' });
                await sendVoice(blob);
            };

            mediaRecorder.start();
            isRecording = true;
            micBtn.classList.add('recording');
            setStatus('Listening...');
        } catch (e) {
            setStatus('Mic access denied');
        }
    }

    function stopRecording() {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
            isRecording = false;
            micBtn.classList.remove('recording');
            setStatus('Processing...');
        }
    }

    async function sendVoice(blob) {
        setStatus('Transcribing...');
        const form = new FormData();
        form.append('audio', blob, 'voice.webm');

        try {
            const res = await fetch('/api/brain/voice', {
                method: 'POST',
                body: form,
            });
            const data = await res.json();
            if (data.transcript) {
                addMessage(data.transcript, 'user');
            }
            if (data.reply) {
                setStatus('');
                addMessage(data.reply, 'assistant');
                speak(data.reply);
            }
        } catch (e) {
            addMessage('Voice processing failed. Try again.', 'status');
        }
        setStatus('');
    }

    // Tap to start, tap to stop
    micBtn.addEventListener('click', () => {
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    });

    // Preload voices for TTS
    if ('speechSynthesis' in window) {
        window.speechSynthesis.getVoices();
    }
})();
```

**Step 5: Commit**

```bash
git add promaia/web/static/js/talk.js
git commit -m "feat(phase5): talk.js — voice recording, text chat, TTS playback"
```

---

### Task 5: PWA manifest for home screen install

**Files:**
- Create: `promaia/web/static/manifest.json`
- Create: `promaia/web/static/sw.js`
- Modify: `promaia/web/templates/base.html` (link manifest + meta tags)

**Step 1: Create manifest.json**

```json
{
    "name": "Promaia",
    "short_name": "Promaia",
    "description": "Your second brain",
    "start_url": "/talk",
    "display": "standalone",
    "background_color": "#F4F0E8",
    "theme_color": "#E63946",
    "icons": [
        {
            "src": "/static/icon-192.png",
            "sizes": "192x192",
            "type": "image/png"
        },
        {
            "src": "/static/icon-512.png",
            "sizes": "512x512",
            "type": "image/png"
        }
    ]
}
```

**Step 2: Create minimal service worker**

```javascript
// Minimal service worker for PWA installability
self.addEventListener('install', (e) => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', (e) => e.respondWith(fetch(e.request)));
```

**Step 3: Add to base.html head**

```html
<link rel="manifest" href="/static/manifest.json">
<meta name="theme-color" content="#E63946">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<script>if('serviceWorker' in navigator) navigator.serviceWorker.register('/static/sw.js');</script>
```

**Step 4: Generate placeholder icons**

We need 192x192 and 512x512 PNG icons. For now, create simple colored squares with "P" — replace with real branding later.

**Step 5: Commit**

```bash
git add promaia/web/static/manifest.json promaia/web/static/sw.js promaia/web/templates/base.html
git commit -m "feat(phase5): PWA manifest — installable on phone home screen"
```

---

### Task 6: Integration test — end to end

**Steps:**
1. Start local: `python -m promaia dev`
2. Open `http://localhost:8000/talk` in browser
3. Verify: page loads with skin, nav shows Talk as active
4. Type a message → verify brain response appears
5. Click mic → speak → click mic → verify transcription + response
6. Verify TTS reads response aloud
7. Open on phone (via local network IP) → verify responsive layout
8. Verify conversation appears in `brain.conversation_messages` table
9. Push to Railway, verify at production URL

**Step 8: Commit all fixes from testing**

```bash
git commit -m "fix(phase5): integration test fixes"
```

---

## Execution Summary

| Task | What | Effort |
|------|------|--------|
| 1 | Web brain chat adapter | 10 min |
| 2 | API endpoints (chat + voice) | 15 min |
| 3 | Talk page template | 15 min |
| 4 | Talk.js (recording, chat, TTS) | 20 min |
| 5 | PWA manifest | 10 min |
| 6 | Integration test | 15 min |

**Total: ~90 minutes**

All backend pieces exist. This is mostly wiring + frontend.
