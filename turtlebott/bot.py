import asyncio
from http import client
import time
import logging
import discord
from discord.ext import commands
from .config import settings
from .utils.logger import setup_logger
from .utils.module_loader import load_modules, get_module_doc, get_all_modules, is_enabled

logger = setup_logger("bot")

# Configure discord.py to use the same logging system
discord_logger = setup_logger("discord")
logging.getLogger("discord").parent = None
logging.getLogger("discord").setLevel(logging.INFO)

def run():
    start_time = time.time()

    # logger.info("Turtlebott Copyright (C) 2025 Turtledevv. Licensed under the GPL 3.0 License.")
    # logger.info("This is free software, and you are welcome to redistribute it under certain conditions. This program comes with ABSOLUTELY NO WARRANTY; see LICENSE for details.")

    bot = commands.Bot(command_prefix="t.", intents=settings.intents)
    
    @bot.event
    async def on_ready():
        logger.info(f"Logged in as {bot.user}")
        await load_modules(bot)
        await bot.tree.sync()
        await bot.change_presence(status=discord.Status.dnd, activity=discord.Activity(name="Beep boop!", type=discord.ActivityType.playing))

        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"Done! (took {elapsed_ms:.0f}ms)")

    @bot.hybrid_command(name="listmodules")
    async def listmodules(ctx):
        """Lists enabled and disabled modules with descriptions."""
        logger.info(f"User {ctx.author} invoked listmodules command.")

        enabled = []
        disabled = []

        for module in get_all_modules():
            desc = get_module_doc(module)
            line = f"**{module}** – *{desc}*"

            if is_enabled(module):
                enabled.append(line)
            else:
                disabled.append(line)

        if not enabled:
            await ctx.send("No modules are currently enabled.")
            return

        message = (
            "## **Enabled modules:**\n"
            + "\n".join(enabled)
            + "\n\n## **Disabled modules:**\n"
            + "\n".join(disabled)
        )

        await ctx.reply(message)

    bot.run(settings.token, log_handler=None)
