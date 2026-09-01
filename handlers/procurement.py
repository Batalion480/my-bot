from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any
import calendar

from utils.database import Database
from utils.date_calculator import NMCKCalculator, calculate_dates, add_working_days, format_date, format_dates_dict, format_nmck_result
from utils.risk_analyzer import analyze_shift_risks, format_risks_for_output
from utils.pdf_generator import PDFGenerator, prepare_pdf_data

router = Router()
db = Database()


# ============================================================
# FSM СОСТОЯНИЯ
# ============================================================
class ProcurementStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_price_1 = State()
    waiting_for_price_2 = State()
    waiting_for_price_3 = State()
    waiting_for_law = State()
    waiting_for_223_settings = State()
    waiting_for_223_review = State()
    waiting_for_publication_date = State()
    waiting_for_shift_days = State()
    waiting_for_final_confirm = State()
    waiting_for_settings_name = State()


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================
def parse_date(date_str: str) -> Optional[date]:
    """Парсит дату в формате ДД.ММ.ГГГГ"""
    formats = ["%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def build_calendar_keyboard(current_date: date) -> InlineKeyboardBuilder:
    """Строит inline-календарь для выбора даты"""
    builder = InlineKeyboardBuilder()
    
    # Заголовок с месяцем и годом
    months_ru = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                 "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    builder.button(
        text=f"{months_ru[current_date.month - 1]} {current_date.year}",
        callback_data="calendar_ignore"
    )
    builder.button(
        text="◀️",
        callback_data="calendar_prev"
    )
    builder.button(
        text="▶️",
        callback_data="calendar_next"
    )
    builder.adjust(3)
    
    # Дни недели
    days_week = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    for d in days_week:
        builder.button(text=d, callback_data="calendar_ignore")
    builder.adjust(7)
    
    # Дни месяца
    cal = calendar.monthcalendar(current_date.year, current_date.month)
    today = date.today()
    for week in cal:
        for day in week:
            if day == 0:
                builder.button(text=" ", callback_data="calendar_ignore")
            else:
                btn_date = date(current_date.year, current_date.month, day)
                if btn_date < today:
                    builder.button(text=f"🔒{day}", callback_data="calendar_ignore")
                else:
                    builder.button(
                        text=str(day),
                        callback_data=f"calendar_select_{btn_date.strftime('%Y-%m-%d')}"
                    )
        builder.adjust(7)
    
    return builder


# ============================================================
# ОБРАБОТЧИКИ КНОПОК
# ============================================================
@router.callback_query(F.data == "new_procurement")
async def start_new_procurement(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    
    await state.set_state(ProcurementStates.waiting_for_title)
    await callback.message.answer(
        "📝 Введите **наименование** закупки (товар, работа или услуга):\n"
        "Например: *Поставка канцелярских товаров*"
    )


@router.callback_query(F.data == "my_procurements")
async def show_archive(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    data = await state.get_data()
    user_id = data.get("user_id")
    if not user_id:
        user_id = await db.get_or_create_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.full_name
        )
        await state.update_data(user_id=user_id)
    
    procurements = await db.get_user_procurements(user_id)
    
    if not procurements:
        await callback.message.answer("📭 У вас пока нет сохраненных закупок.")
        return
    
    builder = InlineKeyboardBuilder()
    for p in procurements:
        builder.button(
            text=f"{p['title'][:30]} | {format_date(p['publication_date'])}",
            callback_data=f"view_procurement_{p['id']}"
        )
    builder.adjust(1)
    builder.button(text="🔙 Назад", callback_data="back_to_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "📂 **Ваши закупки:**",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("view_procurement_"))
async def view_procurement(callback: CallbackQuery):
    await callback.answer()
    procurement_id = int(callback.data.split("_")[2])
    
    procurement = await db.get_procurement(procurement_id)
    if not procurement:
        await callback.message.answer("❌ Закупка не найдена.")
        return
    
    final = await db.get_final_timeline(procurement_id)
    
    text = (
        f"📄 **{procurement['title']}**\n"
        f"⚖️ Закон: {procurement['law_type']}\n"
        f"💰 НМЦК: {procurement['nmck']:,.2f} руб.\n"
        f"📅 Дата публикации: {format_date(procurement['publication_date'])}\n"
        f"✍️ Подписание: {format_date(procurement['signing_date'])}\n"
        f"📊 Статус: {'✅ Утвержден' if procurement['status'] == 'approved' else '📝 Черновик'}\n"
    )
    
    builder = InlineKeyboardBuilder()
    if procurement.get('final_pdf_path') or final:
        builder.button(text="📄 Скачать PDF", callback_data=f"download_pdf_{procurement_id}")
    builder.button(text="🔙 Назад", callback_data="my_procurements")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())


# ============================================================
# ШАГ 1: НАЗВАНИЕ ЗАКУПКИ
# ============================================================
@router.message(ProcurementStates.waiting_for_title)
async def process_title(message: Message, state: FSMContext):
    title = message.text.strip()
    if len(title) < 3:
        await message.answer("⚠️ Название должно быть длиннее 3 символов. Попробуйте еще раз.")
        return
    
    await state.update_data(title=title)
    await state.set_state(ProcurementStates.waiting_for_price_1)
    
    await message.answer(
        f"✅ Название: **{title}**\n\n"
        "💰 Введите **цену первого поставщика** (в рублях):\n"
        "Например: *150000*"
    )


# ============================================================
# ШАГ 2-4: ВВОД ЦЕН
# ============================================================
@router.message(ProcurementStates.waiting_for_price_1)
async def process_price_1(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", ".").replace(" ", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите корректное число (например, 150000)")
        return
    
    await state.update_data(price_1=price)
    await state.set_state(ProcurementStates.waiting_for_price_2)
    await message.answer("💰 Введите **цену второго поставщика** (в рублях):")


@router.message(ProcurementStates.waiting_for_price_2)
async def process_price_2(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", ".").replace(" ", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите корректное число (например, 150000)")
        return
    
    await state.update_data(price_2=price)
    await state.set_state(ProcurementStates.waiting_for_price_3)
    await message.answer("💰 Введите **цену третьего поставщика** (в рублях):")


@router.message(ProcurementStates.waiting_for_price_3)
async def process_price_3(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", ".").replace(" ", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите корректное число (например, 150000)")
        return
    
    await state.update_data(price_3=price)
    
    data = await state.get_data()
    prices = [data["price_1"], data["price_2"], data["price_3"]]
    
    result = NMCKCalculator.calculate_nmck(prices)
    await state.update_data(nmck_result=result, nmck=result["nmck"])
    
    text = format_nmck_result(result)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Продолжить", callback_data="nmck_confirm")
    builder.button(text="🔄 Ввести заново", callback_data="nmck_retry")
    builder.adjust(1)
    
    await state.set_state(ProcurementStates.waiting_for_law)
    await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "nmck_retry")
async def retry_prices(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(price_1=None, price_2=None, price_3=None, nmck_result=None, nmck=None)
    await state.set_state(ProcurementStates.waiting_for_price_1)
    await callback.message.edit_text("🔄 Введите **цену первого поставщика** (в рублях):")


@router.callback_query(F.data == "nmck_confirm")
async def confirm_nmck(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    data = await state.get_data()
    user_id = data.get("user_id")
    settings = await db.get_settings(user_id) if user_id else []
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔵 44-ФЗ", callback_data="law_44")
    
    if settings:
        builder.button(text="🟢 223-ФЗ (выбрать настройки)", callback_data="law_223_settings")
        builder.button(text="🟢 223-ФЗ (ввести вручную)", callback_data="law_223_manual")
    else:
        builder.button(text="🟢 223-ФЗ", callback_data="law_223_manual")
    
    builder.button(text="🔙 Назад", callback_data="back_to_menu")
    builder.adjust(1)
    
    await state.set_state(ProcurementStates.waiting_for_law)
    await callback.message.edit_text(
        "⚖️ **Выберите закон**, по которому будет проводиться закупка:\n\n"
        "• **44-ФЗ** — государственные и муниципальные нужды\n"
        "• **223-ФЗ** — закупки госкорпораций и естественных монополий",
        reply_markup=builder.as_markup()
    )


# ============================================================
# ШАГ 5: ВЫБОР ЗАКОНА
# ============================================================
@router.callback_query(F.data == "law_44")
async def select_44fz(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(law_type="44-FZ")
    await ask_publication_date(callback.message, state)


@router.callback_query(F.data == "law_223_settings")
async def select_223_settings(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    data = await state.get_data()
    user_id = data.get("user_id")
    if not user_id:
        user_id = await db.get_or_create_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.full_name
        )
        await state.update_data(user_id=user_id)
    
    settings = await db.get_settings(user_id)
    
    builder = InlineKeyboardBuilder()
    for s in settings:
        label = f"📌 {s['setting_name']} (подача {s['bid_submission_days']}д, рассмотрение {s['bid_review_days']}д)"
        builder.button(text=label, callback_data=f"use_setting_{s['id']}")
    builder.button(text="✏️ Ввести вручную", callback_data="law_223_manual")
    builder.button(text="🔙 Назад", callback_data="nmck_confirm")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "🟢 **Выберите настройки Положения по 223-ФЗ:**",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("use_setting_"))
async def use_setting(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    setting_id = int(callback.data.split("_")[2])
    await state.update_data(setting_id=setting_id, law_type="223-FZ")
    await ask_publication_date(callback.message, state)


@router.callback_query(F.data == "law_223_manual")
async def select_223_manual(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(law_type="223-FZ")
    await state.set_state(ProcurementStates.waiting_for_223_settings)
    
    await callback.message.edit_text(
        "🟢 **Введите параметры Положения по 223-ФЗ:**\n\n"
        "1️⃣ Срок подачи заявок (в рабочих днях):"
    )


@router.message(ProcurementStates.waiting_for_223_settings)
async def process_223_settings(message: Message, state: FSMContext):
    try:
        bid_days = int(message.text)
        if bid_days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите положительное число (например, 5)")
        return
    
    await state.update_data(custom_bid_days=bid_days)
    await state.set_state(ProcurementStates.waiting_for_223_review)
    await message.answer("2️⃣ Срок рассмотрения заявок (в рабочих днях):")


@router.message(ProcurementStates.waiting_for_223_review)
async def process_223_review(message: Message, state: FSMContext):
    try:
        review_days = int(message.text)
        if review_days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите положительное число (например, 3)")
        return
    
    await state.update_data(custom_review_days=review_days)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="💾 Сохранить как шаблон", callback_data="save_223_setting")
    builder.button(text="⏭️ Продолжить без сохранения", callback_data="skip_223_save")
    builder.adjust(1)
    
    await state.set_state(ProcurementStates.waiting_for_publication_date)
    await message.answer(
        "✅ Настройки сохранены для текущей закупки.\n\n"
        "Хотите сохранить их как шаблон для будущих закупок?",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "save_223_setting")
async def save_223_setting(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ProcurementStates.waiting_for_settings_name)
    await callback.message.edit_text(
        "📝 Введите название шаблона (например, *Стандартный* или *Ускоренный*):"
    )


@router.message(ProcurementStates.waiting_for_settings_name)
async def process_settings_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("⚠️ Название должно быть длиннее 2 символов.")
        return
    
    data = await state.get_data()
    user_id = data.get("user_id")
    if not user_id:
        user_id = await db.get_or_create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.full_name
        )
        await state.update_data(user_id=user_id)
    
    bid_days = data.get("custom_bid_days")
    review_days = data.get("custom_review_days")
    
    await db.create_settings(
        user_id=user_id,
        name=name,
        bid_days=bid_days,
        review_days=review_days,
        is_default=False
    )
    
    await state.set_state(ProcurementStates.waiting_for_publication_date)
    await message.answer(f"✅ Шаблон **«{name}»** сохранен!\n\nТеперь выберем дату публикации.")
    await ask_publication_date(message, state)


@router.callback_query(F.data == "skip_223_save")
async def skip_223_save(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ProcurementStates.waiting_for_publication_date)
    await callback.message.edit_text("✅ Продолжаем.\n\nТеперь выберем дату публикации.")
    await ask_publication_date(callback.message, state)


# ============================================================
# ШАГ 6: ВВОД ДАТЫ ПУБЛИКАЦИИ
# ============================================================
async def ask_publication_date(message: types.Message, state: FSMContext):
    await state.set_state(ProcurementStates.waiting_for_publication_date)
    
    today = date.today()
    builder = build_calendar_keyboard(today)
    builder.button(text="📅 Сегодня", callback_data=f"calendar_select_{today.strftime('%Y-%m-%d')}")
    builder.button(text="📅 Завтра", callback_data=f"calendar_select_{(today + timedelta(days=1)).strftime('%Y-%m-%d')}")
    builder.button(text="✏️ Ввести вручную", callback_data="calendar_manual")
    builder.adjust(3)
    
    await message.answer(
        "📅 **Выберите дату публикации извещения:**\n\n"
        "Используйте календарь или введите дату вручную в формате ДД.ММ.ГГГГ",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "calendar_manual")
async def manual_date(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ProcurementStates.waiting_for_publication_date)
    await callback.message.edit_text(
        "📅 Введите дату публикации в формате **ДД.ММ.ГГГГ**\n"
        "Например: *15.10.2026*"
    )


@router.callback_query(F.data.startswith("calendar_select_"))
async def calendar_select(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    date_str = callback.data.split("_")[2]
    selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    
    if selected_date < date.today():
        await callback.answer("❌ Нельзя выбрать прошедшую дату!", show_alert=True)
        return
    
    await state.update_data(publication_date=selected_date)
    await perform_calculation(callback.message, state)


@router.message(ProcurementStates.waiting_for_publication_date)
async def process_manual_date(message: Message, state: FSMContext):
    selected_date = parse_date(message.text)
    if not selected_date:
        await message.answer("⚠️ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ (например, 15.10.2026)")
        return
    
    if selected_date < date.today():
        await message.answer("⚠️ Нельзя выбрать прошедшую дату. Введите дату от сегодняшнего дня.")
        return
    
    await state.update_data(publication_date=selected_date)
    await perform_calculation(message, state)


# ============================================================
# ШАГ 7: ПЕРВИЧНЫЙ РАСЧЕТ
# ============================================================
async def perform_calculation(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    law_type = data.get("law_type")
    publication_date = data.get("publication_date")
    nmck = data.get("nmck")
    
    if law_type == "44-FZ":
        dates = calculate_dates(
            law_type="44-FZ",
            publication_date=publication_date,
            nmck=nmck
        )
    else:
        setting_id = data.get("setting_id")
        if setting_id:
            user_id = data.get("user_id")
            settings = await db.get_settings(user_id) if user_id else []
            setting = next((s for s in settings if s["id"] == setting_id), None)
            if setting:
                bid_days = setting["bid_submission_days"]
                review_days = setting["bid_review_days"]
                signing_days = setting.get("signing_days", 5)
            else:
                bid_days = data.get("custom_bid_days", 5)
                review_days = data.get("custom_review_days", 3)
                signing_days = 5
        else:
            bid_days = data.get("custom_bid_days", 5)
            review_days = data.get("custom_review_days", 3)
            signing_days = 5
        
        dates = calculate_dates(
            law_type="223-FZ",
            publication_date=publication_date,
            bid_submission_days=bid_days,
            bid_review_days=review_days,
            signing_days=signing_days
        )
    
    await state.update_data(current_dates=dates, original_dates=dates.copy(), shift_days=0)
    
    law_label = "44-ФЗ" if law_type == "44-FZ" else "223-ФЗ"
    text = (
        f"📄 **Ваша закупка:** {data.get('title')}\n"
        f"💰 **НМЦК:** {nmck:,.2f} руб.\n"
        f"⚖️ **Закон:** {law_label}\n\n"
        f"📅 **Календарный план** (публикация {format_date(publication_date)}):\n\n"
        f"{format_dates_dict(dates)}\n\n"
        f"✅ **Статус:** Сроки соблюдены."
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Оставить как есть", callback_data="confirm_dates")
    builder.button(text="⏪ Сдвинуть НАЗАД (раньше)", callback_data="shift_back")
    builder.button(text="⏩ Отложить ВПЕРЕД (позже)", callback_data="shift_forward")
    builder.adjust(1)
    
    await message.answer(text, reply_markup=builder.as_markup())


# ============================================================
# ШАГ 8: СДВИГ ДАТ
# ============================================================
@router.callback_query(F.data == "shift_back")
async def shift_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(shift_direction="back")
    await state.set_state(ProcurementStates.waiting_for_shift_days)
    await callback.message.edit_text(
        "⏪ **На сколько дней сдвинуть публикацию НАЗАД (раньше)?**\n\n"
        "Введите число (например, *3*):"
    )


@router.callback_query(F.data == "shift_forward")
async def shift_forward(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(shift_direction="forward")
    await state.set_state(ProcurementStates.waiting_for_shift_days)
    await callback.message.edit_text(
        "⏩ **На сколько дней отложить публикацию ВПЕРЕД (позже)?**\n\n"
        "Введите число (например, *7*):"
    )


@router.message(ProcurementStates.waiting_for_shift_days)
async def process_shift(message: Message, state: FSMContext):
    try:
        days = int(message.text)
        if days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите положительное число (например, 5)")
        return
    
    data = await state.get_data()
    direction = data.get("shift_direction")
    shift_days = days if direction == "forward" else -days
    
    old_dates = data.get("current_dates", {})
    old_publication = old_dates.get("publication_date")
    
    if direction == "forward":
        new_publication = old_publication + timedelta(days=days)
    else:
        new_publication = old_publication - timedelta(days=days)
    
    law_type = data.get("law_type")
    nmck = data.get("nmck")
    
    if law_type == "44-FZ":
        new_dates = calculate_dates(
            law_type="44-FZ",
            publication_date=new_publication,
            nmck=nmck
        )
    else:
        applied_bid = old_dates.get("applied_bid_days", 5)
        applied_review = old_dates.get("applied_review_days", 3)
        applied_signing = old_dates.get("applied_signing_days", 5)
        
        new_dates = calculate_dates(
            law_type="223-FZ",
            publication_date=new_publication,
            bid_submission_days=applied_bid,
            bid_review_days=applied_review,
            signing_days=applied_signing
        )
    
    risks = analyze_shift_risks(
        old_dates=old_dates,
        new_dates=new_dates,
        law_type=law_type,
        nmck=nmck if law_type == "44-FZ" else None,
        shift_days=shift_days
    )
    
    await state.update_data(
        current_dates=new_dates,
        shift_days=shift_days,
        risks=risks
    )
    
    text = (
        f"🔄 **Пересчет выполнен!**\n\n"
        f"📅 Новая дата публикации: **{format_date(new_publication)}**\n"
        f"({'+' if shift_days > 0 else ''}{shift_days} дней)\n\n"
        f"📊 **Было → Стало:**\n"
        f"📄 Публикация: {format_date(old_publication)} → {format_date(new_publication)}\n"
        f"📩 Подача: {format_date(old_dates['bid_end_date'])} → {format_date(new_dates['bid_end_date'])}\n"
        f"✍️ Подписание: {format_date(old_dates['signing_date'])} → {format_date(new_dates['signing_date'])}\n\n"
    )
    
    if risks:
        text += format_risks_for_output(risks) + "\n"
    else:
        text += "✅ Рисков не обнаружено.\n"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="⚠️ Вернуть исходную дату", callback_data="reset_dates")
    builder.button(text="🔄 Попробовать другой сдвиг", callback_data="try_another_shift")
    builder.button(text="🚀 Утвердить график", callback_data="confirm_dates")
    builder.adjust(1)
    
    await state.set_state(ProcurementStates.waiting_for_final_confirm)
    await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "reset_dates")
async def reset_dates(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    original_dates = data.get("original_dates", {})
    
    await state.update_data(current_dates=original_dates, shift_days=0, risks=[])
    
    text = (
        f"📅 **Возврат к исходному плану:**\n\n"
        f"{format_dates_dict(original_dates)}\n\n"
        f"✅ Статус: Сроки соблюдены."
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Утвердить", callback_data="confirm_dates")
    builder.button(text="⏪ Сдвинуть НАЗАД", callback_data="shift_back")
    builder.button(text="⏩ Отложить ВПЕРЕД", callback_data="shift_forward")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "try_another_shift")
async def try_another_shift(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ProcurementStates.waiting_for_shift_days)
    await callback.message.edit_text("⏩ **На сколько дней сдвинуть публикацию?**\n\nВведите число:")


# ============================================================
# ШАГ 9: УТВЕРЖДЕНИЕ И ГЕНЕРАЦИЯ PDF
# ============================================================
@router.callback_query(F.data == "confirm_dates")
async def confirm_dates(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    data = await state.get_data()
    
    dates = data.get("current_dates", {})
    original_dates = data.get("original_dates", {})
    shift_days = data.get("shift_days", 0)
    risks = data.get("risks", [])
    
    user_id = data.get("user_id")
    if not user_id:
        user_id = await db.get_or_create_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.full_name
        )
        await state.update_data(user_id=user_id)
    
    title = data.get("title")
    law_type = data.get("law_type")
    nmck = data.get("nmck")
    nmck_result = data.get("nmck_result", {})
    setting_id = data.get("setting_id")
    custom_bid = data.get("custom_bid_days")
    custom_review = data.get("custom_review_days")
    
    procurement_data = {
        "title": title,
        "law_type": law_type,
        "nmck": nmck,
        "supplier_ids": [],
        "setting_id": setting_id,
        "custom_bid_days": custom_bid,
        "custom_review_days": custom_review,
        "publication_date": dates.get("publication_date"),
        "bid_end_date": dates.get("bid_end_date"),
        "consideration_date": dates.get("consideration_date"),
        "auction_date": dates.get("auction_date"),
        "signing_date": dates.get("signing_date"),
        "bg_deadline_date": dates.get("bg_deadline_date"),
        "scatter_warning": nmck_result.get("scatter_warning", ""),
    }
    
    procurement_id = await db.create_procurement(user_id, procurement_data)
    
    revision = await db.get_next_revision(procurement_id)
    
    risk_text = "\n".join([r[1] for r in risks]) if risks else ""
    
    timeline_data = {
        "revision_number": revision,
        "shift_days": shift_days,
        "applied_bid_days": dates.get("applied_bid_days", 0),
        "applied_review_days": dates.get("applied_review_days", 0),
        "applied_signing_days": dates.get("applied_signing_days", 5),
        "publication_date": dates.get("publication_date"),
        "bid_end_date": dates.get("bid_end_date"),
        "consideration_date": dates.get("consideration_date"),
        "auction_date": dates.get("auction_date"),
        "signing_date": dates.get("signing_date"),
        "bg_deadline_date": dates.get("bg_deadline_date"),
        "risk_warning": risk_text,
        "is_final": True
    }
    
    if shift_days != 0:
        original_timeline = {
            "revision_number": 1,
            "shift_days": 0,
            "applied_bid_days": original_dates.get("applied_bid_days", 0),
            "applied_review_days": original_dates.get("applied_review_days", 0),
            "applied_signing_days": original_dates.get("applied_signing_days", 5),
            "publication_date": original_dates.get("publication_date"),
            "bid_end_date": original_dates.get("bid_end_date"),
            "consideration_date": original_dates.get("consideration_date"),
            "auction_date": original_dates.get("auction_date"),
            "signing_date": original_dates.get("signing_date"),
            "bg_deadline_date": original_dates.get("bg_deadline_date"),
            "risk_warning": "",
            "is_final": False
        }
        await db.add_timeline_entry(procurement_id, original_timeline)
    
    await db.add_timeline_entry(procurement_id, timeline_data)
    
    # Генерируем PDF
    suppliers = [
        {"name": "Поставщик 1", "inn": "7712345678", "price": data.get("price_1", 0), "note": "КП от 01.09.2026"},
        {"name": "Поставщик 2", "inn": "7712345679", "price": data.get("price_2", 0), "note": ""},
        {"name": "Поставщик 3", "inn": "7712345680", "price": data.get("price_3", 0), "note": ""},
    ]
    
    full_timeline = await db.get_timeline(procurement_id)
    procurement = await db.get_procurement(procurement_id)
    
    pdf_data = prepare_pdf_data(
        procurement=procurement,
        suppliers=suppliers,
        timeline=full_timeline,
        company_name="ООО «Ваша компания»",
        responsible_person="Иванов И.И."
    )
    
    pdf_gen = PDFGenerator()
    pdf_bytes = pdf_gen.generate(pdf_data)
    
    pdf_filename = f"НМЦК_{procurement_id}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    await callback.message.delete()
    await callback.message.answer(
        "✅ **Закупка сохранена!**\n\n"
        f"📄 Название: {title}\n"
        f"💰 НМЦК: {nmck:,.2f} руб.\n"
        f"📅 Дата публикации: {format_date(dates['publication_date'])}\n"
        f"✍️ Подписание: {format_date(dates['signing_date'])}\n\n"
        "Ваш документ готов:",
        reply_markup=None
    )
    
    await callback.message.answer_document(
        BufferedInputFile(pdf_bytes, filename=pdf_filename),
        caption="📄 Документ с обоснованием НМЦК и календарным планом"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🆕 Новая закупка", callback_data="new_procurement")
    builder.button(text="📂 Мои закупки", callback_data="my_procurements")
    builder.adjust(1)
    
    await callback.message.answer(
        "Что делаем дальше?",
        reply_markup=builder.as_markup()
    )
    
    await state.clear()


@router.callback_query(F.data.startswith("download_pdf_"))
async def download_pdf(callback: CallbackQuery):
    await callback.answer()
    procurement_id = int(callback.data.split("_")[2])
    
    procurement = await db.get_procurement(procurement_id)
    if not procurement:
        await callback.message.answer("❌ Закупка не найдена.")
        return
    
    timeline = await db.get_timeline(procurement_id)
    suppliers = await db.get_suppliers_by_ids(procurement.get("selected_supplier_ids", []))
    
    pdf_data = prepare_pdf_data(
        procurement=procurement,
        suppliers=suppliers,
        timeline=timeline,
        company_name="ООО «Ваша компания»",
        responsible_person="Иванов И.И."
    )
    
    pdf_gen = PDFGenerator()
    pdf_bytes = pdf_gen.generate(pdf_data)
    
    pdf_filename = f"НМЦК_{procurement_id}.pdf"
    
    await callback.message.answer_document(
        BufferedInputFile(pdf_bytes, filename=pdf_filename),
        caption="📄 Документ по закупке"
    )