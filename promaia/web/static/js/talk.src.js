/**
 * talk.src.js — Real-Time WebSocket Voice Engine for Promaia
 *
 * Streams raw 16kHz PCM from mic -> Server -> Gemini Live API
 * Receives raw 24kHz PCM from Gemini -> Server -> Browser
 * Uses Gemini's server-side VAD for turn-taking and interruption detection.
 * Silero VAD (browser) is kept only for instant local playback cutoff.
 */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const VoiceSessionState = {
    vad: null,
    conversationMode: false,
    ws: null,
    
    // Audio Capture State
    captureStream: null,
    captureCtx: null,
    captureScriptNode: null,
    
    // Audio Playback State
    playCtx: null,
    nextPlayTime: 0,
    playingNodes: [],
    
    // Wake Lock
    wakeLock: null,
    
    // Real-Time Chat Sync State
    textWs: null,
    lastSentTextLocal: null,
    lastReceivedTextLocal: null,
};

const AudioProcessingUtils = {
    base64ToFloat32Pcm: function(base64Data) {
        const binaryStr = window.atob(base64Data);
        const len = binaryStr.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
            bytes[i] = binaryStr.charCodeAt(i);
        }
        const int16 = new Int16Array(bytes.buffer);
        const float32 = new Float32Array(int16.length);
        for (let i = 0; i < int16.length; i++) {
            float32[i] = int16[i] / 32768; // normalize to -1.0 to 1.0
        }
        return float32;
    },
    
    float32ToBase64Pcm: function(float32Array) {
        // Convert Float32 to Int16
        const int16Array = new Int16Array(float32Array.length);
        for(let i=0; i<float32Array.length; i++) {
            let s = Math.max(-1, Math.min(1, float32Array[i]));
            int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        
        // Base64 encode
        const uint8Array = new Uint8Array(int16Array.buffer);
        let binary = '';
        for (let i = 0; i < uint8Array.byteLength; i++) {
            binary += String.fromCharCode(uint8Array[i]);
        }
        return window.btoa(binary);
    }
};

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
const closeKb = document.getElementById('close-kb');

// ---------------------------------------------------------------------------
// Status management
// ---------------------------------------------------------------------------
function setStatus(state, text) {
    statusLabel.dataset.state = state;
    statusLabel.textContent = text || {
        idle: 'Ready',
        connecting: 'Connecting to Brain...',
        listening: 'Listening...',
        thinking: 'Thinking...',
        speaking: 'Speaking...',
        error: 'Error — tap to retry',
    }[state] || state;
}

// ---------------------------------------------------------------------------
// Audio feedback tones (instant UX confirmation, no latency)
// ---------------------------------------------------------------------------
function playTone(type) {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const gain = ctx.createGain();
        gain.connect(ctx.destination);

        if (type === 'start') {
            // Rising two-note chime: "I'm on"
            gain.gain.setValueAtTime(0.15, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);

            const osc1 = ctx.createOscillator();
            osc1.type = 'sine';
            osc1.frequency.value = 587.33; // D5
            osc1.connect(gain);
            osc1.start(ctx.currentTime);
            osc1.stop(ctx.currentTime + 0.12);

            const gain2 = ctx.createGain();
            gain2.connect(ctx.destination);
            gain2.gain.setValueAtTime(0.15, ctx.currentTime + 0.12);
            gain2.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);

            const osc2 = ctx.createOscillator();
            osc2.type = 'sine';
            osc2.frequency.value = 880; // A5
            osc2.connect(gain2);
            osc2.start(ctx.currentTime + 0.12);
            osc2.stop(ctx.currentTime + 0.35);

            setTimeout(() => ctx.close(), 500);
        } else if (type === 'end') {
            // Gentle descending tone: "done"
            gain.gain.setValueAtTime(0.12, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.35);

            const osc = ctx.createOscillator();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(659.25, ctx.currentTime); // E5
            osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.25); // down to A4
            osc.connect(gain);
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + 0.3);

            setTimeout(() => ctx.close(), 500);
        }
    } catch (e) {
        console.warn('[Tone] Could not play:', e.message);
    }
}

// ---------------------------------------------------------------------------
// Messages UI
// ---------------------------------------------------------------------------
function addMessage(role, text) {
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
// WebSocket Connection
// ---------------------------------------------------------------------------
function connectWebSocket() {
    return new Promise((resolve, reject) => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        VoiceSessionState.ws = new WebSocket(`${protocol}//${window.location.host}/api/brain/stream`);

        VoiceSessionState.ws.onopen = () => {
            console.log('[WS] Connected to Promaia stream');
            resolve();
        };

        VoiceSessionState.ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.serverContent) {
                if (msg.serverContent.control === 'hang_up') {
                    console.log('[WS] Handled server hang-up request');
                    if (VoiceSessionState.conversationMode) stopConversation();
                    return;
                }
                // Audio chunk recieved
                if (msg.serverContent.modelTurn) {
                    const parts = msg.serverContent.modelTurn.parts;
                    for (const part of parts) {
                        if (part.inlineData) {
                            queuePlayback(part.inlineData.data);
                            setStatus('speaking');
                        }
                        if (part.text) {
                            // Transcript or text payload
                            VoiceSessionState.lastReceivedTextLocal = part.text;
                            addMessage('assistant', part.text);
                        }
                    }
                }
                
                // Gemini's server-side VAD detected user interruption
                if (msg.serverContent.interrupted) {
                    console.log('[WS] Gemini detected interruption — stopping playback');
                    stopPlayback();
                    setStatus('listening');
                }

                // End of thought
                if (msg.serverContent.turnComplete) {
                    console.log('[WS] Turn Complete');
                    // We wait for the audio queue to finish draining naturally before UI goes back to 'listening'
                }
            }
        };

        VoiceSessionState.ws.onclose = () => {
            console.log('[WS] Disconnected');
            if (VoiceSessionState.conversationMode) {
                setStatus('error', 'Connection lost');
                stopConversation();
            }
        };

        VoiceSessionState.ws.onerror = (err) => {
            console.error('[WS] Error:', err);
            reject(err);
        };
    });
}

// ---------------------------------------------------------------------------
// Audio Playback (Server -> Browser @ 24kHz)
// ---------------------------------------------------------------------------
function queuePlayback(base64Data) {
    if (!VoiceSessionState.playCtx) {
        console.warn("Play context not initialized synchronously. Creating late (iOS may block this).");
        VoiceSessionState.playCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
        VoiceSessionState.nextPlayTime = VoiceSessionState.playCtx.currentTime;
    }

    if (VoiceSessionState.playCtx.state === 'suspended') {
        VoiceSessionState.playCtx.resume();
    }

    // Decode Base64 to Int16 to Float32 using pure helper
    const float32 = AudioProcessingUtils.base64ToFloat32Pcm(base64Data);

    // Create Buffer
    const buffer = VoiceSessionState.playCtx.createBuffer(1, float32.length, 24000);
    buffer.getChannelData(0).set(float32);

    const source = VoiceSessionState.playCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(VoiceSessionState.playCtx.destination);

    // Schedule seamlessly back-to-back
    if (VoiceSessionState.nextPlayTime < VoiceSessionState.playCtx.currentTime) {
        VoiceSessionState.nextPlayTime = VoiceSessionState.playCtx.currentTime;
    }
    source.start(VoiceSessionState.nextPlayTime);
    VoiceSessionState.nextPlayTime += buffer.duration;

    VoiceSessionState.playingNodes.push(source);
    source.onended = () => {
        VoiceSessionState.playingNodes = VoiceSessionState.playingNodes.filter(n => n !== source);
        // If queue is completely empty, we are done speaking
        if (VoiceSessionState.playingNodes.length === 0 && VoiceSessionState.conversationMode) {
            setStatus('listening');
        }
    };
}

function stopPlayback() {
    VoiceSessionState.playingNodes.forEach(node => {
        try { node.stop(); } catch(e){}
    });
    VoiceSessionState.playingNodes = [];
    if (VoiceSessionState.playCtx) {
        VoiceSessionState.nextPlayTime = VoiceSessionState.playCtx.currentTime;
    }
}

// ---------------------------------------------------------------------------
// Audio Capture (Browser -> Server @ 16kHz)
// ---------------------------------------------------------------------------
async function startCapture() {
    VoiceSessionState.captureStream = await navigator.mediaDevices.getUserMedia({ 
        audio: { 
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true
        } 
    });
    
    // Gemini Live API expects 16kHz audio out of the box
    // Context is normally created synchronously during micBtn click to bypass iOS Safari blocking
    if (!VoiceSessionState.captureCtx) {
        VoiceSessionState.captureCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    }
    const source = VoiceSessionState.captureCtx.createMediaStreamSource(VoiceSessionState.captureStream);
    
    // Create script processor to read raw PCM frames
    VoiceSessionState.captureScriptNode = VoiceSessionState.captureCtx.createScriptProcessor(4096, 1, 1);
    
    VoiceSessionState.captureScriptNode.onaudioprocess = (e) => {
        if (!VoiceSessionState.ws || VoiceSessionState.ws.readyState !== WebSocket.OPEN) return;
        
        const float32Array = e.inputBuffer.getChannelData(0);
        // Convert Float32 to Int16 to Base64 using pure helper
        const b64 = AudioProcessingUtils.float32ToBase64Pcm(float32Array);
        
        VoiceSessionState.ws.send(JSON.stringify({
            realtimeInput: { 
                mediaChunks: [{ mimeType: 'audio/pcm;rate=16000', data: b64 }] 
            }
        }));
    };
    
    source.connect(VoiceSessionState.captureScriptNode);
    // Connect to a silent gain node to prevent local mic echo
    const silentGain = VoiceSessionState.captureCtx.createGain();
    silentGain.gain.value = 0;
    VoiceSessionState.captureScriptNode.connect(silentGain);
    silentGain.connect(VoiceSessionState.captureCtx.destination);
}

function stopCapture() {
    try {
        if (VoiceSessionState.captureScriptNode) {
            try { VoiceSessionState.captureScriptNode.disconnect(); } catch (e) {}
            VoiceSessionState.captureScriptNode = null;
        }
        if (VoiceSessionState.captureCtx) {
            // AudioContext.close() returns a promise, so catch rejection
            VoiceSessionState.captureCtx.close().catch(() => {});
            VoiceSessionState.captureCtx = null;
        }
        if (VoiceSessionState.captureStream) {
            VoiceSessionState.captureStream.getTracks().forEach(t => {
                try { t.stop(); } catch (e) {}
            });
            VoiceSessionState.captureStream = null;
        }
    } catch (e) {
        console.warn("[Capture] Teardown error:", e);
    }
}

// ---------------------------------------------------------------------------
// VAD initialization — local Silero VAD for instant playback cutoff only.
// Gemini's server-side VAD handles turn-taking and interruption signaling.
// ---------------------------------------------------------------------------
async function initVAD() {
    if (!window.vad || !window.vad.MicVAD) {
        throw new Error("VAD library not loaded from CDN yet.");
    }

    if (VoiceSessionState.vad) {
        try { VoiceSessionState.vad.pause(); } catch(e) {}
        try { VoiceSessionState.vad.destroy(); } catch(e) {}
        try {
            if (VoiceSessionState.vad.stream) { VoiceSessionState.vad.stream.getTracks().forEach(t => t.stop()); }
            if (VoiceSessionState.vad.mediaStream) { VoiceSessionState.vad.mediaStream.getTracks().forEach(t => t.stop()); }
        } catch(e) {}
        VoiceSessionState.vad = null;
    }

    VoiceSessionState.vad = await window.vad.MicVAD.new({
        positiveSpeechThreshold: 0.95,
        negativeSpeechThreshold: 0.75,
        redemptionFrames: 15,
        minSpeechFrames: 8,
        preSpeechPadFrames: 3,

        onSpeechStart: () => {
            // Instant local playback cutoff — don't wait for server round-trip
            if (VoiceSessionState.playingNodes.length > 0) {
                console.log('[VAD] Speech during playback — cutting local audio');
                stopPlayback();
                setStatus('listening');
            }
        },

        onSpeechEnd: () => {
            // UI hint only — Gemini's VAD is authoritative for turn-taking
            if (VoiceSessionState.playingNodes.length === 0) {
                setStatus('thinking');
            }
        },
    });
    console.log('[VAD] Local playback monitor initialized');
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------
async function startConversation() {
    VoiceSessionState.conversationMode = true;
    micBtn.classList.add('active');
    feedsEl.classList.add('dimmed');
    setStatus('connecting');

    // Acquire Wake Lock to prevent screen sleep during voice session
    try {
        if ('wakeLock' in navigator) {
            VoiceSessionState.wakeLock = await navigator.wakeLock.request('screen');
            console.log('[WakeLock] Screen lock acquired — screen will stay on');
            VoiceSessionState.wakeLock.addEventListener('release', () => {
                console.log('[WakeLock] Released');
                // Re-acquire if still in conversation (e.g. after tab switch back)
                if (VoiceSessionState.conversationMode && 'wakeLock' in navigator) {
                    navigator.wakeLock.request('screen').then(wl => {
                        VoiceSessionState.wakeLock = wl;
                        console.log('[WakeLock] Re-acquired after release');
                    }).catch(() => {});
                }
            });
        }
    } catch (e) {
        console.warn('[WakeLock] Could not acquire:', e.message);
    }

    try {
        console.log("Starting conversation sequence...");
        await connectWebSocket();
        console.log("WS connected. Init VAD...");
        if (!VoiceSessionState.vad) await initVAD();
        console.log("VAD Init'd. Starting capture...");
        await startCapture();
        console.log("Capture started. Starting VAD...");
        VoiceSessionState.vad.start();
        playTone('start');
        setStatus('listening');
    } catch (err) {
        console.error("FAILED to start conversation!");
        console.error("Error payload:", err);
        console.dir(err);
        setStatus('error');
        stopConversation();
    }
}

function stopConversation() {
    VoiceSessionState.conversationMode = false;
    micBtn.classList.remove('active');
    feedsEl.classList.remove('dimmed');
    setStatus('idle');
    playTone('end');
    
    stopPlayback();
    stopCapture();
    if (VoiceSessionState.vad) {
        try { VoiceSessionState.vad.pause(); } catch(e) {}
        try { VoiceSessionState.vad.destroy(); } catch(e) {}
        // Force kill any hidden streams the VAD might be holding onto
        try {
            if (VoiceSessionState.vad.stream) { VoiceSessionState.vad.stream.getTracks().forEach(t => t.stop()); }
            if (VoiceSessionState.vad.mediaStream) { VoiceSessionState.vad.mediaStream.getTracks().forEach(t => t.stop()); }
        } catch(e) {}
        VoiceSessionState.vad = null;
    }
    // Close playback context to fully release audio hardware
    if (VoiceSessionState.playCtx) {
        VoiceSessionState.playCtx.close().catch(() => {});
        VoiceSessionState.playCtx = null;
        VoiceSessionState.nextPlayTime = 0;
    }
    
    if (VoiceSessionState.ws) {
        // Strip handlers to prevent ghost callbacks after intentional close
        VoiceSessionState.ws.onclose = null;
        VoiceSessionState.ws.onerror = null;
        VoiceSessionState.ws.onmessage = null;
        if (VoiceSessionState.ws.readyState === WebSocket.OPEN || VoiceSessionState.ws.readyState === WebSocket.CONNECTING) {
            VoiceSessionState.ws.close(1000, 'user_hangup');
        }
        VoiceSessionState.ws = null;
        console.log('[WS] Force closed and nulled');
    }

    // Release Wake Lock
    if (VoiceSessionState.wakeLock) {
        VoiceSessionState.wakeLock.release().catch(() => {});
        VoiceSessionState.wakeLock = null;
        console.log('[WakeLock] Released on conversation end');
    }
}

// ---------------------------------------------------------------------------
// Text input (Direct text push through WebSocket)
// ---------------------------------------------------------------------------
async function sendText(text) {
    if (!text.trim()) return;
    VoiceSessionState.lastSentTextLocal = text;
    addMessage('user', text);
    setStatus('thinking');

    // Auto-connect WebSocket if not already open (text-only, no mic needed)
    if (!VoiceSessionState.ws || VoiceSessionState.ws.readyState !== WebSocket.OPEN) {
        try {
            await connectWebSocket();
        } catch (err) {
            addMessage('assistant', '(Could not connect — try again)');
            setStatus('error');
            return;
        }
    }

    VoiceSessionState.ws.send(JSON.stringify({ 
        clientContent: { 
            turns: [{ role: "user", parts: [{ text: text }] }],
            turnComplete: true 
        } 
    }));
}

// ---------------------------------------------------------------------------
// Event listeners
// ---------------------------------------------------------------------------
micBtn.addEventListener('click', () => {
    if (navigator.vibrate) navigator.vibrate(50);

    // Toggle: tap to start, tap to stop
    if (VoiceSessionState.conversationMode) {
        console.log('[UI] Conversation stopped via mic toggle');
        stopConversation();
        return;
    }

    // Starting — force synchronous AudioContext init for iOS Safari
    try {
        if (!VoiceSessionState.playCtx) {
            VoiceSessionState.playCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
            VoiceSessionState.nextPlayTime = VoiceSessionState.playCtx.currentTime;
            const osc = VoiceSessionState.playCtx.createOscillator();
            osc.connect(VoiceSessionState.playCtx.destination);
            osc.start(0);
            osc.stop(0.001);
        } else if (VoiceSessionState.playCtx.state === 'suspended') {
            VoiceSessionState.playCtx.resume();
        }

        if (!VoiceSessionState.captureCtx) {
            VoiceSessionState.captureCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
            const osc2 = VoiceSessionState.captureCtx.createOscillator();
            osc2.connect(VoiceSessionState.captureCtx.destination);
            osc2.start(0);
            osc2.stop(0.001);
        } else if (VoiceSessionState.captureCtx.state === 'suspended') {
            VoiceSessionState.captureCtx.resume();
        }
    } catch (e) {
        console.error("Audio Context Unlock Error:", e);
    }

    startConversation();
});

if (kbToggle) {
    kbToggle.addEventListener('click', () => {
        textBar.classList.add('visible');
        micArea.style.display = 'none';
        const input = document.getElementById('maia-chat-input');
        if (input) input.focus();
    });
}

if (closeKb) {
    closeKb.addEventListener('click', () => {
        textBar.classList.remove('visible');
        micArea.style.display = '';
    });
}

// The text input is now handled entirely by the Maia Widget (maia_widget.js)
// which talks directly to the Brain API instead of the Voice API.

// Camera upload handling
const cameraBtn = document.getElementById('camera-toggle');
const cameraInput = document.getElementById('camera-input');

if (cameraBtn && cameraInput) {
    cameraBtn.addEventListener('click', () => {
        cameraInput.click();
    });

    cameraInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        if (navigator.vibrate) navigator.vibrate(50);
        setStatus('thinking', 'Analyzing photo...');
        
        // Add visual feedback to chat
        addMessage('user', '[Sent a photo]');

        const formData = new FormData();
        formData.append('photo', file);

        try {
            const response = await fetch('/api/capture', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            if (response.ok) {
                addMessage('assistant', `I saved this to memory:\n\n${data.description}`);
                setStatus('idle');
            } else {
                console.error('Capture error:', data);
                addMessage('assistant', `Failed to process image: ${data.detail || data.message || 'Unknown error'}`);
                setStatus('error', 'Analysis failed');
                setTimeout(() => setStatus('idle'), 3000);
            }
        } catch (err) {
            console.error('Network error during upload:', err);
            addMessage('assistant', 'Network error while uploading photo.');
            setStatus('error');
            setTimeout(() => setStatus('idle'), 3000);
        }
        
        // Reset file input
        cameraInput.value = '';
    });
}

// Screen sleep handling — DON'T kill conversation, just log
// Wake Lock keeps screen on; if it fails, we still want audio to survive
document.addEventListener('visibilitychange', () => {
    if (document.hidden && VoiceSessionState.conversationMode) {
        console.warn('[Visibility] Page hidden during conversation — Wake Lock should prevent this');
    }
});

function connectTextLog() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    VoiceSessionState.textWs = new WebSocket(`${protocol}//${window.location.host}/api/brain/stream/text`);
    VoiceSessionState.textWs.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'chat_log') {
                // Deduplicate if we originated it locally
                if (msg.role === 'user' && msg.text === VoiceSessionState.lastSentTextLocal) {
                    VoiceSessionState.lastSentTextLocal = null;
                    return;
                }
                if (msg.role === 'assistant' && msg.text === VoiceSessionState.lastReceivedTextLocal) {
                    VoiceSessionState.lastReceivedTextLocal = null;
                    return;
                }
                addMessage(msg.role, msg.text);
            }
        } catch (e) {}
    };
    VoiceSessionState.textWs.onclose = () => {
        setTimeout(connectTextLog, 5000);
    };
}
connectTextLog();
