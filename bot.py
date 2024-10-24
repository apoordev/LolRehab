import os
from dotenv import load_dotenv
from datetime import datetime, time, timedelta
import asyncio
import discord
from requests.exceptions import HTTPError
from riotwatcher import RiotWatcher, LolWatcher
from ollama import Client
from groq import Groq
import pytz
import matplotlib.pyplot as plt

load_dotenv()
DISCORDT = os.getenv('DISCORD_TOKEN')
RIOTT = os.getenv('RIOT_TOKEN')
guild_id = int(os.getenv('GUILDID'))
channel_id = int(os.getenv('CHANNELID'))
user_id = os.getenv('LOLUSER').split('#')
lol_watcher = LolWatcher(RIOTT)
riot_watcher = RiotWatcher(RIOTT)
tz = pytz.timezone(os.getenv('TIMEZONE'))
region = os.getenv('REGION')
lolregion = os.getenv('SERVERS')

ollclient = Client(host=os.getenv('OLLAMA_HOST'))
gclient = Groq(api_key=os.getenv('GROQ_TOKEN'))

bot = discord.Client(intents=discord.Intents.all())

@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    print('Starting background task...')
    bot.loop.create_task(background_task())  # Start the background task when the bot is ready
    print('Task started.')

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
        print("Pulled player data!")
    except HTTPError as err:
        return print(f"Error fetching player data: {err}")

    past_24_hours = datetime.now() - timedelta(hours=24)
    # Get match IDs for the past 24 hours
    match_ids = lol_watcher.match.matchlist_by_puuid(lolregion, player['puuid'], start_time=int(past_24_hours.timestamp()), queue=420)  # 420 is the queue ID for ranked solo/duo
    # Fetch and process each match
    wins_data = []
    losses_data = []
    concise_game_data = []
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
                    lane = participant['teamPosition']
                    # Find enemy laner
                    enemy_champion = ""
                    for enemy in match_detail['info']['participants']:
                        if enemy['teamPosition'] == lane and enemy['teamId'] != participant['teamId']:
                            enemy_champion = enemy['championName']
                            break
                    game_duration = match_detail['info']['gameDuration'] // 60  # Convert to minutes
                    game_timestamp = datetime.fromtimestamp(match_detail['info']['gameCreation'] / 1000)

                    game_data = {
                        'champion': champion,
                        'kills': kills,
                        'deaths': deaths,
                        'assists': assists,
                        'cs': cs,
                        'lane': lane,
                        'enemy': enemy_champion,
                        'duration': game_duration,
                        'timestamp': game_timestamp,
                        'kda_ratio': ((kills + assists) / max(1, deaths))
                    }

                    if win:
                        wins_data.append(game_data)
                    else:
                        losses_data.append(game_data)

                    concise_game_data.append({
                        'time': game_timestamp,
                        'champion': champion,
                        'result': 'Victory' if win else 'Defeat',
                        'duration': game_duration,
                        'kda': f"{kills}/{deaths}/{assists}",
                        'cs': f"{cs} ({cs / game_duration:.1f}/min)",
                        'lane_matchup': f"{lane} vs {enemy_champion}"
                    })
                    break

    channel = bot.get_guild(guild_id).get_channel(channel_id)

    if wins_data or losses_data:
        print("Sending performance summary...")

        if wins_data:
            wins_embed = discord.Embed(
                title="Victories",
                description=f"Total Wins: {len(wins_data)}",
                color=discord.Color.green()
            )
            for game in wins_data:
                wins_embed.add_field(
                    name=f"{game['champion']} - {game['duration']}min",
                    value=f"KDA: {game['kills']}/{game['deaths']}/{game['assists']} ({game['kda_ratio']:.2f})\n"
                          f"CS: {game['cs']} ({game['cs']/game['duration']:.1f}/min)\n"
                          f"Lane: {game['lane']} vs {game['enemy']}\n"
                          f"Time: {game['timestamp'].astimezone(tz).strftime('%I:%M %p')}",
                    inline=False
                )
            await channel.send(embed=wins_embed)

        if losses_data:
            losses_embed = discord.Embed(
                title="Defeats",
                description=f"Total Losses: {len(losses_data)}",
                color=discord.Color.red()
            )
            for game in losses_data:
                losses_embed.add_field(
                    name=f"{game['champion']} - {game['duration']}min",
                    value=f"KDA: {game['kills']}/{game['deaths']}/{game['assists']} ({game['kda_ratio']:.2f})\n"
                          f"CS: {game['cs']} ({game['cs']/game['duration']:.1f}/min)\n"
                          f"Lane: {game['lane']} vs {game['enemy']}\n"
                          f"Time: {game['timestamp'].astimezone(tz).strftime('%I:%M %p')}",
                    inline=False
                )
            await channel.send(embed=losses_embed)

        concise_performance_message = "\n".join([f"Start: {game['time']} Champ: {game['champion']} Result: {game['result']} Duration: {game['duration']} minutes KDA: {game['kda']} CS: {game['cs']} Lane/Matchup: {game['lane_matchup']}" for game in concise_game_data])

        try:
            print("Generating Groq response...")
            response = gclient.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": "You are "+user_id[0]+"'s Idol, a Korean League of Legends pro named Faker who likes to critique statistics."
                    },
                    {
                        "role": "user",
                        "content": "Here is "+user_id[0]+"'s League of Legends statistics:"+concise_performance_message
                    }
                ],
                temperature=1,
                max_tokens=1024,
                top_p=1,
                stream=False,
                stop=None,
            )
            print("Sending LLM response...")
            await channel.send(response.choices[0].message.content)
        except Exception as e:
            print(e)
            print("Groq failed... Generating ollama response...")
            response = ollclient.chat(model='llama3.1:latest', messages=[
                    {
                        "role": "system",
                        "content": "You are "+user_id[0]+"'s Idol, a Korean League of Legends pro named Faker who likes to critique statistics."
                    },
                    {
                        "role": "user",
                        "content": "Here is "+user_id[0]+"'s League of Legends statistics:"+concise_performance_message
                    }
            ])
            print("Sending LLM response...")
            await channel.send(response['message']['content'])
    else:
        print("No perfomance data for "+user_id[0]+".")
        await channel.send(user_id[0]+" did not play any ranked games today.")

async def called_once_a_month():  # Fired once a month
    await bot.wait_until_ready()
    try:
        player = riot_watcher.account.by_riot_id(region, user_id[0], user_id[1])
        print("Pulled player data!")
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
        print("Creating pie chart...")
        plt.figure(figsize=(8, 8))
        plt.pie([wins, losses], labels=['Wins', 'Losses'], autopct='%1.1f%%', startangle=90)
        plt.title(f"{player['gameName']}'s Win/Loss Ratio")
        plt.axis('equal')

        # Save the chart as an image
        chart_path = 'monthly_stats.png'
        plt.savefig(chart_path)
        plt.close()

        channel = bot.get_guild(guild_id).get_channel(channel_id)
        print("Sending pie chart...")
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
        WHEN = time(hour=4, minute=0, second=0)  # 12:00 AM EST
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
