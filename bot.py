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
lolregion = 'na1'

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
    elif message.content == '!monthly':
        await called_once_a_month()

async def called_once_a_day():  # Fired every day
    await bot.wait_until_ready()  # Make sure your guild cache is ready so the channel can be found via get_channel
    try:
        player = riot_watcher.account.by_riot_id(region, 'ImaHitGold2024Ok', 'Gay')
    except HTTPError as err:
        return print(f"Error fetching player data: {err}")

    past_24_hours = datetime.now() - timedelta(hours=24)
    # Get match IDs for the past 24 hours
    match_ids = lol_watcher.match.matchlist_by_puuid(lolregion, player['puuid'], start_time=int(past_24_hours.timestamp()), queue=420)  # 420 is the queue ID for ranked solo/duo
    # Fetch and process each match
    performance_summary = []
    for match_id in match_ids:
        match_detail = lol_watcher.match.by_id(lolregion, match_id)

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

async def called_once_a_month():  # Fired once a month
    await bot.wait_until_ready()
    try:
        player = riot_watcher.account.by_riot_id(region, 'ImaHitGold2024Ok', 'Gay')
    except HTTPError as err:
        return print(f"Error fetching player data: {err}")

    summoner = lol_watcher.summoner.by_puuid(lolregion, player['puuid'])
    league_entries = lol_watcher.league.by_summoner(lolregion, summoner['id'])

    # Find the ranked solo/duo entry
    solo_duo_entry = next((entry for entry in league_entries if entry['queueType'] == 'RANKED_SOLO_5x5'), None)

    if solo_duo_entry:
        tier = solo_duo_entry['tier']
        rank = solo_duo_entry['rank']
        lp = solo_duo_entry['leaguePoints']
        wins = solo_duo_entry['wins']
        losses = solo_duo_entry['losses']

        message = f"{player['gameName']}'s Ranked Solo/Duo Stats:\n"
        message += f"Tier: {tier} {rank}\n"
        message += f"LP: {lp}\n"
        message += f"Wins: {wins}\n"
        message += f"Losses: {losses}\n"
        message += f"Win Rate: {wins / (wins + losses) * 100:.2f}%"

        # Create a pie chart
        plt.figure(figsize=(8, 8))
        plt.pie([wins, losses], labels=['Wins', 'Losses'], autopct='%1.1f%%', startangle=90)
        plt.title(f"{player['gameName']}'s Win/Loss Ratio")
        plt.axis('equal')

        # Save the chart as an image
        chart_path = 'monthly_stats.png'
        plt.savefig(chart_path)
        plt.close()

        channel = bot.get_guild(guild_id).get_channel(channel_id)
        await channel.send(message, file=discord.File(chart_path))

        # Remove the temporary image file
        os.remove(chart_path)
    else:
        channel = bot.get_guild(guild_id).get_channel(channel_id)
        await channel.send(f"{player['gameName']} is not ranked in Solo/Duo queue.")

async def background_task():
    now = datetime.utcnow()
    WHEN = time(hour=18, minute=0, second=0)  # 6:00 PM UTC
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
        if now.day == 1:  # If it's the first day of the month
            await called_once_a_month()  # Call the monthly function
        tomorrow = datetime.combine(now.date() + timedelta(days=1), time(0))
        seconds = (tomorrow - now).total_seconds()  # Seconds until tomorrow (midnight)
        await asyncio.sleep(seconds) # Sleep until tomorrow and then the loop will start a new iteration

bot.run(DISCORDT)
