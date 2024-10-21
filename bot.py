import os
from dotenv import load_dotenv
from datetime import datetime, time, timedelta
import asyncio
import discord
from requests.exceptions import HTTPError
from riotwatcher import RiotWatcher
from ollama import Client
import matplotlib.pyplot as plt
import io

load_dotenv()
DISCORDT = os.getenv('DISCORD_TOKEN')
RIOTT = os.getenv('RIOT_TOKEN')
guild_id = int(os.getenv('GUILDID'))
channel_id = int(os.getenv('CHANNELID'))
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
    if message.content == '!monthly':
        await called_once_a_month()

async def called_once_a_day():  # Fired every day
    await bot.wait_until_ready()  # Make sure your guild cache is ready so the channel can be found via get_channel
    try:
        player = riot_watcher.account.by_riot_id(region, 'ImaHitGold2024Ok', 'Gay')
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

async def called_once_a_month():
    await bot.wait_until_ready()
    try:
        player = riot_watcher.account.by_riot_id(region, 'ImaHitGold2024Ok', 'Gay')
        summoner = riot_watcher.summoner.by_puuid(region, player['puuid'])
        league_entries = riot_watcher.league.by_summoner(region, summoner['id'])
    except HTTPError as err:
        print(f"Error fetching player data: {err}")
        return

    solo_queue_entry = next((entry for entry in league_entries if entry['queueType'] == 'RANKED_SOLO_5x5'), None)
    if not solo_queue_entry:
        await bot.get_guild(guild_id).get_channel(channel_id).send("No ranked solo queue data available for the player.")
        return

    # Generate graph
    dates = [datetime.now() - timedelta(days=i*7) for i in range(4, -1, -1)]  # Last 5 weeks
    lp_values = [solo_queue_entry['leaguePoints']]  # Current LP
    for _ in range(4):
        lp_values.insert(0, max(0, lp_values[0] - 20))  # Simulated past LP values

    plt.figure(figsize=(10, 6))
    plt.plot(dates, lp_values, marker='o')
    plt.title(f"Rank/ELO Changes for {player['gameName']}")
    plt.xlabel("Date")
    plt.ylabel("League Points (LP)")
    plt.grid(True)

    # Save plot to a buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)

    # Send the graph as a file
    channel = bot.get_guild(guild_id).get_channel(channel_id)
    await channel.send(f"Monthly rank/ELO changes for {player['gameName']}:",
                       file=discord.File(buf, filename="rank_changes.png"))

async def background_task():
    now = datetime.utcnow()
    WHEN = time(hour=18, minute=0, second=0)  # 6:00 PM UTC
    if now.time() > WHEN:
        tomorrow = datetime.combine(now.date() + timedelta(days=1), time(0))
        seconds = (tomorrow - now).total_seconds()
        await asyncio.sleep(seconds)
    while True:
        now = datetime.utcnow()
        target_time = datetime.combine(now.date(), WHEN)
        seconds_until_target = (target_time - now).total_seconds()
        await asyncio.sleep(seconds_until_target)
        await called_once_a_day()
        if now.day == 1:  # First day of the month
            await called_once_a_month()
        tomorrow = datetime.combine(now.date() + timedelta(days=1), time(0))
        seconds = (tomorrow - now).total_seconds()
        await asyncio.sleep(seconds)

bot.run(DISCORDT)
