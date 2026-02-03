import asyncio
from http import client
import time
import logging
import discord
from discord.ext import commands
from .config import settings
from .utils.logger import setup_logger

logger = setup_logger("bot")

# Configure discord.py to use the same logging system
discord_logger = setup_logger("discord")
logging.getLogger("discord").parent = None
logging.getLogger("discord").setLevel(logging.INFO)

 # add ya new modules here if i add any in the future (I WILL.)
modules = [
    "example",
    "battle_panel",
    "ai_suprise"
]

async def load_modules(bot):
    """Load all modules from the modules folder."""
    logger.info("Loading modules...")
    def is_enabled(module_name: str) -> bool:
        experiments = settings.config.get("experiments_config", {})
        module_config = experiments.get(module_name, {})
        return module_config.get("enabled", False)
    
    # loop through modules, and pray to GAWD i named everything correctly...
    for module in modules:
        # check if the module even has a config entry. if it doesn't, assume it doesn't exist and warn
        if module not in settings.config.get("experiments_config", {}):
            logger.warning(f"Module '{module}' not found in config.yml! Skipping... (Are you sure it exists?)")
            continue
        if is_enabled(module):
            logger.info(f"Loading module: {module}")
            await bot.load_extension(f"turtlebott.modules.{module}")
    
    if not modules: # check if modules list is empty
        logger.warning("No modules found! That's not supposed to happen..")
    elif all(not is_enabled(m) for m in modules):  # check if all modules are disabled
        logger.warning("All modules are disabled in config.yml!")
    else: # and finally if everything is a-ok, log success
        logger.info("All enabled modules loaded successfully.")

def run():
    start_time = time.time()
    bot = commands.Bot(command_prefix="t.", intents=settings.intents)
    
    @bot.event
    async def on_ready():
        logger.info(f"Logged in as {bot.user}")
        await load_modules(bot)
        

        await bot.change_presence(status=discord.Status.dnd, activity=discord.Activity(name="Beep boop!", type=discord.ActivityType.playing))


        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"Done! (took {elapsed_ms:.0f}ms)")
    
    bot.run(settings.token, log_handler=None)
