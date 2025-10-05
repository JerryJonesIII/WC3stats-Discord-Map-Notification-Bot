import os
import discord
import requests
from discord.ext import commands, tasks
import datetime # Import the datetime module for timestamps

# ------------------------------------------------------------------------------------
# --- CONFIGURATION - FILL THIS OUT ---
# ------------------------------------------------------------------------------------
BOT_TOKEN = "" ## Bot Token
MONITOR_CHANNEL_ID = ## ID Of channel
GAME_KEYWORDS = ["TEST", "TEST2"] ##Game Keywords to look for
CHECK_INTERVAL_SECONDS = 30 
# ------------------------------------------------------------------------------------

# --- BOT SETUP ---
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

# This variable will act as the bot's "memory" for the announcement message.
active_game_message = None

def get_timestamp():
    """Helper function to get a formatted timestamp for logging."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

async def perform_game_check():
    """
    This is the core logic function. It checks the API and finds the game.
    It returns the details of the found game, or None if not found.
    """
    api_url = "https://api.wc3stats.com/gamelist"
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        api_data = response.json()

        for game in api_data.get('body', []):
            game_name = game.get('name', '')
            if any(keyword.lower() in game_name.lower() for keyword in GAME_KEYWORDS):
                slots = f"{game.get('slotsTaken', 0)} / {game.get('slotsTotal', 0)}"
                return {"name": game_name, "host": game.get('host', 'N/A'), "slots": slots}
        return None # Return None if no game was found after checking all of them
    except requests.exceptions.RequestException as e:
        print(f"[{get_timestamp()}] DEBUG: Could not connect to the API: {e}")
        return None # Return None on error

@bot.event
async def on_ready():
    """Called when the bot successfully connects."""
    print(f"[{get_timestamp()}] {bot.user.name} has connected to Discord!")
    print(f"[{get_timestamp()}] Starting game monitoring loop...")
    monitor_game_lobbies.start()

@tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
async def monitor_game_lobbies():
    """This is the main background task that calls the check function."""
    global active_game_message
    print(f"\n[{get_timestamp()}] DEBUG: Running scheduled check...")
    
    found_game_details = await perform_game_check()
    channel = bot.get_channel(MONITOR_CHANNEL_ID)
    if not channel:
        print(f"[{get_timestamp()}] ERROR: Could not find channel with ID {MONITOR_CHANNEL_ID}. Loop paused.")
        return

    # --- Logic for Posting/Updating/Deleting the Message ---
    if found_game_details:
        message_content = (f"🎮 **A game is being hosted!** <@&1364041405919526962>\n"
                           f"> **Name:** {found_game_details['name']}\n"
                           f"> **Host:** {found_game_details['host']}\n"
                           f"> **Slots:** {found_game_details['slots']}")
        if active_game_message is None:
            print(f"[{get_timestamp()}] DEBUG: Game found ('{found_game_details['name']}'). Posting new message.")
            active_game_message = await channel.send(message_content)
        else:
            if active_game_message.content != message_content:
                print(f"[{get_timestamp()}] DEBUG: Game found ('{found_game_details['name']}'). Updating slots to {found_game_details['slots']}.")
                await active_game_message.edit(content=message_content)
            else:
                print(f"[{get_timestamp()}] DEBUG: Game found ('{found_game_details['name']}'). No changes in slots. Doing nothing.")

# --- NEW DEBUG COMMAND ---
@bot.command(name='checknow')
async def check_now(ctx):
    """Manually runs a check and reports the status in the channel."""
    await ctx.send("⚙️ Performing a manual check on the API...")
    
    found_game_details = await perform_game_check()
    
    if found_game_details:
        message = (f"✅ **Game Found!**\n"
                   f"> **Name:** {found_game_details['name']}\n"
                   f"> **Host:** {found_game_details['host']}\n"
                   f"> **Slots:** {found_game_details['slots']}")
        await ctx.send(message)
    else:
        await ctx.send("❌ **Game Not Found.** No hosted games match the keywords.")

# --- RUN THE BOT ---
bot.run(BOT_TOKEN)