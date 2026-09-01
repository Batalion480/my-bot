import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/zakupki_bot")

TEMPLATE_DIR = "templates"
STATIC_DIR = "static"