#!/usr/bin/env python3
"""
Test Discord bot authentication and list accessible servers.
"""
import asyncio
import json
import discord

async def test_discord_bot():
    """Test Discord bot authentication and list accessible servers."""
    
    # Load credentials
    with open('credentials/koii/discord_credentials.json', 'r') as f:
        creds = json.load(f)
    
    bot_token = creds['bot_token']
    
    # Create a simple bot client
    intents = discord.Intents.default()
    intents.guilds = True
    intents.guild_messages = True
    intents.message_content = True
    
    client = discord.Client(intents=intents)
    
    @client.event
    async def on_ready():
        print("=" * 60)
        print("🤖 DISCORD BOT AUTHENTICATION TEST")
        print("=" * 60)
        print(f"✅ Bot logged in as: {client.user}")
        print(f"   User ID: {client.user.id}")
        print()
        
        print(f"📊 Accessible Servers ({len(client.guilds)}):")
        print("-" * 60)
        
        for guild in client.guilds:
            print(f"  • {guild.name}")
            print(f"    Server ID: {guild.id}")
            print(f"    Member count: {guild.member_count}")
            print(f"    Channels: {len(guild.channels)}")
            
            # Check if this matches our configured servers
            if str(guild.id) == "1291943271509135412":
                print(f"    ✅ This is the 'ds' server")
            elif str(guild.id) == "1463083699334549557":
                print(f"    ✅ This is the 'anglds' server")
            else:
                print(f"    ℹ️  Not configured in promaia")
            
            # List some channels
            text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
            if text_channels:
                print(f"    Text channels: {', '.join([c.name for c in text_channels[:5]])}")
                if len(text_channels) > 5:
                    print(f"      ... and {len(text_channels) - 5} more")
            print()
        
        print("=" * 60)
        
        # Check specifically for our configured servers
        configured_servers = {
            "ds": "1291943271509135412",
            "anglds": "1463083699334549557"
        }
        
        print("🔍 Checking configured servers:")
        print("-" * 60)
        for name, server_id in configured_servers.items():
            guild = client.get_guild(int(server_id))
            if guild:
                print(f"  ✅ {name}: Found '{guild.name}'")
            else:
                print(f"  ❌ {name}: Bot not in server (ID: {server_id})")
                print(f"     💡 Add bot to server using invite link:")
                print(f"        https://discord.com/api/oauth2/authorize?client_id={client.user.id}&permissions=68608&scope=bot")
        
        print("=" * 60)
        
        # Close the client
        await client.close()
    
    try:
        await client.start(bot_token)
    except discord.LoginFailure:
        print("❌ Authentication failed!")
        print("   The bot token may be invalid or expired.")
        print("   Please regenerate the token in Discord Developer Portal.")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_discord_bot())
