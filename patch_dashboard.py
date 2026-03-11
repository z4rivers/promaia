import sys

with open(r"promaia\web\templates\dashboard.html", "r", encoding="utf-8") as f:
    content = f.read()

CSS_INJECTION = """    /* === VOICE OVERLAY === */
    .dashboard {
        padding-bottom: 140px; /* space for fixed mic button */
        transition: opacity 300ms ease, filter 300ms ease;
    }
    .dashboard.dimmed {
        opacity: 0.15;
        filter: blur(4px);
        pointer-events: none;
    }

    /* === Conversation Area (Overlay on dashboard) === */
    .talk-conversation {
        position: fixed;
        bottom: 140px;
        left: 50%;
        transform: translateX(-50%);
        width: 100%;
        max-width: var(--page-max-width, 1120px);
        max-height: 50vh;
        z-index: 45;
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
        pointer-events: none; /* Let clicks pass through to dashboard when empty */
    }
    
    #messages {
        pointer-events: none;
        max-height: 100%;
        overflow-y: auto;
        padding: 0 var(--page-pad-x, 16px);
        display: flex;
        flex-direction: column;
        margin-top: auto;
    }

    .talk-msg {
        pointer-events: auto; /* Catch clicks on messages */
        padding: 10px 16px;
        margin-bottom: 8px;
        border-radius: var(--card-radius, 8px);
        font-size: 0.9rem;
        line-height: 1.5;
        animation: pop-in 200ms ease both;
        max-width: 90%;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        flex-shrink: 0;
    }
    @keyframes pop-in {
        0% { opacity: 0; transform: translateY(10px) scale(0.98); }
        100% { opacity: 1; transform: translateY(0) scale(1); }
    }
    .talk-msg--user {
        background: var(--bg-card);
        border: var(--card-border, 1px solid var(--border-subtle));
        color: var(--text-primary);
        margin-left: auto;
        text-align: right;
    }
    .talk-msg--assistant {
        background: var(--bg-card);
        border: 2px solid var(--accent-primary, #FF3366);
        color: var(--text-primary);
        margin-right: auto;
    }
    .talk-msg-label {
        font-family: var(--font-mono);
        font-size: 0.6rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--text-muted);
        margin-bottom: 4px;
    }

    /* === Status Indicator === */
    .talk-status {
        position: fixed;
        top: var(--space-lg, 24px);
        left: 0;
        right: 0;
        text-align: center;
        z-index: 50;
        pointer-events: none;
    }
    .talk-status-label {
        display: inline-block;
        font-family: var(--font-display, var(--font-heading));
        font-size: 1.2rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        padding: 6px 16px;
        border-radius: 20px;
        background: var(--bg-card);
        color: var(--text-muted);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        transition: color 200ms ease;
    }
    .talk-status-label[data-state="idle"] { display: none; }
    .talk-status-label[data-state="listening"] { color: var(--accent-primary, #FF3366); }
    .talk-status-label[data-state="thinking"] { color: var(--accent-info, #8B00FF); }
    .talk-status-label[data-state="speaking"] { color: var(--accent-success, #00CC88); }
    .talk-status-label[data-state="error"] { color: var(--accent-warning, #FFE700); }

    /* Pulse animation for listening state */
    @keyframes status-pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    .talk-status-label[data-state="listening"],
    .talk-status-label[data-state="thinking"] {
        animation: status-pulse 1.5s ease-in-out infinite;
    }

    /* === Mic Button: MASSIVE, fixed at bottom center === */
    .talk-mic-area {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 16px;
        padding: 20px 20px 32px 20px;
        background: linear-gradient(transparent, var(--bg-primary, #fff) 60%);
        z-index: 50;
    }

    .talk-mic-btn {
        width: 80px;
        height: 80px;
        border-radius: 50%;
        border: 3px solid var(--border-visible, #1A1A2E);
        background: var(--bg-card, #fff);
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 200ms ease;
        flex-shrink: 0;
        touch-action: manipulation;
    }
    .talk-mic-btn svg {
        width: 36px;
        height: 36px;
        fill: var(--text-primary, #1A1A2E);
        transition: fill 200ms ease;
    }
    .talk-mic-btn:hover {
        border-color: var(--accent-primary, #FF3366);
        transform: scale(1.05);
    }
    .talk-mic-btn:active {
        transform: scale(0.95);
    }
    .talk-mic-btn.active {
        background: var(--accent-primary, #FF3366);
        border-color: var(--accent-primary, #FF3366);
    }
    .talk-mic-btn.active svg {
        fill: #FFFFFF;
    }

    @keyframes mic-pulse {
        0% { box-shadow: 0 0 0 0 rgba(255, 51, 102, 0.4); }
        70% { box-shadow: 0 0 0 20px rgba(255, 51, 102, 0); }
        100% { box-shadow: 0 0 0 0 rgba(255, 51, 102, 0); }
    }
    .talk-mic-btn.active {
        animation: mic-pulse 2s ease-out infinite;
    }

    .talk-kb-btn, .talk-end-btn {
        width: 44px;
        height: 44px;
        border-radius: 50%;
        border: 2px solid var(--border-subtle, #E0E0E8);
        background: var(--bg-card, #fff);
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 150ms ease;
        touch-action: manipulation;
    }
    .talk-kb-btn svg, .talk-end-btn svg {
        width: 20px;
        height: 20px;
        fill: var(--text-muted, #888);
    }
    .talk-kb-btn:hover, .talk-end-btn:hover {
        border-color: var(--accent-primary);
    }
    
    .talk-end-btn { display: none; }
    .talk-end-btn.visible {
        display: flex;
        border-color: var(--accent-primary, #FF3366);
    }
    .talk-end-btn.visible svg {
        fill: var(--accent-primary, #FF3366);
    }

    .vad-toggle-wrapper {
        position: absolute;
        top: -40px;
        left: 50%;
        transform: translateX(-50%);
        background: var(--bg-card, #fff);
        border: 1px solid var(--border-subtle, #E0E0E8);
        border-radius: 20px;
        padding: 4px;
        display: flex;
        gap: 4px;
        z-index: 52;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    .vad-mode-btn {
        background: transparent;
        border: none;
        padding: 4px 12px;
        border-radius: 14px;
        font-family: 'Outfit', sans-serif;
        font-size: 12px;
        font-weight: 600;
        color: var(--text-muted, #888);
        cursor: pointer;
        transition: all 150ms ease;
    }
    .vad-mode-btn.active {
        background: var(--text-primary, #1A1A2E);
        color: #fff;
    }

    .talk-text-bar {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        display: none;
        padding: 12px 16px 28px 16px;
        background: var(--bg-primary, #fff);
        border-top: 2px solid var(--border-visible, #1A1A2E);
        z-index: 51;
        gap: 8px;
        align-items: center;
    }
    .talk-text-bar.visible { display: flex; }
    .talk-text-bar input {
        flex: 1;
        font-family: var(--font-body);
        font-size: 1rem;
        padding: 10px 14px;
        border: 2px solid var(--border-visible, #1A1A2E);
        border-radius: var(--card-radius, 8px);
        background: var(--bg-card, #fff);
        color: var(--text-primary);
        outline: none;
    }
    .talk-text-bar input:focus { border-color: var(--accent-primary, #FF3366); }
    .talk-text-bar button {
        font-family: var(--font-heading);
        font-weight: 700;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        padding: 10px 18px;
        background: var(--accent-primary, #FF3366);
        color: #fff;
        border: 2px solid var(--accent-primary, #FF3366);
        border-radius: var(--card-radius, 8px);
        cursor: pointer;
    }
    .talk-text-bar .close-kb {
        background: transparent;
        border: none;
        color: var(--text-muted);
        font-size: 1.2rem;
        cursor: pointer;
        padding: 8px;
    }
    @media (max-width: 480px) {
        .talk-mic-btn { width: 72px; height: 72px; }
        .talk-mic-btn svg { width: 32px; height: 32px; }
    }
"""

content = content.replace("</style>", CSS_INJECTION + "\n</style>")

# Replace <main class="dashboard"> with id="feeds"
content = content.replace('<main class="dashboard">', '<main class="dashboard" id="feeds">')

# Append UI after main
HTML_INJECTION = """
<!-- Voice Overlay UI -->
<div class="talk-status">
    <div class="talk-status-label" id="talk-status" data-state="idle">Ready</div>
</div>

<section class="talk-conversation" id="conversation">
    <div id="messages"></div>
</section>

<!-- Fixed Mic Button Area -->
<div class="talk-mic-area" id="mic-area">
    <div class="vad-toggle-wrapper" id="vad-toggle">
        <button class="vad-mode-btn active" data-mode="normal">Quiet</button>
        <button class="vad-mode-btn" data-mode="driving">Driving</button>
    </div>

    <button class="talk-kb-btn" id="kb-toggle" title="Type instead">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M20 5H4c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm-9 3h2v2h-2V8zm0 3h2v2h-2v-2zM8 8h2v2H8V8zm0 3h2v2H8v-2zm-1 2H5v-2h2v2zm0-3H5V8h2v2zm9 7H8v-2h8v2zm0-4h-2v-2h2v2zm0-3h-2V8h2v2zm3 3h-2v-2h2v2zm0-3h-2V8h2v2z"/>
        </svg>
    </button>
    
    <button class="talk-mic-btn" id="mic-btn" title="Tap to Start">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V5zm6 6c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
        </svg>
    </button>
    
    <button class="talk-end-btn" id="end-btn" title="End Call">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 9c-1.6 0-3.15.25-4.6.72v3.1c0 .39-.23.74-.56.9-.98.49-1.87 1.12-2.66 1.85-.18.18-.43.28-.7.28-.28 0-.53-.11-.71-.29L.29 13.08c-.18-.17-.29-.42-.29-.7 0-.28.11-.53.29-.71C3.34 8.78 7.46 7 12 7s8.66 1.78 11.71 4.67c.18.18.29.43.29.71 0 .28-.11.53-.29.71l-2.48 2.48c-.18.18-.43.29-.71.29-.27 0-.52-.11-.7-.28-.79-.74-1.69-1.36-2.67-1.85-.33-.16-.56-.5-.56-.9v-3.1C15.15 9.25 13.6 9 12 9z"/>
        </svg>
    </button>
</div>

<!-- Text Input Bar (hidden by default) -->
<div class="talk-text-bar" id="text-bar">
    <button class="close-kb" id="close-kb" title="Back to voice">&times;</button>
    <input type="text" id="text-field" placeholder="Type a message..." autocomplete="off">
    <button id="send-btn">Send</button>
</div>
"""

content = content.replace('</main>', '</main>\n' + HTML_INJECTION)

JS_INJECTION = """
    <!-- CDN VAD Scripts -->
    <script src="https://cdn.jsdelivr.net/npm/onnxruntime-web@1.14.0/dist/ort.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.0.7/dist/bundle.min.js"></script>
    <!-- Main Application Logic -->
    <script src="/static/js/talk.js?v=2.5"></script>
"""

content = content.replace('{% block scripts %}\n{{ super() }}', '{% block scripts %}\n{{ super() }}' + JS_INJECTION)

with open(r"promaia\web\templates\dashboard.html", "w", encoding="utf-8") as f:
    f.write(content)
