import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Используем SQLite для Amvera
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/bot.db")

TEMPLATE_DIR = "templates"
STATIC_DIR = "static"