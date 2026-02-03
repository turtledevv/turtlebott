import os
from discord import Intents
from dotenv import load_dotenv
import yaml

load_dotenv()

with open("config.yml", "r", encoding="utf-8") as f:
    yaml_config = yaml.safe_load(f)

class Settings:
    config = yaml_config
    token = os.getenv("DISCORD_TOKEN")
    intents = Intents.all()

settings = Settings()
