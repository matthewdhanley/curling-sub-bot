import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

import db

load_dotenv()

TOKEN = os.environ["DISCORD_BOT_TOKEN"]
GUILD_ID = int(os.environ["GUILD_ID"])
DB_PATH = os.environ.get("DB_PATH", "./data/subbot.db")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: Exception):
    import traceback
    print(f"App command error: {error}")
    traceback.print_exc()


@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
    print(f"Logged in as {bot.user} ({bot.user.id})")
    print(f"Commands synced to guild {GUILD_ID}")


async def main():
    async with bot:
        await db.init_db(DB_PATH)
        await bot.load_extension("cogs.sub_request")
        await bot.start(TOKEN)


asyncio.run(main())
