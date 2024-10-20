import os
from dotenv import load_dotenv
from datetime import datetime, time, timedelta
import asyncio
import discord
from discord.ext import commands
from requests.exceptions import HTTPError
from riotwatcher import RiotWatcher, LolWatcher

load_dotenv()
DISCORDT = os.getenv('DISCORD_TOKEN')
RIOTT = os.getenv('RIOT_TOKEN')
guild_id = os.getenv('GUILDID')
channel_id = os.getenv('CHANNELID')
lol_watcher = LolWatcher(RIOTT)
riot_watcher = RiotWatcher(RIOTT)

bot = discord.Client(intents=discord.Intents.default())

@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')

async def called_once_a_day():  # Fired every day
    await bot.wait_until_ready()  # Make sure your guild cache is ready so the channel can be found via get_channel
    try:
        player = riot_watcher.account.by_riot_id('AMERICAS', 'ImaHitGold2024Ok', 'Gay')
    except HTTPError as err:
        if err.response.status_code == 429:
            print('We should retry in {} seconds.'.format(err.response.headers['Retry-After']))
            print('this retry-after is handled by default by the RiotWatcher library')
            print('future requests wait until the retry-after time passes')
        elif err.response.status_code == 404:
            print('Summoner with that ridiculous name not found.')
        elif err.response.status_code == 400:
            print('Something with the API is broken')
            quit()
        else:
            raise
    channel = bot.bot.get_guild(guild_id).get_channel(channel_id) # Note: It's more efficient to do bot.get_guild(guild_id).get_channel(channel_id) as there's less looping involved, but just get_channel still works fine
    await channel.send(player.gameName)

async def background_task():
    now = datetime.utcnow()
    if now.time() > WHEN:  # Make sure loop doesn't start after {WHEN} as then it will send immediately the first time as negative seconds will make the sleep yield instantly
        tomorrow = datetime.combine(now.date() + timedelta(days=1), time(0))
        seconds = (tomorrow - now).total_seconds()  # Seconds until tomorrow (midnight)
        await asyncio.sleep(seconds)   # Sleep until tomorrow and then the loop will start 
    while True:
        now = datetime.utcnow() # You can do now() or a specific timezone if that matters, but I'll leave it with utcnow
        target_time = datetime.combine(now.date(), WHEN)  # 6:00 PM today (In UTC)
        seconds_until_target = (target_time - now).total_seconds()
        await asyncio.sleep(seconds_until_target)  # Sleep until we hit the target time
        await called_once_a_day()  # Call the helper function that sends the message
        tomorrow = datetime.combine(now.date() + timedelta(days=1), time(0))
        seconds = (tomorrow - now).total_seconds()  # Seconds until tomorrow (midnight)
        await asyncio.sleep(seconds) # Sleep until tomorrow and then the loop will start a new iteration

bot.run(DISCORDT)
