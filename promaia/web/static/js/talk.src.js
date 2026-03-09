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
        // Gemini standard TTS format is 24000Hz PCM
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
    captureCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
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
    if (captureScriptNode) {
        captureScriptNode.disconnect();
        captureScriptNode = null;
    }
    if (captureCtx) {
        captureCtx.close();
        captureCtx = null;
    }
    if (captureStream) {
        captureStream.getTracks().forEach(t => t.stop());
        captureStream = null;
    }
}

// ---------------------------------------------------------------------------
// VAD initialization (Used purely for UI State and Interruptions)
// ---------------------------------------------------------------------------
async function initVAD() {
    // CDN injects the library into the global window.vad object
    if (!window.vad || !window.vad.MicVAD) {
        throw new Error("VAD library not loaded from CDN yet.");
    }

    vad = await window.vad.MicVAD.new({
        // By removing custom paths, vad-web fetches models natively from unpkg
        positiveSpeechThreshold: 0.8,
        negativeSpeechThreshold: 0.5,
        redemptionFrames: 6,
        minSpeechFrames: 4,
        preSpeechPadFrames: 3,

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
    feedsEl.classList.add('dimmed');
    setStatus('connecting');

    try {
        console.log("Starting conversation sequence...");
        await connectWebSocket();
        console.log("WS connected. Init VAD...");
        if (!vad) await initVAD();
        console.log("VAD Init'd. Starting capture...");
        await startCapture();
        console.log("Capture started. Starting VAD...");
        vad.start();
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
    feedsEl.classList.remove('dimmed');
    setStatus('idle');
    
    stopPlayback();
    stopCapture();
    if (vad) vad.pause();
    
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
    }
}

// ---------------------------------------------------------------------------
// Text input (Direct text push through WebSocket)
// ---------------------------------------------------------------------------
function sendText(text) {
    if (!text.trim()) return;
    addMessage('user', text);
    setStatus('thinking');

    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ 
            clientContent: { 
                turns: [{ role: "user", parts: [{ text: text }] }],
                turnComplete: true 
            } 
        }));
    } else {
        addMessage('assistant', '(Disconnected — tap mic to connect first)');
        setStatus('idle');
    }
}

// ---------------------------------------------------------------------------
// Event listeners
// ---------------------------------------------------------------------------
micBtn.addEventListener('click', () => {
    if (navigator.vibrate) navigator.vibrate(50);
    if (!conversationMode) {
        startConversation();
    } else {
        stopConversation();
    }
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

// Avoid iOS background loops
document.addEventListener('visibilitychange', () => {
    if (document.hidden && conversationMode) {
        stopConversation();
    }
});
