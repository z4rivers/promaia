import re

def refactor_js():
    with open(r"promaia\web\static\js\talk.src.js", "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Replace the top declaration block
    old_state_block = """let vad = null;
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
let lastReceivedTextLocal = null;"""

    new_state_block = """const VoiceSessionState = {
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
};"""
    content = content.replace(old_state_block, new_state_block)

    # 2. Replace audio decode logic in queuePlayback
    old_audio_decode = """    // Decode Base64 to Int16 to Float32
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
    }"""
    
    new_audio_decode = """    // Decode Base64 to Int16 to Float32 using pure helper
    const float32 = AudioProcessingUtils.base64ToFloat32Pcm(base64Data);"""
    content = content.replace(old_audio_decode, new_audio_decode)

    # 3. Replace audio encode logic in captureScriptNode.onaudioprocess
    old_audio_encode = """        const float32Array = e.inputBuffer.getChannelData(0);
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
        const b64 = window.btoa(binary);"""
        
    new_audio_encode = """        const float32Array = e.inputBuffer.getChannelData(0);
        // Convert Float32 to Int16 to Base64 using pure helper
        const b64 = AudioProcessingUtils.float32ToBase64Pcm(float32Array);"""
    content = content.replace(old_audio_encode, new_audio_encode)
    
    # 4. Replace variable bindings (be careful of word boundaries)
    vars_to_replace = [
        "vad", "conversationMode", "ws", "captureStream", "captureCtx", 
        "captureScriptNode", "playCtx", "nextPlayTime", "playingNodes", 
        "wakeLock", "textWs", "lastSentTextLocal", "lastReceivedTextLocal"
    ]
    
    for var in vars_to_replace:
        # Regex replaces the word bounded by non-words (excluding properties that have dots or are object keys like obj.vad: )
        # To avoid replacing currentVadMode or similar string constants, we use \b
        # Also care for `window.vad` - if there is `window.` we shouldn't touch it.
        # Also care for `let var` which we removed.
        content = re.sub(r'(?<!\.)\b' + var + r'\b(?!:)', "VoiceSessionState." + var, content)

    # Re-fix currentVoiceSessionState.vadMode -> currentVadMode just in case (vadMode wasn't in the list tho). Wait, what if we have some string logs?
    # e.g. "playCtx" ? `VoiceSessionState.playCtx` inside a string is fine.

    with open(r"promaia\web\static\js\talk.src.js", "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    refactor_js()
