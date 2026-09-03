from aiogram import Router, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.database import Database

router = Router()
db = Database()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Главное меню бота"""
    user_id = await db.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.full_name
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🔵 44-ФЗ", callback_data="law_44")
    builder.button(text="🟢 223-ФЗ", callback_data="law_223")
    builder.adjust(1)

    await message.answer(
        "🏢 Добро пожаловать в бот **«Смета+Срок»**!\n\n"
        "Я помогу вам:\n"
        "• Рассчитать НМЦК методом сопоставимых рыночных цен\n"
        "• Построить календарный план по 44-ФЗ или 223-ФЗ\n"
        "• Сформировать готовый PDF-документ\n\n"
        "Выберите закон:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    """Возврат в главное меню"""
    await callback.answer()
    await cmd_start(callback.message)