# ============================================================
# handlers/terms.py
# Обработчик расчёта сроков по 44-ФЗ и 223-ФЗ
# ============================================================

import os
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, date, timedelta

from utils.date_calculator import (
    format_date, 
    calculate_dates_from_db,
    add_working_days,
    add_calendar_days
)
from utils.risk_analyzer import analyze_shift_risks, format_risks_for_output
from utils.database import Database
from utils.pdf_generator import generate_terms_pdf

router = Router()
db = Database()


# ============================================================
# FSM СОСТОЯНИЯ
# ============================================================

class TermsStates(StatesGroup):
    waiting_for_procedure = State()
    waiting_for_nmck = State()
    waiting_for_publication_date = State()
    waiting_for_shift_days = State()
    # Для 223-ФЗ
    waiting_for_bid_days = State()
    waiting_for_review_days = State()


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def get_stage_name(stage: str) -> str:
    """Возвращает человекочитаемое название этапа"""
    stage_names = {
        "bid_submission": "📩 Подача заявок",
        "auction": "⚡ Аукцион",
        "review": "🔍 Рассмотрение заявок",
        "protocol": "📋 Протокол",
        "signing": "✍️ Подписание контракта"
    }
    return stage_names.get(stage, stage)


# ============================================================
# ОБРАБОТЧИКИ
# ============================================================

@router.callback_query(lambda c: c.data == "go_to_terms")
async def start_terms(callback: types.CallbackQuery, state: FSMContext):
    """Начало расчёта сроков - выбор процедуры"""
    await callback.answer()
    await state.set_state(TermsStates.waiting_for_procedure)

    builder = InlineKeyboardBuilder()
    builder.button(text="⚡ Электронный аукцион", callback_data="procedure_auction")
    builder.button(text="📩 Запрос котировок", callback_data="procedure_quote")
    builder.button(text="📋 Электронный конкурс", callback_data="procedure_competition")
    builder.button(text="🔙 Главное меню", callback_data="back_to_menu")
    builder.adjust(1)

    await callback.message.edit_text(
        "📅 **Выберите процедуру для расчета сроков:**",
        reply_markup=builder.as_markup()
    )


@router.callback_query(lambda c: c.data.startswith("procedure_"))
async def select_procedure(callback: types.CallbackQuery, state: FSMContext):
    """Выбор процедуры"""
    await callback.answer()
    procedure = callback.data.replace("procedure_", "")
    await state.update_data(procedure=procedure)

    data = await state.get_data()
    law_type = data.get("law_type", "44")

    # Человекочитаемое название процедуры
    procedure_names = {
        "auction": "Электронный аукцион",
        "quote": "Запрос котировок",
        "competition": "Электронный конкурс"
    }
    procedure_name = procedure_names.get(procedure, procedure)

    if law_type == "44":
        # Для 44-ФЗ запрашиваем НМЦК
        await state.set_state(TermsStates.waiting_for_nmck)
        await callback.message.edit_text(
            f"📌 Выбрана процедура: **{procedure_name}**\n\n"
            "💰 Введите **НМЦК** (в рублях):\n"
            "Например: *2500000*"
        )
    else:
        # Для 223-ФЗ запрашиваем сроки из Положения
        await state.set_state(TermsStates.waiting_for_bid_days)
        await callback.message.edit_text(
            f"📌 Выбрана процедура: **{procedure_name}**\n\n"
            "📋 Для 223-ФЗ нужны сроки из вашего Положения.\n"
            "Введите **срок подачи заявок** (в рабочих днях):\n"
            "Например: *7*"
        )


# ============================================================
# 44-ФЗ: ВВОД НМЦК
# ============================================================

@router.message(TermsStates.waiting_for_nmck)
async def process_nmck_for_terms(message: types.Message, state: FSMContext):
    """Ввод НМЦК для 44-ФЗ"""
    try:
        nmck = float(message.text.replace(",", ".").replace(" ", ""))
        if nmck <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите корректную сумму (например, 2500000)")
        return

    await state.update_data(nmck=nmck)
    await state.set_state(TermsStates.waiting_for_publication_date)
    await message.answer(
        "📅 Введите **дату публикации извещения** (в формате ДД.ММ.ГГГГ):\n"
        "Например: *15.10.2026*"
    )


# ============================================================
# 223-ФЗ: ВВОД СРОКОВ ИЗ ПОЛОЖЕНИЯ
# ============================================================

@router.message(TermsStates.waiting_for_bid_days)
async def process_bid_days(message: types.Message, state: FSMContext):
    """Ввод срока подачи заявок для 223-ФЗ"""
    try:
        bid_days = int(message.text)
        if bid_days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите положительное число (например, 7)")
        return

    await state.update_data(bid_days=bid_days)
    await state.set_state(TermsStates.waiting_for_review_days)
    await message.answer(
        "Введите **срок рассмотрения заявок** (в рабочих днях):\n"
        "Например: *5*"
    )


@router.message(TermsStates.waiting_for_review_days)
async def process_review_days(message: types.Message, state: FSMContext):
    """Ввод срока рассмотрения заявок для 223-ФЗ"""
    try:
        review_days = int(message.text)
        if review_days <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите положительное число (например, 5)")
        return

    await state.update_data(review_days=review_days)
    await state.set_state(TermsStates.waiting_for_publication_date)
    await message.answer(
        "📅 Введите **дату публикации извещения** (в формате ДД.ММ.ГГГГ):\n"
        "Например: *15.10.2026*"
    )


# ============================================================
# ОБЩАЯ ДАТА ПУБЛИКАЦИИ
# ============================================================

@router.message(TermsStates.waiting_for_publication_date)
async def process_publication_date(message: types.Message, state: FSMContext):
    """Ввод даты публикации и расчёт сроков"""
    try:
        pub_date = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
        if pub_date < date.today():
            await message.answer("⚠️ Дата не может быть в прошлом. Введите дату от сегодняшнего дня.")
            return
    except ValueError:
        await message.answer("⚠️ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ")
        return

    data = await state.get_data()
    law_type = data.get("law_type", "44")
    nmck = data.get("nmck")
    procedure = data.get("procedure")

    # Преобразуем тип закона для БД
    law_type_db = f"{law_type}-FZ"

    # Получаем правила из БД для отображения
    rules = await db.get_all_rules_for_procedure(law_type_db, procedure)

    # Формируем текст с правилами
    rules_text = ""
    for rule in rules:
        stage_name = get_stage_name(rule["stage"])
        rules_text += f"{stage_name}:\n"
        rules_text += f"  📌 {rule['rule_text']}\n"
        rules_text += f"  📎 {rule['article']}\n\n"

    # Рассчитываем даты
    if law_type == "44":
        dates = await calculate_dates_from_db(
            law_type=law_type_db,
            procedure_type=procedure,
            publication_date=pub_date,
            nmck=nmck,
            db=db
        )
    else:  # 223-ФЗ
        bid_days = data.get("bid_days")
        review_days = data.get("review_days")
        if bid_days is None or review_days is None:
            await message.answer("⚠️ Ошибка: не указаны сроки по 223-ФЗ. Начните заново.")
            return
        
        dates = await calculate_dates_from_db(
            law_type=law_type_db,
            procedure_type=procedure,
            publication_date=pub_date,
            nmck=None,
            db=db,
            custom_params={
                "bid_days": bid_days,
                "review_days": review_days,
                "signing_days": 5
            }
        )

    await state.update_data(dates=dates)

    # Формируем вывод
    law_label = f"{law_type}-ФЗ"
    text = (
        f"📅 **Расчет сроков по {law_label}**\n\n"
        f"📖 **Применены правила:**\n{rules_text}\n"
        f"📊 **Рассчитанные даты:**\n"
        f"📄 Публикация: {format_date(dates['publication_date'])}\n"
        f"📩 Окончание подачи: {format_date(dates['bid_end_date'])}\n"
        f"⚡ Аукцион: {format_date(dates.get('auction_date', dates['bid_end_date']))}\n"
        f"🔍 Рассмотрение: {format_date(dates.get('review_date', dates.get('consideration_date', dates['bid_end_date'])))}\n"
        f"📋 Протокол: {format_date(dates.get('protocol_date', dates.get('consideration_date', dates['bid_end_date'])))}\n"
        f"✍️ Подписание: {format_date(dates['signing_date'])}\n"
    )
    if nmck:
        text += f"\n💰 НМЦК: {nmck:,.2f} руб."

    builder = InlineKeyboardBuilder()
    builder.button(text="⏪ Сдвинуть НАЗАД", callback_data="shift_back")
    builder.button(text="⏩ Сдвинуть ВПЕРЕД", callback_data="shift_forward")
    builder.button(text="📄 Сформировать PDF", callback_data="terms_pdf")
    builder.button(text="🔙 Главное меню", callback_data="back_to_menu")
    builder.adjust(2, 1, 1)

    await state.set_state(TermsStates.waiting_for_shift_days)
    await message.answer(text, reply_markup=builder.as_markup())


# ============================================================
# СДВИГ ДАТ
# ============================================================

@router.callback_query(lambda c: c.data in ["shift_back", "shift_forward"])
async def handle_shift(callback: types.CallbackQuery, state: FSMContext):
    """Обработка сдвига дат"""
    await callback.answer()
    direction = callback.data.replace("shift_", "")
    await state.update_data(shift_direction=direction)

    direction_text = "НАЗАД (раньше)" if direction == "back" else "ВПЕРЕД (позже)"
    await callback.message.edit_text(
        f"⏳ На сколько дней сдвинуть публикацию **{direction_text}**?\n\n"
        "Введите число (например, *5*):"
    )


@router.message(TermsStates.waiting_for_shift_days)
async def process_shift(message: types.Message, state: FSMContext):
    """Пересчёт дат с учётом сдвига и анализ рисков"""
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

    old_dates = data.get("dates")
    if not old_dates:
        await message.answer("⚠️ Ошибка: данные не найдены. Начните заново.")
        return

    old_publication = old_dates["publication_date"]
    new_publication = old_publication + timedelta(days=shift_days)

    law_type = data.get("law_type", "44")
    law_type_db = f"{law_type}-FZ"
    nmck = data.get("nmck")
    procedure = data.get("procedure")

    # Пересчитываем даты с новым сдвигом
    if law_type == "44":
        new_dates = await calculate_dates_from_db(
            law_type=law_type_db,
            procedure_type=procedure,
            publication_date=new_publication,
            nmck=nmck,
            db=db
        )
    else:
        bid_days = data.get("bid_days")
        review_days = data.get("review_days")
        new_dates = await calculate_dates_from_db(
            law_type=law_type_db,
            procedure_type=procedure,
            publication_date=new_publication,
            nmck=None,
            db=db,
            custom_params={
                "bid_days": bid_days,
                "review_days": review_days,
                "signing_days": 5
            }
        )

    # Анализ рисков
    risks = analyze_shift_risks(
        old_dates=old_dates,
        new_dates=new_dates,
        law_type=law_type_db,
        nmck=nmck,
        shift_days=shift_days
    )

    await state.update_data(dates=new_dates)

    # Формируем результат
    shift_text = f"+{shift_days}" if shift_days > 0 else str(shift_days)
    text = (
        f"🔄 **Пересчет выполнен!**\n\n"
        f"📅 Новая дата публикации: {format_date(new_publication)}\n"
        f"(сдвиг {shift_text} дней)\n\n"
        f"📊 **Было → Стало:**\n"
        f"📄 Публикация: {format_date(old_publication)} → {format_date(new_publication)}\n"
        f"📩 Подача: {format_date(old_dates['bid_end_date'])} → {format_date(new_dates['bid_end_date'])}\n"
        f"✍️ Подписание: {format_date(old_dates['signing_date'])} → {format_date(new_dates['signing_date'])}\n\n"
    )

    # Добавляем анализ рисков
    if risks:
        text += format_risks_for_output(risks) + "\n"
    else:
        text += "✅ **Рисков не обнаружено.** Все сроки соблюдены.\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="⚠️ Вернуть исходную дату", callback_data="reset_dates")
    builder.button(text="🔄 Другой сдвиг", callback_data="another_shift")
    builder.button(text="📄 Сформировать PDF", callback_data="terms_pdf")
    builder.button(text="🔙 Главное меню", callback_data="back_to_menu")
    builder.adjust(1)

    await message.answer(text, reply_markup=builder.as_markup())


# ============================================================
# СБРОС ДАТ
# ============================================================

@router.callback_query(lambda c: c.data == "reset_dates")
async def reset_dates(callback: types.CallbackQuery, state: FSMContext):
    """Возврат к исходным датам"""
    await callback.answer()
    data = await state.get_data()
    old_dates = data.get("dates")
    
    if not old_dates:
        await callback.message.edit_text("⚠️ Данные не найдены. Начните заново.")
        return

    # Восстанавливаем исходные даты (убираем сдвиг)
    # Для этого пересчитываем с нулевым сдвигом
    law_type = data.get("law_type", "44")
    law_type_db = f"{law_type}-FZ"
    nmck = data.get("nmck")
    procedure = data.get("procedure")
    pub_date = old_dates.get("publication_date")

    if law_type == "44":
        new_dates = await calculate_dates_from_db(
            law_type=law_type_db,
            procedure_type=procedure,
            publication_date=pub_date,
            nmck=nmck,
            db=db
        )
    else:
        bid_days = data.get("bid_days")
        review_days = data.get("review_days")
        new_dates = await calculate_dates_from_db(
            law_type=law_type_db,
            procedure_type=procedure,
            publication_date=pub_date,
            nmck=None,
            db=db,
            custom_params={
                "bid_days": bid_days,
                "review_days": review_days,
                "signing_days": 5
            }
        )

    await state.update_data(dates=new_dates)

    text = (
        f"✅ **Даты возвращены к исходным:**\n\n"
        f"📄 Публикация: {format_date(new_dates['publication_date'])}\n"
        f"📩 Подача: {format_date(new_dates['bid_end_date'])}\n"
        f"✍️ Подписание: {format_date(new_dates['signing_date'])}"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="⏪ Сдвинуть НАЗАД", callback_data="shift_back")
    builder.button(text="⏩ Сдвинуть ВПЕРЕД", callback_data="shift_forward")
    builder.button(text="📄 Сформировать PDF", callback_data="terms_pdf")
    builder.button(text="🔙 Главное меню", callback_data="back_to_menu")
    builder.adjust(2, 1, 1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())


# ============================================================
# ДРУГОЙ СДВИГ
# ============================================================

@router.callback_query(lambda c: c.data == "another_shift")
async def another_shift(callback: types.CallbackQuery, state: FSMContext):
    """Повторный сдвиг"""
    await callback.answer()
    await callback.message.edit_text(
        "⏳ На сколько дней сдвинуть публикацию?\n\n"
        "Введите число (например, *5*):\n"
        "• Положительное = вперёд (позже)\n"
        "• Отрицательное = назад (раньше)"
    )


# ============================================================
# ГЕНЕРАЦИЯ PDF
# ============================================================

@router.callback_query(lambda c: c.data == "terms_pdf")
async def generate_terms_pdf_handler(callback: types.CallbackQuery, state: FSMContext):
    """Генерация PDF со сроками"""
    await callback.answer()
    
    data = await state.get_data()
    dates = data.get("dates")
    law_type = data.get("law_type", "44")
    nmck = data.get("nmck")
    procedure = data.get("procedure")

    if not dates:
        await callback.message.answer("⚠️ Данные не найдены. Начните расчёт заново.")
        return

    # Получаем правила из БД для отображения в PDF
    law_type_db = f"{law_type}-FZ"
    rules = await db.get_all_rules_for_procedure(law_type_db, procedure)
    dates['rules'] = rules

    try:
        pdf_path = generate_terms_pdf(
            dates=dates,
            law_type=f"{law_type}-ФЗ",
            nmck=nmck,
            company_name="ООО «Ваша компания»",
            responsible_person="Иванов И.И."
        )

        if pdf_path and os.path.exists(pdf_path):
            # Отправляем PDF новым сообщением
            await callback.message.answer_document(
                types.FSInputFile(pdf_path),
                caption=f"📄 Календарный план закупки\n\n"
                        f"Закон: {law_type}-ФЗ\n"
                        f"Публикация: {format_date(dates.get('publication_date'))}\n"
                        f"Подписание: {format_date(dates.get('signing_date'))}"
            )
            
            # Удаляем временный файл
            try:
                os.unlink(pdf_path)
            except:
                pass
        else:
            await callback.message.answer("❌ Не удалось сгенерировать PDF. Попробуйте ещё раз.")

    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}")


# ============================================================
# ВОЗВРАТ В ГЛАВНОЕ МЕНЮ
# ============================================================

@router.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "🏠 **Главное меню**\n\n"
        "Выберите действие:",
        reply_markup=InlineKeyboardBuilder().button(
            text="📊 Расчёт НМЦК", callback_data="new_procurement"
        ).button(
            text="📅 Расчёт сроков", callback_data="go_to_terms"
        ).button(
            text="📄 Скачать шаблон Excel", callback_data="download_template_direct"
        ).adjust(1).as_markup()
    )