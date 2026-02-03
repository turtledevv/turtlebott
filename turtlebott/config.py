import os
from discord import Intents
from dotenv import load_dotenv
import yaml
from .utils.logger import setup_logger

logger = setup_logger("config")

load_dotenv()

with open("config.yml", "r", encoding="utf-8") as f:
    logger.info("Loading configuration from config.yml")
    yaml_config = yaml.safe_load(f)

class Settings:
    config = yaml_config
    token = os.getenv("DISCORD_TOKEN")
    intents = Intents.all()

modules = list(yaml_config["experiments_config"].keys())
settings = Settings()
