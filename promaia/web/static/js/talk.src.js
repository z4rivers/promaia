/**
 * talk.src.js — Real-Time WebSocket Voice Engine for Promaia
 *
 * Streams raw 16kHz PCM from mic -> Server -> Gemini Live API
 * Receives raw 24kHz PCM from Gemini -> Server -> Browser
 * Uses Silero VAD (loaded via CDN as `window.vad`) purely for UI state and interruption signaling.
 */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let vad = null;
let conversationMode = false;
let ws = null;

// Audio Capture State
let captureStream = null;
let captureCtx = null;
let captureScriptNode = null;

// Audio Playback State
let playCtx = null;
let nextPlayTime = 0;
let playingNodes = [];

// Wake Lock (keeps screen on during voice sessions)
let wakeLock = null;

// Real-Time Chat Sync State
let textWs = null;
let lastSentTextLocal = null;
let lastReceivedTextLocal = null;

// ---------------------------------------------------------------------------
// DOM
// ---------------------------------------------------------------------------
const micBtn = document.getElementById('mic-btn');
const endBtn = document.getElementById('end-btn');
const vadModeBtns = document.querySelectorAll('.vad-mode-btn');
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
        ws = new WebSocket(`${protocol}//${window.location.host}/api/brain/stream`);

        ws.onopen = () => {
            console.log('[WS] Connected to Promaia stream');
            resolve();
        };

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            if (msg.serverContent) {
                if (msg.serverContent.control === 'hang_up') {
                    console.log('[WS] Handled server hang-up request');
                    if (conversationMode) stopConversation();
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
                            lastReceivedTextLocal = part.text;
                            addMessage('assistant', part.text);
                        }
                    }
                }
                
                // End of thought
                if (msg.serverContent.turnComplete) {
                    console.log('[WS] Turn Complete');
                    // We wait for the audio queue to finish draining naturally before UI goes back to 'listening'
                }
            }
        };

        ws.onclose = () => {
            console.log('[WS] Disconnected');
            if (conversationMode) {
                setStatus('error', 'Connection lost');
                stopConversation();
            }
        };

        ws.onerror = (err) => {
            console.error('[WS] Error:', err);
            reject(err);
        };
    });
}

// ---------------------------------------------------------------------------
// Audio Playback (Server -> Browser @ 24kHz)
// ---------------------------------------------------------------------------
function queuePlayback(base64Data) {
    if (!playCtx) {
        console.warn("Play context not initialized synchronously. Creating late (iOS may block this).");
        playCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
        nextPlayTime = playCtx.currentTime;
    }

    if (playCtx.state === 'suspended') {
        playCtx.resume();
    }

    // Decode Base64 to Int16 to Float32
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

    // Create Buffer
    const buffer = playCtx.createBuffer(1, float32.length, 24000);
    buffer.getChannelData(0).set(float32);

    const source = playCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(playCtx.destination);

    // Schedule seamlessly back-to-back
    if (nextPlayTime < playCtx.currentTime) {
        nextPlayTime = playCtx.currentTime;
    }
    source.start(nextPlayTime);
    nextPlayTime += buffer.duration;

    playingNodes.push(source);
    source.onended = () => {
        playingNodes = playingNodes.filter(n => n !== source);
        // If queue is completely empty, we are done speaking
        if (playingNodes.length === 0 && conversationMode) {
            setStatus('listening');
        }
    };
}

function stopPlayback() {
    playingNodes.forEach(node => {
        try { node.stop(); } catch(e){}
    });
    playingNodes = [];
    if (playCtx) {
        nextPlayTime = playCtx.currentTime;
    }
}

// ---------------------------------------------------------------------------
// Audio Capture (Browser -> Server @ 16kHz)
// ---------------------------------------------------------------------------
async function startCapture() {
    captureStream = await navigator.mediaDevices.getUserMedia({ 
        audio: { 
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true
        } 
    });
    
    // Gemini Live API expects 16kHz audio out of the box
    // Context is normally created synchronously during micBtn click to bypass iOS Safari blocking
    if (!captureCtx) {
        captureCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    }
    const source = captureCtx.createMediaStreamSource(captureStream);
    
    // Create script processor to read raw PCM frames
    captureScriptNode = captureCtx.createScriptProcessor(4096, 1, 1);
    
    captureScriptNode.onaudioprocess = (e) => {
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        
        const float32Array = e.inputBuffer.getChannelData(0);
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
        const b64 = window.btoa(binary);
        
        ws.send(JSON.stringify({
            realtimeInput: { 
                mediaChunks: [{ mimeType: 'audio/pcm;rate=16000', data: b64 }] 
            }
        }));
    };
    
    source.connect(captureScriptNode);
    // Connect to a silent gain node to prevent local mic echo
    const silentGain = captureCtx.createGain();
    silentGain.gain.value = 0;
    captureScriptNode.connect(silentGain);
    silentGain.connect(captureCtx.destination);
}

function stopCapture() {
    try {
        if (captureScriptNode) {
            try { captureScriptNode.disconnect(); } catch (e) {}
            captureScriptNode = null;
        }
        if (captureCtx) {
            // AudioContext.close() returns a promise, so catch rejection
            captureCtx.close().catch(() => {});
            captureCtx = null;
        }
        if (captureStream) {
            captureStream.getTracks().forEach(t => {
                try { t.stop(); } catch (e) {}
            });
            captureStream = null;
        }
    } catch (e) {
        console.warn("[Capture] Teardown error:", e);
    }
}

let currentVadMode = 'normal';

// ---------------------------------------------------------------------------
// VAD initialization (Used purely for UI State and Interruptions)
// ---------------------------------------------------------------------------
async function initVAD() {
    // CDN injects the library into the global window.vad object
    if (!window.vad || !window.vad.MicVAD) {
        throw new Error("VAD library not loaded from CDN yet.");
    }
    
    // Cleanup old vad if swapping modes
    if (vad) {
        try { vad.pause(); } catch(e) {}
    }

    const modeConfig = currentVadMode === 'driving' ? {
        positiveSpeechThreshold: 0.95,
        negativeSpeechThreshold: 0.75,
        redemptionFrames: 15,
        minSpeechFrames: 8,
        preSpeechPadFrames: 3,
    } : {
        positiveSpeechThreshold: 0.82,
        negativeSpeechThreshold: 0.6,
        redemptionFrames: 8,
        minSpeechFrames: 5,
        preSpeechPadFrames: 3,
    };

    vad = await window.vad.MicVAD.new({
        ...modeConfig,

        onSpeechStart: () => {
            console.log('[VAD] Speech started - Interruption triggered');
            
            // 11.4: The Interruption Mechanism
            if (playingNodes.length > 0) {
                stopPlayback(); // stop local audio echo immediately
                
                // Send explicit turnComplete interrupt to tell Gemini to stop talking and listen
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ 
                        clientContent: { 
                            turns: [{ role: "user", parts: [{ text: "Stop." }] }],
                            turnComplete: true 
                        } 
                    }));
                }
            }
            setStatus('listening');
        },

        onSpeechEnd: () => {
            console.log('[VAD] User stopped talking');
            // Gemini handles STT automatically, we just update the UI state
            if (playingNodes.length === 0) {
                setStatus('thinking');
            }
        },
    });
    console.log('[VAD] UI Monitor Initialized');
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------
async function startConversation() {
    conversationMode = true;
    micBtn.classList.add('active');
    endBtn.classList.add('visible');
    feedsEl.classList.add('dimmed');
    setStatus('connecting');

    // Acquire Wake Lock to prevent screen sleep during voice session
    try {
        if ('wakeLock' in navigator) {
            wakeLock = await navigator.wakeLock.request('screen');
            console.log('[WakeLock] Screen lock acquired — screen will stay on');
            wakeLock.addEventListener('release', () => {
                console.log('[WakeLock] Released');
                // Re-acquire if still in conversation (e.g. after tab switch back)
                if (conversationMode && 'wakeLock' in navigator) {
                    navigator.wakeLock.request('screen').then(wl => {
                        wakeLock = wl;
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
        if (!vad) await initVAD();
        console.log("VAD Init'd. Starting capture...");
        await startCapture();
        console.log("Capture started. Starting VAD...");
        vad.start();
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
    conversationMode = false;
    micBtn.classList.remove('active');
    endBtn.classList.remove('visible');
    feedsEl.classList.remove('dimmed');
    setStatus('idle');
    playTone('end');
    
    stopPlayback();
    stopCapture();
    if (vad) {
        try { vad.pause(); } catch(e) {}
        try { vad.destroy(); } catch(e) {}
        // Force kill any hidden streams the VAD might be holding onto
        try {
            if (vad.stream) { vad.stream.getTracks().forEach(t => t.stop()); }
            if (vad.mediaStream) { vad.mediaStream.getTracks().forEach(t => t.stop()); }
        } catch(e) {}
        vad = null;
    }
    // Close playback context to fully release audio hardware
    if (playCtx) {
        playCtx.close().catch(() => {});
        playCtx = null;
        nextPlayTime = 0;
    }
    
    if (ws) {
        // Strip handlers to prevent ghost callbacks after intentional close
        ws.onclose = null;
        ws.onerror = null;
        ws.onmessage = null;
        if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
            ws.close(1000, 'user_hangup');
        }
        ws = null;
        console.log('[WS] Force closed and nulled');
    }

    // Release Wake Lock
    if (wakeLock) {
        wakeLock.release().catch(() => {});
        wakeLock = null;
        console.log('[WakeLock] Released on conversation end');
    }
}

// ---------------------------------------------------------------------------
// Text input (Direct text push through WebSocket)
// ---------------------------------------------------------------------------
async function sendText(text) {
    if (!text.trim()) return;
    lastSentTextLocal = text;
    addMessage('user', text);
    setStatus('thinking');

    // Auto-connect WebSocket if not already open (text-only, no mic needed)
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        try {
            await connectWebSocket();
        } catch (err) {
            addMessage('assistant', '(Could not connect — try again)');
            setStatus('error');
            return;
        }
    }

    ws.send(JSON.stringify({ 
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
    
    // 1. Force completely synchronous initialization of ALL AudioContexts for iOS Safari
    try {
        if (!playCtx) {
            playCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
            nextPlayTime = playCtx.currentTime;
            
            // Hack to unlock iOS audio output immediately
            const osc = playCtx.createOscillator();
            osc.connect(playCtx.destination);
            osc.start(0);
            osc.stop(0.001);
        } else if (playCtx.state === 'suspended') {
            playCtx.resume();
        }

        if (!captureCtx) {
            captureCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
            
            // Hack to unlock iOS audio input pipeline immediately
            const osc2 = captureCtx.createOscillator();
            osc2.connect(captureCtx.destination);
            osc2.start(0);
            osc2.stop(0.001);
        } else if (captureCtx.state === 'suspended') {
            captureCtx.resume();
        }
    } catch (e) {
        console.error("Audio Context Unlock Error:", e);
    }

    if (!conversationMode) {
        startConversation();
    } else {
        // If already in conversation mode, a tap on the mic acts as a manual "Interrupt" / "Stop Talking" button
        console.log('[UI] Manual Interrupt triggered via mic button');
        if (playingNodes.length > 0) {
            stopPlayback();
        }
        
        // Send explicit turnComplete interrupt to tell Gemini to stop talking and listen
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ 
                clientContent: { 
                    turns: [{ role: "user", parts: [{ text: "Stop." }] }],
                    turnComplete: true 
                } 
            }));
        }
        setStatus('listening');
    }
});

endBtn.addEventListener('click', () => {
    if (navigator.vibrate) navigator.vibrate(50);
    if (conversationMode) {
        console.log('[UI] Conversation stopped via End Call button');
        stopConversation();
    }
});

vadModeBtns.forEach(btn => {
    btn.addEventListener('click', async () => {
        vadModeBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentVadMode = btn.dataset.mode;
        
        // If we are currently in a conversation, we need to hot-swap the VAD
        if (conversationMode && vad) {
            console.log(`[VAD] Hot-swapping to ${currentVadMode} mode`);
            await initVAD();
            vad.start();
        }
    });
});

kbToggle.addEventListener('click', () => {
    textBar.classList.add('visible');
    micArea.style.display = 'none';
    textField.focus();
});

closeKb.addEventListener('click', () => {
    textBar.classList.remove('visible');
    micArea.style.display = '';
});

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

// Camera upload handling
const cameraBtn = document.getElementById('camera-toggle');
const cameraInput = document.getElementById('camera-input');

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

// Screen sleep handling — DON'T kill conversation, just log
// Wake Lock keeps screen on; if it fails, we still want audio to survive
document.addEventListener('visibilitychange', () => {
    if (document.hidden && conversationMode) {
        console.warn('[Visibility] Page hidden during conversation — Wake Lock should prevent this');
    }
});

function connectTextLog() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    textWs = new WebSocket(`${protocol}//${window.location.host}/api/brain/stream/text`);
    textWs.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'chat_log') {
                // Deduplicate if we originated it locally
                if (msg.role === 'user' && msg.text === lastSentTextLocal) {
                    lastSentTextLocal = null;
                    return;
                }
                if (msg.role === 'assistant' && msg.text === lastReceivedTextLocal) {
                    lastReceivedTextLocal = null;
                    return;
                }
                addMessage(msg.role, msg.text);
            }
        } catch (e) {}
    };
    textWs.onclose = () => {
        setTimeout(connectTextLog, 5000);
    };
}
connectTextLog();
