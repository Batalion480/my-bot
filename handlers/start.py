from aiogram import Router, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.database import Database

router = Router()
db = Database()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    # Проверяем подключение к БД
    if db.conn is None:
        await db.connect()
    
    user_id = await db.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.full_name
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🆕 Новая закупка", callback_data="new_procurement")
    builder.button(text="📂 Мои закупки", callback_data="my_procurements")
    builder.adjust(1)

    await message.answer(
        "🏢 Добро пожаловать в бот **«Смета+Срок»**!\n\n"
        "Я помогу вам:\n"
        "• Рассчитать НМЦК на основе коммерческих предложений\n"
        "• Построить календарный план по 44-ФЗ или 223-ФЗ\n"
        "• Проанализировать риски при сдвиге дат\n"
        "• Сформировать готовый PDF-документ\n\n"
        "Выберите действие:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    """Возврат в главное меню"""
    await callback.answer()
    await callback.message.delete()
    await cmd_start(callback.message)