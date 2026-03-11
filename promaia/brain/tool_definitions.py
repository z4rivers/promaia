# 11.5 Tool Definitions for Staging and Committing Memories
memory_tools = {
    "function_declarations": [
        {
            "name": "save_conversation_memory",
            "description": "Stage a memory for significant decisions, facts, or commitments. Write the summary from the USER's perspective (e.g. 'Zack decided...' not 'I noted...'). Do NOT call for casual chat, greetings, or filler.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "summary": { "type": "STRING", "description": "Concise summary of fact/decision" },
                    "memory_type": { "type": "STRING", "description": "profile_update, project_decision, action_item" }
                },
                "required": ["summary", "memory_type"]
            }
        },
        {
            "name": "commit_staged_memories",
            "description": "Call this ONLY AFTER you have read the staged memories aloud to the user and they have verbally confirmed they are correct and should be saved.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "confirmation_note": { "type": "STRING", "description": "A brief note on what the user said to confirm (e.g. 'User said exactly')" }
                },
                "required": ["confirmation_note"]
            }
        },
        {
            "name": "create_calendar_event",
            "description": "Schedule a new event or reminder on Zack's calendar. ALWAYS verbally confirm details before calling.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "summary": { "type": "STRING", "description": "Event title/summary" },
                    "description": { "type": "STRING", "description": "Event description (optional)" },
                    "start_time": { "type": "STRING", "description": "Start time (ISO 8601 format: 2026-03-10T14:00:00)" },
                    "end_time": { "type": "STRING", "description": "End time (ISO 8601 format: 2026-03-10T15:00:00)" }
                },
                "required": ["summary", "start_time", "end_time"]
            }
        },
        {
            "name": "delete_calendar_event",
            "description": "Delete an event from Zack's calendar by searching for it. ALWAYS verbally confirm which event to delete before calling.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "summary": { "type": "STRING", "description": "Event title/summary to search for (partial match)" },
                    "date": { "type": "STRING", "description": "Date of the event (YYYY-MM-DD)" }
                },
                "required": ["summary"]
            }
        },
        {
            "name": "send_email_draft",
            "description": "Create an email draft in the Promaia Dashboard based on user's request. ALWAYS verbally confirm before calling.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "to": { "type": "STRING", "description": "Recipient email address" },
                    "subject": { "type": "STRING", "description": "Email subject" },
                    "body": { "type": "STRING", "description": "Email body text" }
                },
                "required": ["to", "subject", "body"]
            }
        },
        {
            "name": "switch_cognitive_mode",
            "description": "Switch your thinking style based on natural user cues. Call this when the user asks you to: think critically / play devil's advocate / poke holes / what could go wrong (-> critical mode); brainstorm / wild ideas / what else could we try (-> creative mode); just the facts / what do we actually know (-> facts mode); what's your gut say / forget the logic (-> instinct mode); what's the upside / make the case for it (-> optimist mode); step back / help me think through this / big picture (-> process mode). NEVER mention mode names or thinking styles to the user.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "hat_color": { "type": "STRING", "description": "critical, creative, instinct, facts, optimist, or process" }
                },
                "required": ["hat_color"]
            }
        },
        {
            "name": "hang_up_call",
            "description": "End the current voice call and hang up the connection. Use this ONLY when Zack explicitly says 'hang up', 'goodbye', 'end call', etc. Say your goodbye FIRST, then call this tool."
        },
        {
            "name": "log_system_feedback",
            "description": "Log a bug report, behavior correction, or system feature request directly to the developer codebase. Call this IMMEDIATELY whenever Zack gives feedback on your performance, complains about the app, or suggests an improvement.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "feedback": { "type": "STRING", "description": "The exact complaint, bug, or feedback Zack provided." }
                },
                "required": ["feedback"]
            }
        },
        {
            "name": "create_action",
            "description": "Create a new action item or reminder for Zack. Requires title, optional due date, and domain.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "description": { "type": "STRING", "description": "Action item description/title" },
                    "due_date": { "type": "STRING", "description": "Due date (e.g. YYYY-MM-DD) or 'ASAP' (optional)" },
                    "domain": { "type": "STRING", "description": "Domain/project (e.g. 'heatpup', 'promaia', 'personal')" }
                },
                "required": ["description", "domain"]
            }
        },
        {
            "name": "recall_memory",
            "description": "Recall specific facts or context from MuninnDB based on a semantic search query.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query": { "type": "STRING", "description": "The concept or fact you are trying to remember." }
                },
                "required": ["query"]
            }
        }
    ]
}
