import os
from dotenv import load_dotenv
from datetime import datetime, time, timedelta
import asyncio
import discord
from requests.exceptions import HTTPError
from riotwatcher import RiotWatcher, LolWatcher
from ollama import Client
import matplotlib.pyplot as plt

load_dotenv()
DISCORDT = os.getenv('DISCORD_TOKEN')
RIOTT = os.getenv('RIOT_TOKEN')
guild_id = int(os.getenv('GUILDID'))
channel_id = int(os.getenv('CHANNELID'))
lol_watcher = LolWatcher(RIOTT)
riot_watcher = RiotWatcher(RIOTT)
region = 'AMERICAS'

ollclient = Client(host=os.getenv('OLLAMA_HOST'))

bot = discord.Client(intents=discord.Intents.all())

@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')

@bot.event
async def on_message(message):
    # Ignore messages made by the bot
    if(message.author == bot.user):
        return
    if message.content == '!daily':
        await called_once_a_day()

async def called_once_a_day():  # Fired every day
    await bot.wait_until_ready()  # Make sure your guild cache is ready so the channel can be found via get_channel
    try:
        player = riot_watcher.account.by_riot_id(region, 'ImaHitGold2024Ok', 'Gay')
    except HTTPError as err:
        print(f"Error fetching player data: {err}")
        return

    past_24_hours = datetime.now() - timedelta(hours=24)
    # Get match IDs for the past 24 hours
    match_ids = lol_watcher.match.matchlist_by_puuid(region, player['puuid'], start_time=int(past_24_hours.timestamp()), queue=420)  # 420 is the queue ID for ranked solo/duo
    # Fetch and process each match
    performance_summary = []
    for match_id in match_ids:
        match_detail = lol_watcher.match.by_id(region, match_id)

        # Check if the match is a ranked game
        if match_detail['info']['queueId'] == 420:  # 420 is the queue ID for ranked solo/duo
            # Find the player in the match
            for participant in match_detail['info']['participants']:
                if participant['puuid'] == player['puuid']:
                    champion = participant['championName']
                    kills = participant['kills']
                    deaths = participant['deaths']
                    assists = participant['assists']
                    win = participant['win']

                    performance_summary.append(f"Champion: {champion}, K/D/A: {kills}/{deaths}/{assists}, Result: {'Win' if win else 'Loss'}")
                    break

    if performance_summary:
        performance_message = f"{player['gameName']}'s performance in the last 24 hours:\n" + "\n".join(performance_summary)
    else:
        performance_message = "No games played in the last 24 hours."

    response = ollclient.chat(model='llama3.1', messages=[
        {
            'role': 'user',
            'content': 'Summarize the following League of Legends statistics:\n'+performance_message,
        },
    ])
    
    channel = bot.get_guild(guild_id).get_channel(channel_id)
    await channel.send(performance_message+"\n"+response['message']['content'])

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
