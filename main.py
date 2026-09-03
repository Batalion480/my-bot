import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

from handlers import start, nmck, terms
from utils.database import Database

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не найден в переменных окружения!")
        return

    db = Database()
    await db.connect()
    logger.info("✅ База данных подключена")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
    )
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(nmck.router)
    dp.include_router(terms.router)

    logger.info("🚀 Бот запущен!")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())