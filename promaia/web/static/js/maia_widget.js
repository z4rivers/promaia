/**
 * maia_widget.js
 * Frontend client for the Maia Web Bridge.
 * Connects to /api/brain/maia_stream via WebSockets.
 */

document.addEventListener('DOMContentLoaded', () => {
    const chatInput = document.getElementById('maia-chat-input');
    const sendBtn = document.getElementById('maia-send-btn');
    const sessionFeed = document.getElementById('maia-session-feed');
    const statusLabel = document.getElementById('maia-status-label');
    
    let ws = null;

    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${protocol}//${window.location.host}/api/brain/maia_stream`);
        
        ws.onopen = () => {
            console.log("Maia Widget Engine: Connected");
            updateStatus("Connected to Engine", "idle");
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === "activity") {
                    appendFeedItem(data.text, "activity");
                    updateStatus(data.text, "working");
                } else if (data.type === "response") {
                    appendFeedItem(data.text, "response");
                    updateStatus("Idle", "idle");
                }
            } catch (e) {
                console.error("Error parsing maia message", e);
            }
        };

        ws.onclose = () => {
            console.log("Maia Widget Engine: Disconnected");
            updateStatus("Disconnected", "error");
            setTimeout(connectWebSocket, 5000); // Auto-reconnect
        };
    }

    function updateStatus(text, state) {
        if (statusLabel) {
            statusLabel.textContent = text;
            statusLabel.dataset.state = state;
        }
    }

    function appendFeedItem(text, type) {
        if (!sessionFeed) return;
        
        // Auto-expand the details block if activity occurs
        const detailsBlock = document.getElementById('maia-widget-details');
        if (detailsBlock && !detailsBlock.open) {
            detailsBlock.open = true;
        }

        const div = document.createElement('div');
        div.className = `maia-feed-item maia-feed-item--${type}`;
        
        const timestamp = new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute:'2-digit', second:'2-digit' });
        
        let icon = "⚡";
        if (type === "user") icon = "👤";
        if (type === "response") icon = "🧠";
        if (type === "activity") icon = "⚙️";
        
        div.innerHTML = `
            <span class="maia-feed-time">[${timestamp}]</span> 
            <span class="maia-feed-icon">${icon}</span> 
            <span class="maia-feed-text">${escapeHtml(text)}</span>
        `;
        
        sessionFeed.appendChild(div);
        sessionFeed.scrollTop = sessionFeed.scrollHeight;
    }

    function escapeHtml(unsafe) {
        return (unsafe || '').toString()
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }

    function sendMessage() {
        if (!chatInput || !ws || ws.readyState !== WebSocket.OPEN) return;
        const text = chatInput.value.trim();
        if (!text) return;
        
        appendFeedItem(text, "user");
        ws.send(JSON.stringify({ message: text }));
        chatInput.value = '';
    }

    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }

    if (chatInput) {
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    }

    // Initialize connection
    connectWebSocket();
});
