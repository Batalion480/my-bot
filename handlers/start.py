from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.database import Database

router = Router()
db = Database()

# Укажите здесь свой Telegram ID (можно узнать у @userinfobot)
ADMIN_IDS = [871907300]  # ← ЗАМЕНИТЕ НА СВОЙ ID


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Главное меню бота"""
    user_id = await db.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.full_name
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🔵 44-ФЗ", callback_data="menu_44")
    builder.button(text="🟢 223-ФЗ", callback_data="menu_223")
    builder.adjust(1)

    await message.answer(
        "🏢 **Добро пожаловать в бот «НМЦК+Срок»!**\n\n"
        "Я помогу вам:\n"
        "• Рассчитать НМЦК методом сопоставимых рыночных цен\n"
        "• Рассчитать сроки в рамках 44-ФЗ или 223-ФЗ\n"
        "• Сформировать готовый PDF-документ\n\n"
        " \n\n"
        "• Уважаемые пользователи! Чат-бот является тока помощником, он не может претендовать на точность в своих подсчетов и юридически не несет ответственности за те данные, которые он Вам предоставит.В данный момент функция распознования PDF не работает!\n\n"
        "📌 **Выберите закон:**",
        reply_markup=builder.as_markup()
    )


@router.callback_query(lambda c: c.data == "menu_44")
async def menu_44(callback: types.CallbackQuery, state: FSMContext):
    """Меню 44-ФЗ"""
    await callback.answer()
    await state.update_data(law_type="44")
    await callback.message.delete()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Расчёт НМЦК", callback_data="new_procurement")
    builder.button(text="📅 Расчёт сроков", callback_data="go_to_terms")
    builder.button(text="🔙 Главное меню", callback_data="back_to_menu")
    builder.adjust(1)

    await callback.message.answer(
        "🔵 **44-ФЗ**\n\n"
        "Выберите действие:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(lambda c: c.data == "menu_223")
async def menu_223(callback: types.CallbackQuery, state: FSMContext):
    """Меню 223-ФЗ"""
    await callback.answer()
    await state.update_data(law_type="223")
    await callback.message.delete()
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Расчёт НМЦК", callback_data="new_procurement")
    builder.button(text="📅 Расчёт сроков", callback_data="go_to_terms")
    builder.button(text="🔙 Главное меню", callback_data="back_to_menu")
    builder.adjust(1)

    await callback.message.answer(
        "🟢 **223-ФЗ**\n\n"
        "Выберите действие:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await callback.answer()
    await state.clear()
    await callback.message.delete()
    await cmd_start(callback.message)


# ============================================================
# КОМАНДА /stats (только для администратора)
# ============================================================

@router.message(Command("stats"))
async def show_stats(message: types.Message):
    """Статистика бота (только для администратора)"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ У вас нет прав на эту команду.")
        return

    total = await db.get_user_count()
    today = await db.get_active_users(1)
    week = await db.get_active_users(7)
    recent = await db.get_recent_users(5)

    text = f"📊 **Статистика бота**\n\n"
    text += f"👤 **Всего пользователей:** {total}\n"
    text += f"📅 **Активных за 24 часа:** {today}\n"
    text += f"📅 **Активных за 7 дней:** {week}\n\n"
    text += "🕒 **Последние 5 активных пользователей:**\n"
    for i, u in enumerate(recent, 1):
        name = u.get('first_name') or u.get('username') or f"ID {u.get('telegram_id')}"
        date = u.get('last_activity', '').replace('T', ' ')[:16]
        text += f"{i}. {name} — {date}\n"

    await message.answer(text)