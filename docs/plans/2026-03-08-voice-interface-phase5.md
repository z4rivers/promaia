# Phase 5: Hands-Free Voice Interface — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** A web page on Zack's phone where he taps a mic button ONCE, talks to Promaia hands-free while driving, and hears the response read back through car speakers — with full brain context, conversation persistence, continuous conversation loop, and robust handling of car noise.

**Primary use case:** Driving. Voice in, voice out. No screen dependency. Car noise (engine, horns, Siri navigation) must not interrupt the conversation.

**Architecture:** New `/talk` route serving `talk.html`. New `/api/brain/chat`, `/api/brain/voice`, and `/api/brain/tts` endpoints. Browser-side MediaRecorder for capture with smart MIME detection. Simple energy-threshold silence detection for auto-stop (V2: upgrade to Silero VAD). Google Cloud TTS returns MP3 played via `<audio>` element for reliable car speaker playback (survives screen lock via Media Session API). Continuous conversation loop: after TTS finishes, auto-resume listening. PWA manifest for home screen install.

**Tech Stack:** FastAPI, Jinja2, Gemini 3 Flash (conversation + transcription), Google Cloud TTS (speech output), Web Audio API (recording + silence detection), Media Session API (lock screen playback), existing brain Postgres schema, existing conversation.py engine.

**Research findings (Gemini-verified 2026-03-08):**
- `audio/webm;codecs=opus` works on Chrome, Firefox, Safari iOS 18+ — Gemini API accepts it natively
- Gemini handles car noise server-side (contextual correction) — do NOT pre-filter audio sent for transcription
- Send raw audio to Gemini multimodal endpoint, not a separate STT API
- Prompt: "Audio may contain road noise. Focus on primary speaker. Mark inaudible as [inaudible]."
- Web Speech API dies on screen lock — Cloud TTS via `<audio>` tag required for car use
- iOS PWA: getUserMedia works in standalone mode but may re-prompt permissions each launch
- iOS PWA: no auto-install banner — need custom instructions (Share → Add to Home Screen)
- MediaRecorder.start(1000) timeslice prevents memory issues on long recordings
- Browser `noiseSuppression: true` + `echoCancellation: true` on getUserMedia helps

---

### Task 1: Adapt conversation engine for web use

The conversation engine (`promaia/telegram/conversation.py`) currently takes a Telegram `chat_id` (integer). We need it to work with a web session identifier too.

**Files:**
- Modify: `promaia/telegram/conversation.py`
- Modify: `promaia/telegram/brain_ops.py`
- Create: `promaia/web/brain_chat.py`

**Step 1: Check brain_ops.py for chat_id usage**

Read `promaia/telegram/brain_ops.py` to understand how `chat_id` flows through `get_or_create_session`, `save_conversation_message`, `get_conversation_history`. The chat_id is used as a grouping key.

**Step 2: Create web brain chat adapter**

Create `promaia/web/brain_chat.py` — thin wrapper that routes web requests to the conversation engine using Zack's Telegram chat_id (so web and Telegram conversations share context — one brain).

```python
"""
Thin adapter: web endpoints -> conversation engine.
Web sessions use the whitelisted Telegram chat_id so all
conversations (web + Telegram) share context.
"""
import os
import logging
from promaia.telegram.conversation import generate_response, reset_synthesis_timer

logger = logging.getLogger(__name__)

WEB_CHAT_ID = int(os.environ.get("TELEGRAM_WHITELIST", "6269250506"))


async def chat(message: str) -> str:
    """Send a message to the brain and get a response."""
    response = await generate_response(WEB_CHAT_ID, message)
    await reset_synthesis_timer(WEB_CHAT_ID)
    return response


async def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
    """Transcribe audio bytes via Gemini multimodal (handles noise server-side)."""
    from google import genai
    from google.genai import types
    from promaia.ai.models import GOOGLE_MODELS

    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    response = await client.aio.models.generate_content(
        model=GOOGLE_MODELS["flash"],
        contents=[
            types.Content(parts=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                types.Part(text=(
                    "Transcribe this voice note exactly. The audio may contain "
                    "background road noise, car sounds, or navigation prompts. "
                    "Focus on the primary speaker's voice and ignore background sounds. "
                    "Return only the transcription, no commentary. "
                    "If a word is inaudible due to noise, mark it as [inaudible]."
                )),
            ])
        ],
        config=types.GenerateContentConfig(temperature=0.0),
    )
    if response.candidates and response.candidates[0].content.parts:
        return response.text.strip()
    return ""
```

**Step 3: Commit**

```bash
git add promaia/web/brain_chat.py
git commit -m "feat(phase5): web brain chat adapter — shares context with Telegram, noise-aware transcription"
```

---

### Task 2: Create API endpoints for brain chat, voice, and TTS

**Files:**
- Create: `promaia/web/routers/brain.py`
- Modify: `promaia/web/main.py` (register router)

**Step 1: Create the brain router**

```python
"""
Brain chat + voice + TTS API endpoints for the web interface.

POST /api/brain/chat     — text message in, response out
POST /api/brain/voice    — audio blob in, transcription + response out
POST /api/brain/tts      — text in, MP3 audio out (Google Cloud TTS)
"""
import logging
import os
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, Response
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
    transcript = await transcribe_audio(audio_bytes, mime)
    if not transcript:
        raise HTTPException(status_code=422, detail="Could not transcribe audio")

    reply = await chat(transcript)
    return ChatResponse(reply=reply, transcript=transcript)


@router.post("/tts")
async def brain_tts(req: ChatRequest):
    """Convert text to speech via Google Cloud TTS, return MP3 audio."""
    try:
        from google.cloud import texttospeech
        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=req.message)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Journey-F",
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
        )
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        return Response(
            content=response.audio_content,
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-cache"},
        )
    except ImportError:
        # Fallback: use Gemini TTS if google-cloud-texttospeech not installed
        logger.warning("google-cloud-texttospeech not installed, TTS unavailable")
        raise HTTPException(status_code=501, detail="TTS not configured")
    except Exception as e:
        logger.error(f"TTS failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="TTS failed")
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
git commit -m "feat(phase5): brain chat + voice + TTS API endpoints"
```

---

### Task 3: Create the Talk page template (driving-first design)

**Files:**
- Create: `promaia/web/templates/talk.html`
- Modify: `promaia/web/routers/dashboard.py` (add /talk route)
- Modify: `promaia/web/templates/base.html` (add Talk to nav)

**Design principles for driving:**
- MASSIVE mic button, dead center (thumb-reachable while glancing)
- Minimal visual noise — conversation messages visible but not the focus
- Status indicator large and readable at arm's length: "Listening...", "Thinking...", "Speaking..."
- Dark background to reduce glare at night
- Text input hidden by default (keyboard icon to reveal — not the primary interface)

**Step 1: Create talk.html**

Use `frontend-design` skill for the actual UI implementation. The template extends base.html and loads talk.js.

**Step 2: Add /talk route to dashboard.py**

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

```html
<a href="/talk" class="{% if active_page == 'talk' %}active{% endif %}">Talk</a>
```

**Step 4: Commit**

```bash
git add promaia/web/templates/talk.html promaia/web/routers/dashboard.py promaia/web/templates/base.html
git commit -m "feat(phase5): Talk page — driving-first voice interface"
```

---

### Task 4: Create talk.js — the conversation engine

**Files:**
- Create: `promaia/web/static/js/talk.js`

**This is the heart of the hands-free experience. Architecture:**

1. User taps mic → enters "conversation mode"
2. MediaRecorder captures audio with smart MIME detection
3. Simple energy-threshold silence detection auto-stops after ~2s of silence
4. Raw audio (unfiltered) sent to `/api/brain/voice` — Gemini handles noise
5. Response text sent to `/api/brain/tts` → MP3 returned
6. MP3 played via `<audio>` element (works through car Bluetooth, survives screen lock)
7. Media Session API shows "Promaia" on lock screen
8. After audio finishes playing → auto-resume listening (conversation loop)
9. Tap mic again → exit conversation mode

**Key implementation details:**

```javascript
// Smart MIME detection — tested order for cross-browser support
function getSupportedMimeType() {
    const types = [
        'audio/webm;codecs=opus',   // Chrome, Firefox, Safari 18+
        'audio/webm',               // Chrome/Android fallback
        'audio/mp4',                // Safari AAC
        'audio/ogg;codecs=opus',    // Old Firefox
    ];
    for (const type of types) {
        if (MediaRecorder.isTypeSupported(type)) return type;
    }
    return '';
}

// getUserMedia with car-optimized constraints
const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
        channelCount: 1,
        sampleRate: 16000,
        noiseSuppression: true,     // Browser-level noise suppression
        echoCancellation: true,     // Prevent TTS feedback loop
        autoGainControl: true,      // Stabilize levels
    }
});

// Silence detection via Web Audio API AnalyserNode
// Monitor RMS energy — when it drops below threshold for 2s, stop recording
// Threshold tuned for car environment (higher than default)

// TTS playback via <audio> element
async function playTTS(text) {
    const res = await fetch('/api/brain/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);

    // Media Session API for lock screen
    if ('mediaSession' in navigator) {
        navigator.mediaSession.metadata = new MediaMetadata({
            title: 'Promaia',
            artist: 'Your Brain',
        });
    }

    audio.onended = () => {
        URL.revokeObjectURL(url);
        // Auto-resume listening after response finishes
        if (conversationMode) startRecording();
    };
    audio.play();
}

// Handle iOS backgrounding — save recording if app is minimized
document.addEventListener('visibilitychange', () => {
    if (document.hidden && isRecording) {
        stopRecording(); // Save what we have
    }
});
```

**Step 5: Commit**

```bash
git add promaia/web/static/js/talk.js
git commit -m "feat(phase5): talk.js — hands-free conversation loop with Cloud TTS and silence detection"
```

---

### Task 5: PWA manifest for home screen install

**Files:**
- Create: `promaia/web/static/manifest.json`
- Create: `promaia/web/static/sw.js`
- Modify: `promaia/web/templates/base.html` (link manifest + meta tags + apple-touch-icon)

**Step 1: Create manifest.json**

```json
{
    "id": "promaia-zbrain",
    "name": "Promaia",
    "short_name": "Promaia",
    "description": "Your second brain — voice first",
    "start_url": "/talk",
    "display": "standalone",
    "background_color": "#1a1a2e",
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
self.addEventListener('install', (e) => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', (e) => e.respondWith(fetch(e.request)));
```

**Step 3: Add to base.html head**

```html
<link rel="manifest" href="/static/manifest.json">
<link rel="apple-touch-icon" href="/static/icon-192.png">
<meta name="theme-color" content="#E63946">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<script>if('serviceWorker' in navigator) navigator.serviceWorker.register('/static/sw.js');</script>
```

**Step 4: Generate placeholder icons** (192x192 and 512x512 PNG)

**Step 5: Commit**

```bash
git add promaia/web/static/manifest.json promaia/web/static/sw.js promaia/web/templates/base.html
git commit -m "feat(phase5): PWA manifest — installable on phone, starts on Talk page"
```

---

### Task 6: Google Cloud TTS setup

**Files:**
- Modify: `.env` (add GOOGLE_APPLICATION_CREDENTIALS or verify existing key works)
- Modify: `requirements.txt` or `pyproject.toml` (add google-cloud-texttospeech)

**Step 1: Check if google-cloud-texttospeech is installable**

```bash
pip install google-cloud-texttospeech
```

**Step 2: Verify credentials**

Google Cloud TTS needs a service account or API key. Check if the existing `GOOGLE_API_KEY` works for TTS or if we need Cloud credentials. If the existing key doesn't cover TTS, consider using Gemini's native TTS endpoint as fallback.

**Step 3: Test TTS endpoint**

```bash
curl -X POST http://localhost:8000/api/brain/tts \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello from Promaia"}' \
  --output test.mp3 && play test.mp3
```

**Step 4: Commit**

```bash
git commit -m "feat(phase5): Google Cloud TTS dependency + credentials"
```

---

### Task 7: Integration test — driving scenario

**Steps:**
1. Start local: `python -m promaia dev`
2. Open `http://localhost:8000/talk` on iPhone (via local network IP)
3. Tap mic → speak with background noise (TV, music) → verify auto-stop on silence
4. Verify transcription appears (Gemini handled noise)
5. Verify TTS response plays through phone speakers
6. Verify conversation loop: after TTS, it auto-starts listening again
7. Lock phone screen → verify audio still plays
8. Test text fallback: tap keyboard icon, type message, send
9. Install as PWA: Share → Add to Home Screen → verify it opens to Talk page
10. Push to Railway, verify at zbrain.online

---

## Execution Summary

| Task | What | Effort |
|------|------|--------|
| 1 | Web brain chat adapter + noise-aware transcription | 10 min |
| 2 | API endpoints (chat + voice + TTS) | 15 min |
| 3 | Talk page template (driving-first, use frontend-design) | 20 min |
| 4 | talk.js — conversation loop + silence detection + Cloud TTS | 30 min |
| 5 | PWA manifest | 10 min |
| 6 | Google Cloud TTS setup | 15 min |
| 7 | Integration test | 20 min |

**Total: ~2 hours**

## V2 Upgrades (future)
- Silero VAD (@ricky0123/vad-web) replacing simple silence detection
- Continuous listening without tap-to-start
- Wake word detection
- Gemini Live API for real-time streaming conversation
- Cloud TTS voice customization / persona voice
