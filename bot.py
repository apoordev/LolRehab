import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
from requests.exceptions import HTTPError
from riotwatcher import LolWatcher, APIError

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
RIOT_TOKEN = os.getenv('RIOT_TOKEN')

lol_watcher = LolWatcher(RIOT_TOKEN)
region = 'na1'
player_account = riot_watcher.account.by_riot_id('AMERICAS', 'pseudonym', 'sudo')
player = lol_watcher.summoner.by_puuid(region, player_account['puuid'])

bot = discord.Client()

@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    print('Watching summoner')
    print(player)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if message.content.startswith('!summoner'):
        try:
            summoner = lol_watcher.summoner.by_name(region, message.content.split(' ')[1])
            print(summoner)
        except HTTPError:
            await message.channel.send('No summoner found')
        except APIError:
            await message.channel.send('API Error')

bot.run()
