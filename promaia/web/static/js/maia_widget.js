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
    const uploadBtn = document.getElementById('maia-upload-btn');
    const mediaUpload = document.getElementById('maia-media-upload');
    const attachmentsPreview = document.getElementById('maia-attachments-preview');
    
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
        const files = mediaUpload ? mediaUpload.files : [];
        if (!text && files.length === 0) return;
        
        appendFeedItem(files.length > 0 ? `${text} [${files.length} attachments]` : text, "user");
        
        // HYBRID ARCHITECTURE: 
        // If there are files attached, we send out-of-band via HTTP POST so we don't crash the websocket payload limit.
        if (files.length > 0) {
            updateStatus("Uploading media...", "working");
            const formData = new FormData();
            formData.append("message", text || "Attached media");
            for(let i = 0; i < files.length; i++) {
                formData.append("files", files[i]);
            }
            
            fetch('/api/brain/capture_multimodal', {
                method: 'POST',
                body: formData
            }).then(resp => {
                if (!resp.ok) console.error("Media upload failed", resp);
            }).catch(e => console.error("Fetch media upload error", e))
            .finally(() => {
                // The websocket will broadcast the response, we just reset the input
                chatInput.value = '';
                if(mediaUpload) mediaUpload.value = '';
                if(attachmentsPreview) {
                    attachmentsPreview.innerHTML = '';
                    attachmentsPreview.style.display = 'none';
                }
            });
        } else {
            // Standard WebSocket delivery for lightweight text
            ws.send(JSON.stringify({ message: text }));
            chatInput.value = '';
        }
    }

    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }

    if (chatInput) {
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    // Attach functionality for media upload button
    if (uploadBtn && mediaUpload) {
        uploadBtn.addEventListener('click', () => mediaUpload.click());
        mediaUpload.addEventListener('change', () => {
             if (!attachmentsPreview) return;
             attachmentsPreview.innerHTML = '';
             if (mediaUpload.files.length > 0) {
                 attachmentsPreview.style.display = 'flex';
                 for(let i=0; i < mediaUpload.files.length; i++){
                    const file = mediaUpload.files[i];
                    const objUrl = URL.createObjectURL(file);
                    const div = document.createElement('div');
                    div.style.cssText = "background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 4px; padding: 4px; font-size: 0.75rem; display: flex; align-items: center; gap: 4px;";
                    if (file.type.startsWith('image/')) {
                         div.innerHTML = `<img src="${objUrl}" style="height:24px; width:24px; object-fit:cover; border-radius:2px;"> <span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:80px;">${file.name}</span>`;
                    } else if (file.type.startsWith('audio/')) {
                         div.innerHTML = `🎵 <span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:80px;">${file.name}</span>`;
                    } else {
                         div.innerHTML = `📄 <span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:80px;">${file.name}</span>`;
                    }
                    attachmentsPreview.appendChild(div);
                 }
             } else {
                 attachmentsPreview.style.display = 'none';
             }
        });
    }

    // Initialize connection
    connectWebSocket();
});
