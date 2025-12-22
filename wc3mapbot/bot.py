import os
import discord
import requests
from discord.ext import commands, tasks
import datetime

# ------------------------------------------------------------------------------------
# --- CONFIGURATION ---
# ------------------------------------------------------------------------------------
BOT_TOKEN = ""
MONITOR_CHANNEL_ID = ##Discord Channel ID##
GAME_KEYWORDS = ["LOAP", "Life of a Peasant"]
CHECK_INTERVAL_SECONDS = 30
# ------------------------------------------------------------------------------------

# --- BOT SETUP ---
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

# Format:
# announced_games = {
#     game_id: {
#         "message": <discord.Message>,
#         "details": { name, host, slots }
#     }
# }
announced_games = {}

def discord_timestamp():
    """Return a Discord-formatted relative timestamp."""
    return f"<t:{int(datetime.datetime.now().timestamp())}:R>"

@bot.event
async def on_ready():
    print(f"[{datetime.datetime.now()}] {bot.user.name} connected.")
    monitor_game_lobbies.start()

@tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
async def monitor_game_lobbies():
    global announced_games
    print(f"\n[{datetime.datetime.now()}] DEBUG: Running scheduled check...")

    api_url = "https://api.wc3stats.com/gamelist"
    channel = bot.get_channel(MONITOR_CHANNEL_ID)

    if not channel:
        print("ERROR: Monitor channel not found.")
        return

    # --- Step 1: Fetch hosted games ---
    current_hosted_games = {}

    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        api_data = response.json()

        for game in api_data.get("body", []):
            game_name = game.get("name", "")
            if any(keyword.lower() in game_name.lower() for keyword in GAME_KEYWORDS):

                players = game.get("slotsTaken", 0)
                game_id = game.get("id")

                if players > 0 and game_id is not None:
                    current_hosted_games[game_id] = {
                        "name": game_name,
                        "host": game.get("host", "N/A"),
                        "slots": f"{players} / {game.get('slotsTotal', 0)}"
                    }

    except Exception as e:
        print(f"API error: {e}")
        return

    # --- Step 2: Compare sets ---
    current_game_ids = set(current_hosted_games.keys())
    announced_game_ids = set(announced_games.keys())

    # --- Step 3: Announce new games ---
    new_game_ids = current_game_ids - announced_game_ids

    for game_id in new_game_ids:
        game = current_hosted_games[game_id]

        message_content = (
            f"🎮 **A LOAP is being hosted!** <@&1364041405919526962>\n" ## Adjust Name of hosted lobby ##
            f"> **Name:** {game['name']}\n"
            f"> **Host:** {game['host']}\n"
            f"> **Slots:** {game['slots']}\n"
            f"> **Last updated:** {discord_timestamp()}"
        )

        new_message = await channel.send(message_content)

        announced_games[game_id] = {
            "message": new_message,
            "details": game
        }

    # --- Step 5: Update ongoing games ---
    ongoing_game_ids = announced_game_ids.intersection(current_game_ids)

    for game_id in ongoing_game_ids:
        game_details = current_hosted_games[game_id]
        stored = announced_games[game_id]
        message_to_update = stored["message"]

        new_content = (
            f"🎮 **A LOAP is being hosted!** <@&1364041405919526962>\n" ## Adjust name of Discord Lobby ##
            f"> **Name:** {game_details['name']}\n"
            f"> **Host:** {game_details['host']}\n"
            f"> **Slots:** {game_details['slots']}\n"
            f"> **Last updated:** {discord_timestamp()}\n"
            f"> ***Courtesy of Roark Productions***"
        )

        if message_to_update.content != new_content:
            await message_to_update.edit(content=new_content)

        announced_games[game_id]["details"] = game_details

    # --- Step 6: Mark games that ended ---
    no_longer_hosted_ids = announced_game_ids - current_game_ids

    for game_id in no_longer_hosted_ids:
        stored = announced_games[game_id]
        message_to_update = stored["message"]
        game_details = stored["details"]

        ended_content = (
            f"❌ **This LOAP is no longer being hosted.**\n"
            f"> **Name:** {game_details['name']}\n"
            f"> **Host:** {game_details['host']}\n"
            f"> **Last updated:** {discord_timestamp()}\n"
            f"> ***Courtesy of Roark Productions***"
        )

        await message_to_update.edit(content=ended_content)
        del announced_games[game_id]

    print(f"DEBUG: Tracking {len(announced_games)} games.")

# --- RUN THE BOT ---
bot.run(BOT_TOKEN)
