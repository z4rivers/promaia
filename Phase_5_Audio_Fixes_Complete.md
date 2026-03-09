Phase 5 Audio Fixes: Complete Technical Summary
1. Audio In (Speech Detection) Fixes
The Problem: The VAD (Voice Activity Detection) ONNX WASM backend was failing to initialize with a 404 Not Found error. The Root Cause: The Railway production environment serves static assets from promaia/web/static. The VAD library (@ricky0123/vad-web) expects its 

.onnx
 and 

.wasm
 model files to be explicitly available at runtime, but esbuild was ignoring these binary files during the bundling step. The Fix:

Updated 

esbuild.config.mjs
 with a new copyFileSync task that runs before the bundler begins.
It dynamically looks up node_modules/@ricky0123/vad-web/dist/ and node_modules/onnxruntime-web/dist/.
It copies silero_vad.onnx, 

ort-wasm-simd-threaded.mjs
, and 

.wasm
 directly into the promaia/web/static/vad/ directory.
This satisfies the Silero ONNX runtime environment and allows the microphone to instantiate perfectly across cloud environments.
2. Audio Out (TTS Synthesis) Fixes
The Problem: The /api/brain/tts endpoint was consistently throwing 500 Internal Server Errors, and even when unblocked, the Chrome browser refused to play the audio buffer with a NotSupportedError: Failed to load because no supported source was found. The Root Cause:

The 500 Error: The backend 

brain.py
 endpoint was calling gemini-2.5-flash-preview-tts using an aggressive multimodal config object (containing speech_config) that triggered an INVALID_ARGUMENT exception on Google's new Python SDK.
The NotSupportedError: HTML5 <audio> tags natively play MP3, OGG, and WAV. When the Gemini SDK successfully returns TTS bytes, it does not return a WAV file. It returns a pure, headerless audio/L16;codec=pcm;rate=24000 data structure. Browsers cannot parse or play raw PCM bits out of the box. The Fix:
Simplified the client.aio.models.generate_content call to drop the nested speech_config while preserving response_modalities=["AUDIO"].
Checked GOOGLE_MODELS inside 

models.py
 to ensure the correct 

tts
 key mapped to gemini-2.5-flash-preview-tts.
Built a Python-native transcoder inside 

brain.py
 using 

io
 and wave.
When the backend detects an audio/L16 MIME type return from Gemini, it instantiates an empty IO buffer, writes a standard RIFF/WAV header (1 Channel, 16-bit, 24000Hz), injects the raw PCM bits, and returns it to the client as a clean, browser-compliant audio/wav blob.