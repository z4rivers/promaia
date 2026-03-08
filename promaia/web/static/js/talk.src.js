/**
 * talk.src.js — Hands-free voice conversation engine for Promaia.
 *
 * Bundled by esbuild. Uses @ricky0123/vad-web (Silero VAD) for
 * speech detection, sends audio to Gemini for transcription,
 * plays response via Cloud TTS through <audio> element.
 *
 * Conversation loop: tap mic → listen → detect speech end →
 * transcribe → respond → TTS → auto-resume listen → tap to stop.
 */
import { MicVAD } from '@ricky0123/vad-web';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let vad = null;
let conversationMode = false;
let isProcessing = false;
let currentAudio = null;

// ---------------------------------------------------------------------------
// DOM
// ---------------------------------------------------------------------------
const micBtn = document.getElementById('mic-btn');
const statusLabel = document.getElementById('talk-status');
const messagesEl = document.getElementById('messages');
const feedsEl = document.getElementById('feeds');
const micArea = document.getElementById('mic-area');
const kbToggle = document.getElementById('kb-toggle');
const textBar = document.getElementById('text-bar');
const textField = document.getElementById('text-field');
const sendBtn = document.getElementById('send-btn');
const closeKb = document.getElementById('close-kb');

// ---------------------------------------------------------------------------
// Float32Array → WAV blob (16-bit PCM, mono)
// ---------------------------------------------------------------------------
function writeString(view, offset, str) {
    for (let i = 0; i < str.length; i++) {
        view.setUint8(offset + i, str.charCodeAt(i));
    }
}

function float32ToWav(samples, sampleRate) {
    // VAD outputs at 16kHz by default
    sampleRate = sampleRate || 16000;
    const numSamples = samples.length;
    const buffer = new ArrayBuffer(44 + numSamples * 2);
    const view = new DataView(buffer);

    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + numSamples * 2, true);
    writeString(view, 8, 'WAVE');
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);       // PCM chunk size
    view.setUint16(20, 1, true);        // PCM format
    view.setUint16(22, 1, true);        // mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true); // byte rate
    view.setUint16(32, 2, true);        // block align
    view.setUint16(34, 16, true);       // bits per sample
    writeString(view, 36, 'data');
    view.setUint32(40, numSamples * 2, true);

    for (let i = 0; i < numSamples; i++) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }

    return new Blob([buffer], { type: 'audio/wav' });
}

// ---------------------------------------------------------------------------
// Status management
// ---------------------------------------------------------------------------
function setStatus(state, text) {
    statusLabel.dataset.state = state;
    statusLabel.textContent = text || {
        idle: 'Ready',
        listening: 'Listening...',
        thinking: 'Thinking...',
        speaking: 'Speaking...',
        error: 'Error — tap to retry',
    }[state] || state;
}

// ---------------------------------------------------------------------------
// Messages
// ---------------------------------------------------------------------------
function addMessage(role, text) {
    // Remove empty state placeholder
    const empty = messagesEl.querySelector('.talk-empty');
    if (empty) empty.remove();

    const div = document.createElement('div');
    div.className = `talk-msg talk-msg--${role}`;

    const label = document.createElement('div');
    label.className = 'talk-msg-label';
    label.textContent = role === 'user' ? 'You' : 'Promaia';
    div.appendChild(label);

    const content = document.createElement('div');
    content.textContent = text;
    div.appendChild(content);

    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ---------------------------------------------------------------------------
// TTS Playback
// ---------------------------------------------------------------------------
async function playTTS(text) {
    setStatus('speaking');

    try {
        const res = await fetch('/api/brain/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text }),
        });

        if (!res.ok) {
            console.warn('TTS unavailable, skipping audio playback');
            afterTTSComplete();
            return;
        }

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        currentAudio = new Audio(url);

        // Media Session API — shows "Promaia" on lock screen
        if ('mediaSession' in navigator) {
            navigator.mediaSession.metadata = new MediaMetadata({
                title: 'Promaia',
                artist: 'Your Brain',
            });
        }

        currentAudio.onended = () => {
            URL.revokeObjectURL(url);
            currentAudio = null;
            afterTTSComplete();
        };

        currentAudio.onerror = () => {
            URL.revokeObjectURL(url);
            currentAudio = null;
            afterTTSComplete();
        };

        await currentAudio.play();
    } catch (err) {
        console.error('TTS playback failed:', err);
        currentAudio = null;
        afterTTSComplete();
    }
}

function afterTTSComplete() {
    if (conversationMode && vad) {
        // Auto-resume listening (conversation loop)
        setStatus('listening');
        vad.start();
    } else {
        setStatus('idle');
    }
}

// ---------------------------------------------------------------------------
// VAD initialization
// ---------------------------------------------------------------------------
async function initVAD() {
    setStatus('thinking', 'Loading...');

    vad = await MicVAD.new({
        baseAssetPath: '/static/vad/',
        onnxWASMBasePath: '/static/vad/',

        onSpeechStart: () => {
            if (!isProcessing) {
                setStatus('listening');
            }
        },

        onSpeechEnd: async (audio) => {
            if (isProcessing) return;
            isProcessing = true;

            // Pause VAD while processing (prevents double-triggers)
            vad.pause();
            setStatus('thinking');

            try {
                const wavBlob = float32ToWav(audio);
                const formData = new FormData();
                formData.append('audio', wavBlob, 'speech.wav');

                const res = await fetch('/api/brain/voice', {
                    method: 'POST',
                    body: formData,
                });

                if (!res.ok) {
                    const errData = await res.json().catch(() => ({}));
                    throw new Error(errData.detail || `HTTP ${res.status}`);
                }

                const data = await res.json();

                if (data.transcript) {
                    addMessage('user', data.transcript);
                }
                addMessage('assistant', data.reply);

                // Play TTS — will auto-resume listening on completion
                await playTTS(data.reply);
            } catch (err) {
                console.error('Voice processing failed:', err);
                setStatus('error');
                // Resume listening after error pause
                setTimeout(() => {
                    if (conversationMode && vad) {
                        setStatus('listening');
                        vad.start();
                    }
                }, 2000);
            } finally {
                isProcessing = false;
            }
        },
    });
}

// ---------------------------------------------------------------------------
// Text input
// ---------------------------------------------------------------------------
async function sendText(text) {
    if (!text.trim()) return;

    addMessage('user', text);
    setStatus('thinking');

    try {
        const res = await fetch('/api/brain/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text }),
        });
        const data = await res.json();
        addMessage('assistant', data.reply);

        // Play TTS for text responses too
        await playTTS(data.reply);
    } catch (err) {
        console.error('Chat failed:', err);
        addMessage('assistant', 'Something went wrong. Try again?');
        setStatus('idle');
    }
}

// ---------------------------------------------------------------------------
// Event listeners
// ---------------------------------------------------------------------------

// Mic button — toggle conversation mode
micBtn.addEventListener('click', async () => {
    // Haptic feedback on supported devices
    if (navigator.vibrate) navigator.vibrate(50);

    if (!conversationMode) {
        // Enter conversation mode
        if (!vad) {
            try {
                await initVAD();
            } catch (err) {
                console.error('VAD init failed:', err);
                setStatus('error', 'Mic access denied');
                return;
            }
        }

        vad.start();
        conversationMode = true;
        micBtn.classList.add('active');
        feedsEl.classList.add('dimmed');
        setStatus('listening');
    } else {
        // Exit conversation mode
        if (vad) vad.pause();
        conversationMode = false;
        micBtn.classList.remove('active');
        feedsEl.classList.remove('dimmed');
        setStatus('idle');

        if (currentAudio) {
            currentAudio.pause();
            currentAudio = null;
        }
    }
});

// Keyboard toggle
kbToggle.addEventListener('click', () => {
    textBar.classList.add('visible');
    micArea.style.display = 'none';
    textField.focus();
});

closeKb.addEventListener('click', () => {
    textBar.classList.remove('visible');
    micArea.style.display = '';
});

// Send text
sendBtn.addEventListener('click', () => {
    const text = textField.value.trim();
    if (text) {
        textField.value = '';
        sendText(text);
    }
});

textField.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        sendBtn.click();
    }
});

// Handle iOS backgrounding — stop recording if app is minimized
document.addEventListener('visibilitychange', () => {
    if (document.hidden && conversationMode && vad) {
        vad.pause();
        setStatus('idle', 'Paused');
    } else if (!document.hidden && conversationMode && vad && !isProcessing) {
        vad.start();
        setStatus('listening');
    }
});
