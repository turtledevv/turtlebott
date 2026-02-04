import asyncio
from http import client
import time
import logging
import discord
from discord.ext import commands
from .config import settings
from .utils.logger import setup_logger
from .utils.module_loader import load_modules, get_module_doc, get_all_modules, is_enabled
import traceback

logger = setup_logger("bot")

# Configure discord.py to use the same logging system
discord_logger = setup_logger("discord")
logging.getLogger("discord").parent = None
logging.getLogger("discord").setLevel(logging.INFO)

def run():
    start_time = time.time()

    # logger.info("Turtlebott Copyright (C) 2025 Turtledevv. Licensed under the GPL 3.0 License.")
    # logger.info("This is free software, and you are welcome to redistribute it under certain conditions. This program comes with ABSOLUTELY NO WARRANTY; see LICENSE for details.")

    bot = commands.Bot(command_prefix="t.", intents=settings.intents, help_command=None)

    @bot.event
    async def on_ready():
        logger.info(f"Logged in as {bot.user}")

        logger.info("Loading modules...")
        await load_modules(bot)

        logger.info("Syncing application commands...")
        await bot.tree.sync()
        logger.info(f"Synced {len(bot.tree.get_commands())} commands.")

        await bot.change_presence(status=discord.Status.dnd, activity=discord.Activity(name="Beep boop!", type=discord.ActivityType.playing))

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"Done! (took {elapsed_ms:.0f}ms)")

    @bot.event
    async def on_command_error(ctx, error):
        traceback.print_exception(type(error), error, error.__traceback__)
        await ctx.reply(f"An error occurred: {str(error)}")


    bot.run(settings.token, log_handler=None)
