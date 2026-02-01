import os
import discord
import requests
from discord.ext import commands, tasks
import datetime
import asyncio

# ------------------------------------------------------------------------------------
# --- CONFIGURATION ---
# ------------------------------------------------------------------------------------
BOT_TOKEN = "" ## Bot token from discord
MONITOR_CHANNEL_ID =  ## Channel ID where you want it to post in discord  
GAME_KEYWORDS = [""] ## Game Keywords
CHECK_INTERVAL_SECONDS = 30 ## Default is 30 seconds and it is recommended
# ------------------------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix='!', intents=intents)

# Structure: { game_id: { "message": MessageObj, "last_data": dict } }
announced_games = {}

def get_timestamp():
    return f"<t:{int(datetime.datetime.now().timestamp())}:R>"

@bot.event
async def on_ready():
    print(f"\n[{datetime.datetime.now()}] {bot.user.name} is online and connected.")
    
    # --- SMART RECOVERY: Find orphaned messages from before the restart ---
    channel = bot.get_channel(MONITOR_CHANNEL_ID)
    if channel:
        print(f"[{datetime.datetime.now()}] Recovering state from channel history...")
        async for msg in channel.history(limit=20):
            # Adopt active messages
            if msg.author == bot.user and "A LOAP is being hosted!" in msg.content:
                # Try to extract ID from footer "ID: 12345"
                for line in msg.content.split('\n'):
                    if "ID: " in line:
                        try:
                            game_id = int(line.split("ID: ")[1].strip())
                            # Re-construct basic data so the bot knows what this is
                            announced_games[game_id] = {
                                "message": msg,
                                "last_data": {
                                    "name": "Recovered Game", 
                                    "host": "Unknown", 
                                    "slots": "Unknown"
                                }
                            }
                            print(f" > Recovered active game from history. ID: {game_id}")
                        except:
                            pass
    
    if not monitor_game_lobbies.is_running():
        monitor_game_lobbies.start()

@tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
async def monitor_game_lobbies():
    print(f"\n[{datetime.datetime.now()}] DEBUG: Running scheduled check...")
    global announced_games
    
    api_url = "https://api.wc3stats.com/gamelist"
    channel = bot.get_channel(MONITOR_CHANNEL_ID)
    if not channel: 
        print("ERROR: Monitor channel not found.")
        return

    # --- Step 1: Fetch API Data ---
    current_hosted_games = {}
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        api_data = response.json()

        for game in api_data.get("body", []):
            game_name = game.get("name", "")
            if any(k.lower() in game_name.lower() for k in GAME_KEYWORDS):
                players = game.get("slotsTaken", 0)
                game_id = game.get("id")
                
                if game_id is not None and players > 0:
                    current_hosted_games[game_id] = {
                        "name": game_name,
                        "host": game.get("host", "Unknown"),
                        "slots": f"{players} / {game.get('slotsTotal', 0)}",
                        "id": game_id
                    }

    except Exception as e:
        print(f"API Error: {e}")
        return

    # --- Step 2: Handle New Games ---
    for game_id, game_data in current_hosted_games.items():
        if game_id not in announced_games:
            
            print(f" > Found NEW game: {game_data['name']} (ID: {game_id})")
            
            content = (
                f"🎮 **A LOAP is being hosted!** <@&1364041405919526962>\n"
                f"> **Name:** {game_data['name']}\n"
                f"> **Host:** {game_data['host']}\n"
                f"> **Slots:** {game_data['slots']}\n"
                f"> **Last updated:** {get_timestamp()}\n"
                f"> *ID: {game_id}*\n" 
            )
            msg = await channel.send(content)
            announced_games[game_id] = {
                "message": msg,
                "last_data": game_data
            }

    # --- Step 3: Update Ongoing or Ended Games ---
    known_ids = list(announced_games.keys())

    for game_id in known_ids:
        
        # === OPTION A: Game is Still Running ===
        if game_id in current_hosted_games:
            new_data = current_hosted_games[game_id]
            stored_data = announced_games[game_id]["last_data"]
            message = announced_games[game_id]["message"]

            # Only edit if SLOTS or HOST changed
            if new_data['slots'] != stored_data['slots'] or new_data['host'] != stored_data['host']:
                print(f" > Updating game {game_id}: Slots changed {stored_data['slots']} -> {new_data['slots']}")
                
                new_content = (
                    f"🎮 **A LOAP is being hosted!** <@&1364041405919526962>\n"
                    f"> **Name:** {new_data['name']}\n"
                    f"> **Host:** {new_data['host']}\n"
                    f"> **Slots:** {new_data['slots']}\n"
                    f"> **Last updated:** {get_timestamp()}\n"
                    f"> *ID: {game_id}*\n"
                )
                try:
                    await message.edit(content=new_content)
                    announced_games[game_id]["last_data"] = new_data
                except discord.NotFound:
                    print(f" > Message for game {game_id} was deleted manually. Removing from tracker.")
                    del announced_games[game_id]

        # === OPTION B: Game Has Ended ===
        else:
            print(f" > Game ended: {game_id}. Updating message to 'Ended'.")
            game_data = announced_games[game_id]["last_data"]
            message = announced_games[game_id]["message"]
            
            ended_content = (
                f"❌ **This LOAP is no longer being hosted.**\n"
                f"> **Name:** {game_data.get('name', 'LOAP')}\n"
                f"> **Host:** {game_data.get('host', 'Unknown')}\n"
                f"> **Last updated:** {get_timestamp()}\n"
                f"> *ID: {game_id}*\n"
            )
            try:
                await message.edit(content=ended_content)
            except discord.NotFound:
                print(f" > Could not edit ended message (it was deleted).")
            
            # CRITICAL: Remove from memory so it doesn't trigger again
            del announced_games[game_id]

    print(f"DEBUG: Currently tracking {len(announced_games)} active games.")

bot.run(BOT_TOKEN)
