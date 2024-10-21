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
user_id = os.getenv('LOLUSER').split('#')
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
    print('Starting background task...')
    bot.loop.create_task(background_task())  # Start the background task when the bot is ready

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
        player = riot_watcher.account.by_riot_id(region, user_id[0], user_id[1])
    except HTTPError as err:
        return print(f"Error fetching player data: {err}")

    past_24_hours = datetime.now() - timedelta(hours=24)
    # Get match IDs for the past 24 hours
    match_ids = lol_watcher.match.matchlist_by_puuid(lolregion, player['puuid'], start_time=int(past_24_hours.timestamp()), queue=420)  # 420 is the queue ID for ranked solo/duo
    # Fetch and process each match
    performance_summary = []
    for match_id in match_ids:
        match_detail = lol_watcher.match.by_id(lolregion, match_id)

        # Check if the match is a ranked game and longer than 10 minutes
        if match_detail['info']['queueId'] == 420 and match_detail['info']['gameDuration'] > 600:  # 420 is the queue ID for ranked solo/duo, 600 seconds = 10 minutes
            # Find the player in the match
            for participant in match_detail['info']['participants']:
                if participant['puuid'] == player['puuid']:
                    champion = participant['championName']
                    kills = participant['kills']
                    deaths = participant['deaths']
                    assists = participant['assists']
                    win = participant['win']
                    cs = participant['totalMinionsKilled'] + participant['neutralMinionsKilled']
                    vision_score = participant['visionScore']
                    game_duration = match_detail['info']['gameDuration'] // 60  # Convert to minutes

                    performance_summary.append(
                        f"```md\n"
                        f"# {champion} - {'Victory' if win else 'Defeat'} ({game_duration} min)\n"
                        f"## KDA: {kills}/{deaths}/{assists} ({((kills + assists) / max(1, deaths)):.2f})\n"
                        f"* CS: {cs} ({cs / game_duration:.1f}/min)\n"
                        f"* Vision Score: {vision_score}\n"
                        f"```"
                    )
                    break

    if performance_summary:
        performance_message = f"**{player['gameName']}'s performance in the last 24 hours (games longer than 10 minutes):**\n" + "\n".join(performance_summary)
    else:
        performance_message = "No games longer than 10 minutes played in the last 24 hours."

    response = ollclient.chat(model='llama3.1', messages=[
        {
            'role': 'user',
            'content': 'Summarize the following League of Legends statistics and critique them:\n'+performance_message,
        },
    ])

    channel = bot.get_guild(guild_id).get_channel(channel_id)
    await channel.send(performance_message)
    await channel.send(response['message']['content'])

async def called_once_a_month():  # Fired once a month
    await bot.wait_until_ready()
    try:
        player = riot_watcher.account.by_riot_id(region, user_id[0], user_id[1])
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
        await channel.send("\n"+message, file=discord.File(chart_path))

        # Remove the temporary image file
        os.remove(chart_path)
    else:
        channel = bot.get_guild(guild_id).get_channel(channel_id)
        await channel.send(f"{player['gameName']} is not ranked in Solo/Duo queue.")

async def background_task():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.utcnow()
        WHEN = time(hour=0, minute=0, second=0)  # 12:00 AM UTC 8:00 PM EST
        if now.time() > WHEN:
            tomorrow = datetime.combine(now.date() + timedelta(days=1), time(0))
            seconds = (tomorrow - now).total_seconds()
            await asyncio.sleep(seconds)
        target_time = datetime.combine(now.date(), WHEN)
        seconds_until_target = (target_time - now).total_seconds()
        await asyncio.sleep(seconds_until_target)
        await called_once_a_day()
        if now.day == 1:
            await called_once_a_month()

bot.run(DISCORDT)
