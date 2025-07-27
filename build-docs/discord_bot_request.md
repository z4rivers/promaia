# Request: Discord Bot for Promaia Integration Demo

Hi Team,

To prepare for our upcoming demo, I need your help setting up a Discord bot. We've successfully developed a new integration for our internal tool, **Promaia**, that allows it to securely sync and understand content from Discord channels.

### Rationale

Promaia is our in-house productivity and AI assistant tool. This new feature allows it to use conversations from key Discord channels as a knowledge source. For the demo, I need to showcase its ability to pull context from our server to answer questions and generate summaries accurately.

The integration uses the official Discord Bot API for **read-only access** to channel messages. It is fully compliant with Discord's Terms of Service and is designed to be secure and unobtrusive.

### Bot Permissions Required

For the integration to function, the bot needs to be configured with the following permissions and privileged intents. These are necessary to view channels, read message history, and resolve author names.

1.  **Privileged Gateway Intents** (To be enabled in the "Bot" section of the Discord Developer Portal):
    *   `SERVER MEMBERS INTENT`: To resolve user IDs to usernames.
    *   `MESSAGE CONTENT INTENT`: To read the content of messages.

2.  **Bot Permissions** (To be set via the OAuth2 Invite URL):
    *   `View Channels`
    *   `Read Message History`

### Channels for Demo Access

For the demo, the bot will need explicit read access to the following channels:

*   **#announcements** ([Link](https://discord.com/channels/1197017602292207666/1197585118148165722))
*   **#release-notes** ([Link](https://discord.com/channels/1197017602292207666/1203844590575296572))
*   **#plush-announcements** ([Link](https://discord.com/channels/1197017602292207666/1257791479460397177))

### Action Required

Could you please create a new bot, configure it with the permissions above, and invite it to our server?

Once created, please securely share the **Bot Token** with me so I can configure it in Promaia.

This is a key requirement for a successful demo. Thank you for your help! 