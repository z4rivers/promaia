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
    let currentRoomId = 1;

    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${protocol}//${window.location.host}/api/brain/maia_stream?room_id=${currentRoomId}`);
        
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
        
        const div = document.createElement('div');
        div.className = `maia-feed-item maia-feed-item--${type}`;
        
        const timestamp = new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute:'2-digit', second:'2-digit' });
        
        let icon = "⚡";
        if (type === "user") icon = "👤";
        if (type === "response") icon = "💎";
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
            formData.append("room_id", currentRoomId);
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

    async function fetchCommitteeRooms() {
        try {
            const resp = await fetch('/api/brain/rooms');
            const data = await resp.json();
            const grid = document.getElementById('committee-rooms-grid');
            if (!grid) return;
            
            grid.innerHTML = '';
            
            const rooms = data.rooms || [];
            const topicRooms = rooms.filter(r => r.id !== 1);
            
            if (topicRooms.length === 0) {
                grid.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem; font-style: italic;" id="no-rooms-placeholder">No active topic rooms.</div>';
                return;
            }

            for (const room of topicRooms) {
                const card = document.createElement('div');
                card.className = 'card';
                card.style.display = 'flex';
                card.style.flexDirection = 'column';
                card.style.gap = '8px';
                
                // Fetch members
                let membersHtml = '';
                try {
                    const mResp = await fetch(`/api/brain/rooms/${room.id}/members`);
                    const mData = await mResp.json();
                    if (mData.members) {
                        membersHtml = mData.members.map(m => {
                            // "online" => active, "idle" => yellow, "offline" => none
                            let color = 'var(--text-muted)';
                            let badgeClass = 'action-indicator';
                            if (m.current_status === 'online') badgeClass += ' action-indicator--active';
                            else if (m.current_status === 'idle') { badgeClass += ' action-indicator--active'; color = '#fbbf24'; }
                            return `<span style="display:flex; align-items:center; gap:4px; font-size:0.75rem; color:var(--text-muted);"><span class="${badgeClass}" style="margin-top:0; ${m.current_status === 'idle' ? 'background:#fbbf24;' : ''}"></span>${escapeHtml(m.agent_name)}</span>`;
                        }).join('');
                    }
                } catch(e) { console.error(e); }

                card.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; cursor: pointer;" class="room-enter-zone">
                        <div>
                            <div class="project-name">${escapeHtml(room.name)}</div>
                            <div class="project-detail" style="font-family: var(--font-mono); font-size: 0.7rem; color: var(--text-muted); margin-top: 4px;">${escapeHtml(room.topic || 'No topic')}</div>
                        </div>
                    </div>
                    <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 4px;">
                        ${membersHtml || '<span style="font-size:0.75rem; color:var(--text-muted);">Empty</span>'}
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-top: auto; padding-top: 8px; border-top: 1px solid var(--border-subtle);">
                        <button class="btn btn--secondary room-invite-btn" style="padding: 2px 8px; font-size: 0.7rem;">+ Invite</button>
                        <button class="btn btn--secondary room-dissolve-btn" style="padding: 2px 8px; font-size: 0.7rem; color: var(--color-danger); border-color: transparent;">Dissolve</button>
                    </div>
                `;
                
                // Interactive parts
                card.querySelector('.room-enter-zone').addEventListener('click', () => {
                   enterTopicRoom(room);
                });
                card.querySelector('.room-invite-btn').addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const nameToInvite = prompt("Agent name to summon (e.g. 'claude-code', 'maia', 'zack'):");
                    if (!nameToInvite) return;
                    try {
                        const sResp = await fetch(`/api/brain/rooms/${room.id}/summon`, {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({agent_name: nameToInvite, role: 'member'})
                        });
                        if(sResp.ok) fetchCommitteeRooms();
                    } catch(e) {}
                });
                card.querySelector('.room-dissolve-btn').addEventListener('click', async (e) => {
                    e.stopPropagation();
                    if(!confirm(`Are you sure you want to dissolve '${room.name}'?`)) return;
                    try {
                        const dResp = await fetch(`/api/brain/rooms/${room.id}/dissolve`, {method: 'POST'});
                        if(dResp.ok) fetchCommitteeRooms();
                    } catch(e) {}
                });

                grid.appendChild(card);
            }
            
        } catch (e) {
            console.error("Failed to fetch rooms", e);
        }
    }

    async function enterTopicRoom(room) {
        if (currentRoomId === room.id) return;
        currentRoomId = room.id;
        
        // Update Title UI
        const mainTitle = document.getElementById('main-room-title');
        if (mainTitle) {
            mainTitle.innerHTML = `<span style="color:var(--text-muted); font-weight:normal; font-size:0.8em; cursor:pointer;" onclick="window.enterTopicRoom({id:1, name:'Maia Chat', topic:''})">← Maia Chat</span> &nbsp; ${escapeHtml(room.name)}`;
        }
        
        // Members UI
        const mainMembers = document.getElementById('main-room-members');
        if (mainMembers) {
            let membersHtml = '';
            try {
                const mResp = await fetch(`/api/brain/rooms/${room.id}/members`);
                const mData = await mResp.json();
                if (mData.members) {
                    membersHtml = mData.members.map(m => {
                        let badgeClass = 'action-indicator';
                        let bgStyle = '';
                        if (m.current_status === 'online') badgeClass += ' action-indicator--active';
                        else if (m.current_status === 'idle') { badgeClass += ' action-indicator--active'; bgStyle = 'background:#fbbf24;'; }
                        return `<span style="display:flex; align-items:center; gap:4px;"><span class="${badgeClass}" style="margin-top:0; ${bgStyle}"></span>${escapeHtml(m.agent_name)}</span>`;
                    }).join('');
                }
            } catch(e) {}
            mainMembers.innerHTML = membersHtml;
        }

        // Fetch History
        if (sessionFeed) {
            sessionFeed.innerHTML = '<div style="color:var(--text-muted); font-size:0.8rem; text-align:center; margin:16px;">Loading room history...</div>';
            try {
                const hResp = await fetch(`/api/brain/rooms/${room.id}/messages`);
                const hData = await hResp.json();
                sessionFeed.innerHTML = '';
                if (hData.messages && hData.messages.length > 0) {
                    hData.messages.forEach(m => {
                        appendFeedItem(m.body, m.from_agent === 'zack' ? 'user' : 'response');
                    });
                } else {
                    sessionFeed.innerHTML = '<div style="color:var(--text-muted); font-size:0.8rem; text-align:center; margin:16px;">Room created. Use chat to begin.</div>';
                }
            } catch(e) {
                console.error(e);
                sessionFeed.innerHTML = '';
            }
        }
        
        // Reconnect WS
        if (ws) {
            ws.onclose = null; // Prevent auto-reconnect fallback triggering immediately
            ws.close();
        }
        connectWebSocket();
    }
    window.enterTopicRoom = enterTopicRoom; // expose for the "<- Main Room" click

    const newRoomBtn = document.getElementById('new-room-btn');
    if (newRoomBtn) {
        newRoomBtn.addEventListener('click', async () => {
            const name = prompt("Topic Room Name (e.g., 'Routing Refix'):");
            if (!name) return;
            const topic = prompt("Topic Description:");
            try {
                const resp = await fetch('/api/brain/rooms', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        name: name,
                        topic: topic || "Focus session",
                        created_by: "zack"
                    })
                });
                if (resp.ok) fetchCommitteeRooms();
            } catch (e) {
                console.error("Failed to create room", e);
            }
        });
    }

    // Initialize connection
    fetchCommitteeRooms();
    connectWebSocket();
});
