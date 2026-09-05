from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
import os
import re
import json
from datetime import datetime, date
from typing import List, Dict, Any
import pandas as pd
# import cv2  # закомментировано для сервера
import numpy as np
import pytesseract

from aiogram import Router, F, types
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.database import Database
from utils.date_calculator import NMCKCalculator, format_date, format_nmck_result
from utils.pdf_generator import PDFGenerator, prepare_pdf_data

router = Router()
db = Database()


# ============================================================
# FSM СОСТОЯНИЯ
# ============================================================
class NMCKStates(StatesGroup):
    waiting_for_law = State()
    waiting_for_position_count = State()
    waiting_for_calculation_method = State()
    waiting_for_input_method = State()
    
    # Ручной ввод (1 позиция)
    waiting_for_price_1 = State()
    waiting_for_price_2 = State()
    waiting_for_price_3 = State()
    waiting_for_quantity = State()
    
    # Реквизиты для PDF
    waiting_for_item_name = State()
    waiting_for_okpd = State()
    waiting_for_kp1_number = State()
    waiting_for_kp1_date = State()
    waiting_for_kp2_number = State()
    waiting_for_kp2_date = State()
    waiting_for_kp3_number = State()
    waiting_for_kp3_date = State()
    
    # Много позиций - фото
    waiting_for_photo = State()
    waiting_for_photo_confirm = State()
    waiting_for_photo_next = State()
    
    # Много позиций - Excel
    waiting_for_excel = State()
    waiting_for_excel_confirm = State()
    
    # Общие для всех
    waiting_for_final_action = State()


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def extract_price(text: str) -> float:
    patterns = [
        r'(\d{1,3}(?:[ \t]*\d{3})*[.,]\d{2})',
        r'(\d{1,3}(?:[ \t]*\d{3})*)',
        r'(\d+[\s]*[.,][\s]*\d+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            raw = match.group(1).replace(' ', '').replace(',', '.')
            try:
                return float(raw)
            except ValueError:
                continue
    return 0.0


def extract_quantity(text: str) -> float:
    patterns = [
        r'(\d+)\s*(шт|кг|л|м|усл\.?\s*ед\.?|упак|пачка|коробка)',
        r'(\d+)\s*(ед|шт|кг|л|м)',
        r'Кол-во[:\s]*(\d+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return 0.0


def extract_item_name(text: str) -> str:
    lines = text.split('\n')
    for line in lines[:15]:
        line = line.strip()
        if len(line) > 5 and not re.search(r'\d{2}[./]\d{2}[./]\d{2,4}', line) and not re.search(r'\d{10,}', line):
            if not line.upper().startswith(('КОММЕРЧЕСКОЕ', 'ПРЕДЛОЖЕНИЕ', 'ООО', 'ИП', 'АО')):
                return line
    return "Не распознано"


def extract_unit(text: str) -> str:
    units = ['шт', 'кг', 'л', 'м', 'усл. ед.', 'упак', 'пачка', 'коробка', 'ед.']
    for unit in units:
        if unit in text.lower():
            return unit
    return "шт."


# ============================================================
# ОБРАБОТЧИКИ КНОПОК ВЫБОРА ЗАКОНА
# ============================================================

@router.callback_query(lambda c: c.data.startswith("law_"))
async def select_law(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    law_type = callback.data.replace("law_", "")
    await state.update_data(law_type=law_type)
    await state.set_state(NMCKStates.waiting_for_position_count)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="1 позиция", callback_data="pos_1")
    builder.button(text="Много позиций", callback_data="pos_many")
    builder.button(text="🔙 Назад", callback_data="back_to_menu")
    builder.adjust(2, 1)
    
    await callback.message.edit_text(
        f"⚖️ Выбран закон: {law_type}-ФЗ\n\n"
        "Сколько позиций в коммерческом предложении?",
        reply_markup=builder.as_markup()
    )


@router.callback_query(lambda c: c.data.startswith("pos_"))
async def select_position_count(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    count = callback.data.replace("pos_", "")
    await state.update_data(position_count=count)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Средняя цена", callback_data="method_average")
    builder.button(text="📉 Минимальная цена (письмо Минфина)", callback_data="method_minimum")
    builder.button(text="🔙 Назад", callback_data="law_44")
    builder.adjust(1)
    
    await state.set_state(NMCKStates.waiting_for_calculation_method)
    await callback.message.edit_text(
        "📊 Выберите метод расчёта НМЦК:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(lambda c: c.data.startswith("method_"))
async def select_calculation_method(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    method = callback.data.replace("method_", "")
    await state.update_data(calculation_method=method)
    
    method_text = "средней цене" if method == "average" else "минимальной цене (по письму Минфина)"
    data = await state.get_data()
    count = data.get("position_count")
    
    if count == "1":
        await state.set_state(NMCKStates.waiting_for_price_1)
        await callback.message.edit_text(
            f"✅ Выбран метод: {method_text}\n\n"
            "💰 Введите **цену первого поставщика** (в рублях):\n"
            "Например: *150000*"
        )
    else:
        builder = InlineKeyboardBuilder()
        builder.button(text="📸 Загрузить фото/скан КП", callback_data="input_photo")
        builder.button(text="📂 Загрузить файл Excel", callback_data="input_excel")
        builder.button(text="🔙 Назад", callback_data="method_back")
        builder.adjust(1)
        
        await state.set_state(NMCKStates.waiting_for_input_method)
        await callback.message.edit_text(
            f"✅ Выбран метод: {method_text}\n\n"
            "📊 Выберите способ ввода данных для нескольких позиций:",
            reply_markup=builder.as_markup()
        )


@router.callback_query(lambda c: c.data == "method_back")
async def method_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(NMCKStates.waiting_for_position_count)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="1 позиция", callback_data="pos_1")
    builder.button(text="Много позиций", callback_data="pos_many")
    builder.button(text="🔙 Назад", callback_data="back_to_menu")
    builder.adjust(2, 1)
    
    await callback.message.edit_text(
        "Сколько позиций в коммерческом предложении?",
        reply_markup=builder.as_markup()
    )


# ============================================================
# РУЧНОЙ ВВОД (1 ПОЗИЦИЯ)
# ============================================================

@router.message(NMCKStates.waiting_for_price_1)
async def process_price_1(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", ".").replace(" ", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите корректное число (например, 150000)")
        return
    
    await state.update_data(price_1=price)
    await state.set_state(NMCKStates.waiting_for_price_2)
    await message.answer("💰 Введите **цену второго поставщика** (в рублях):")


@router.message(NMCKStates.waiting_for_price_2)
async def process_price_2(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", ".").replace(" ", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите корректное число (например, 150000)")
        return
    
    await state.update_data(price_2=price)
    await state.set_state(NMCKStates.waiting_for_price_3)
    await message.answer("💰 Введите **цену третьего поставщика** (в рублях):")


@router.message(NMCKStates.waiting_for_price_3)
async def process_price_3(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", ".").replace(" ", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите корректное число (например, 150000)")
        return
    
    await state.update_data(price_3=price)
    await state.set_state(NMCKStates.waiting_for_quantity)
    await message.answer("📦 Введите **количество** (условная единица):")


@router.message(NMCKStates.waiting_for_quantity)
async def process_quantity(message: Message, state: FSMContext):
    try:
        quantity = float(message.text.replace(",", ".").replace(" ", ""))
        if quantity <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Введите корректное число (например, 100)")
        return
    
    data = await state.get_data()
    prices = [data["price_1"], data["price_2"], data["price_3"]]
    method = data.get("calculation_method", "average")
    
    result = NMCKCalculator.calculate_nmck(prices=prices, method=method)
    nmck_total = result["nmck"] * quantity
    await state.update_data(
        nmck_result=result,
        nmck=result["nmck"],
        quantity=quantity,
        nmck_total=nmck_total,
        prices=prices,
        nmck_for_terms=nmck_total
    )
    
    method_text = "средней цене" if method == "average" else "минимальной цене"
    
    text = (
        f"📊 **Итоговый расчет:**\n\n"
        f"📊 Метод: {method_text}\n"
        f"💰 Цена за единицу: {result['nmck']:,.2f} руб.\n"
        f"📦 Количество: {quantity:,.0f} шт.\n"
        f"💵 **НМЦК контракта: {nmck_total:,.2f} руб.**\n\n"
        f"📊 Коэффициент вариации: {result['variation_coefficient'] * 100:.1f}%\n"
        f"{result.get('scatter_warning', '')}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📄 Сформировать PDF", callback_data="pdf_create")
    builder.button(text="📅 Сроки", callback_data="go_to_terms")
    builder.button(text="🔙 Главное меню", callback_data="back_to_menu")
    builder.adjust(1)
    
    await state.set_state(NMCKStates.waiting_for_final_action)
    await message.answer(text, reply_markup=builder.as_markup())


# ============================================================
# СБОР РЕКВИЗИТОВ ДЛЯ PDF (1 ПОЗИЦИЯ)
# ============================================================

@router.callback_query(lambda c: c.data == "pdf_create")
async def start_pdf_collection(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(NMCKStates.waiting_for_item_name)
    await callback.message.edit_text(
        "📝 Для формирования PDF введите **наименование позиции**:"
    )


@router.message(NMCKStates.waiting_for_item_name)
async def process_item_name(message: Message, state: FSMContext):
    item_name = message.text.strip()
    if len(item_name) < 3:
        await message.answer("⚠️ Название должно быть длиннее 3 символов. Попробуйте ещё раз.")
        return
    await state.update_data(item_name=item_name)
    await state.set_state(NMCKStates.waiting_for_okpd)
    await message.answer("📝 Введите **ОКПД2/КТРУ** (или '-' если нет):")


@router.message(NMCKStates.waiting_for_okpd)
async def process_okpd(message: Message, state: FSMContext):
    okpd = message.text.strip()
    await state.update_data(okpd=okpd)
    await state.set_state(NMCKStates.waiting_for_kp1_number)
    await message.answer("📝 Введите **входящий номер КП1**: (например, 9)")


@router.message(NMCKStates.waiting_for_kp1_number)
async def process_kp1_number(message: Message, state: FSMContext):
    await state.update_data(kp1_number=message.text.strip())
    await state.set_state(NMCKStates.waiting_for_kp1_date)
    await message.answer("📝 Введите **дату КП1** (в формате ДД.ММ.ГГГГ):")


@router.message(NMCKStates.waiting_for_kp1_date)
async def process_kp1_date(message: Message, state: FSMContext):
    await state.update_data(kp1_date=message.text.strip())
    await state.set_state(NMCKStates.waiting_for_kp2_number)
    await message.answer("📝 Введите **входящий номер КП2**: (например, 10)")


@router.message(NMCKStates.waiting_for_kp2_number)
async def process_kp2_number(message: Message, state: FSMContext):
    await state.update_data(kp2_number=message.text.strip())
    await state.set_state(NMCKStates.waiting_for_kp2_date)
    await message.answer("📝 Введите **дату КП2** (в формате ДД.ММ.ГГГГ):")


@router.message(NMCKStates.waiting_for_kp2_date)
async def process_kp2_date(message: Message, state: FSMContext):
    await state.update_data(kp2_date=message.text.strip())
    await state.set_state(NMCKStates.waiting_for_kp3_number)
    await message.answer("📝 Введите **входящий номер КП3**: (например, 11)")


@router.message(NMCKStates.waiting_for_kp3_number)
async def process_kp3_number(message: Message, state: FSMContext):
    await state.update_data(kp3_number=message.text.strip())
    await state.set_state(NMCKStates.waiting_for_kp3_date)
    await message.answer("📝 Введите **дату КП3** (в формате ДД.ММ.ГГГГ):")


@router.message(NMCKStates.waiting_for_kp3_date)
async def process_kp3_date(message: Message, state: FSMContext):
    await state.update_data(kp3_date=message.text.strip())
    await generate_final_pdf(message, state)


# ============================================================
# ФИНАЛЬНАЯ ГЕНЕРАЦИЯ PDF
# ============================================================

async def generate_final_pdf(message: Message, state: FSMContext):
    data = await state.get_data()
    
    method = data.get("calculation_method", "average")
    method_text = "Средняя арифметическая" if method == "average" else "Минимальная цена (письмо Минфина)"
    
    prices = [
        data.get("price_1", 0),
        data.get("price_2", 0),
        data.get("price_3", 0)
    ]
    kp_numbers = [
        data.get("kp1_number", ""),
        data.get("kp2_number", ""),
        data.get("kp3_number", "")
    ]
    kp_dates = [
        data.get("kp1_date", ""),
        data.get("kp2_date", ""),
        data.get("kp3_date", "")
    ]
    
    avg_price = sum(prices) / 3 if prices else 0
    variation = 0
    if avg_price > 0 and len(prices) >= 3:
        variance = sum((p - avg_price) ** 2 for p in prices) / 3
        std_dev = variance ** 0.5
        variation = (std_dev / avg_price) * 100 if avg_price > 0 else 0
    
    positions = [{
        "name": data.get("item_name", "Закупка"),
        "okpd": data.get("okpd", ""),
        "quantity": data.get("quantity", 1),
        "unit": "шт.",
        "prices": prices,
        "kp_numbers": kp_numbers,
        "kp_dates": kp_dates,
        "avg_price": avg_price,
        "variation": variation,
        "total_price": data.get("nmck_total", 0)
    }]
    
    suppliers = []
    for i in range(3):
        suppliers.append({
            "name": f"Поставщик {i+1}",
            "price": prices[i] if i < len(prices) else 0,
            "note": f"КП {i+1}"
        })
    
    pdf_data = prepare_pdf_data(
        procurement={
            "title": data.get("item_name", "Закупка"),
            "law_type": f"{data.get('law_type', '44')}-ФЗ",
            "nmck": data.get("nmck_total", 0),
            "nmck_method": method_text,
            "nmck_source": "ч. 6 ст. 22 44-ФЗ" if method == "average" else "письмо Минфина от 08.09.2017 № 24-01-09/58179",
        },
        suppliers=suppliers,
        timeline=[],
        company_name="ООО «Ваша компания»",
        responsible_person="Иванов И.И.",
        positions=positions,
        method=method
    )
    
    pdf_gen = PDFGenerator()
    pdf_bytes = pdf_gen.generate(pdf_data)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Сроки", callback_data="go_to_terms")
    builder.button(text="🆕 Новая закупка", callback_data="new_procurement")
    builder.button(text="🔙 Главное меню", callback_data="back_to_menu")
    builder.adjust(1)
    
    await message.answer_document(
        BufferedInputFile(pdf_bytes, filename=f"НМЦК_{datetime.now().strftime('%Y%m%d')}.pdf"),
        caption=f"📄 **Обоснование начальной (максимальной) цены контракта**\n\n"
                f"📊 Метод: {method_text}"
    )
    
    await state.clear()
    await message.answer(
        "Что делаем дальше?",
        reply_markup=builder.as_markup()
    )


# ============================================================
# ЗАГРУЗКА ФОТО/СКАНА (МНОГО ПОЗИЦИЙ) - ОТКЛЮЧЕНА
# ============================================================

@router.callback_query(lambda c: c.data == "input_photo")
async def input_photo(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        "⚠️ **Функция распознавания фото временно отключена на сервере.**\n\n"
        "Пожалуйста, используйте:\n"
        "• 📝 Ручной ввод\n"
        "• 📂 Загрузку Excel-файла\n\n"
        "Извините за неудобства!"
    )


# ============================================================
# ЗАГРУЗКА EXCEL (МНОГО ПОЗИЦИЙ) С УЛУЧШЕННЫМ ПАРСИНГОМ
# ============================================================

@router.callback_query(lambda c: c.data == "input_excel")
async def input_excel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(NMCKStates.waiting_for_excel)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📄 Скачать шаблон Excel", callback_data="download_template")
    builder.adjust(1)
    
    await callback.message.edit_text(
        "📂 Загрузите Excel-файл (`.xlsx` или `.xls`).\n\n"
        "Файл должен содержать колонки с ценами и реквизитами.\n"
        "Вы можете скачать шаблон:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(lambda c: c.data == "download_template")
async def download_template(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await send_template(callback.message)


@router.message(NMCKStates.waiting_for_excel, F.document)
async def handle_excel(message: Message, state: FSMContext):
    document = message.document
    if not document.file_name.endswith(('.xlsx', '.xls')):
        await message.answer("⚠️ Пожалуйста, загрузите файл Excel (.xlsx или .xls)")
        return

    file = await message.bot.get_file(document.file_id)
    file_path = f"temp/{document.file_id}.xlsx"
    os.makedirs("temp", exist_ok=True)
    await message.bot.download_file(file.file_path, file_path)

    await message.answer("🔍 Парсинг файла...")

    try:
        df = pd.read_excel(file_path, dtype=str)

        # Отладка: список колонок
        cols = list(df.columns)
        await message.answer(f"📋 Найдены колонки: {', '.join(cols)}")

        # Улучшенное сопоставление колонок
        col_map = {}
        for col in df.columns:
            col_str = str(col).strip().lower()
            # Убираем точки, пробелы, лишние символы
            col_clean = col_str.replace('.', '').replace(' ', '').replace('№', '').replace('(', '').replace(')', '')
            
            if 'п/п' in col_str or 'пп' in col_str or 'пп№' in col_clean:
                col_map['pp'] = col
            elif 'наименование' in col_str or 'название' in col_str:
                col_map['name'] = col
            elif 'окпд' in col_str:
                col_map['okpd'] = col
            elif 'ед.изм' in col_str or 'единиц' in col_str or col_clean == 'ед' or col_clean == 'единица':
                col_map['unit'] = col
            elif 'кол' in col_str or 'количество' in col_str:
                col_map['qty'] = col
            elif 'коммерческое предложение 1' in col_str or 'кп1' in col_str:
                col_map['price1'] = col
            elif 'коммерческое предложение 2' in col_str or 'кп2' in col_str:
                col_map['price2'] = col
            elif 'коммерческое предложение 3' in col_str or 'кп3' in col_str:
                col_map['price3'] = col

        # Выводим сопоставление
        mapping_info = "\n".join([f"{k} → {v}" for k, v in col_map.items()])
        await message.answer(f"🔍 Сопоставление колонок:\n{mapping_info}")

        required = ['pp', 'name', 'okpd', 'unit', 'qty', 'price1', 'price2', 'price3']
        missing = [k for k in required if k not in col_map]
        if missing:
            await message.answer(
                f"⚠️ Не найдены колонки: {', '.join(missing)}.\n"
                "Пожалуйста, используйте шаблон, скачанный через /template"
            )
            return

        positions = []
        for index, row in df.iterrows():
            if pd.isna(row[col_map['name']]) or str(row[col_map['name']]).strip() == '':
                continue

            try:
                price1 = float(str(row[col_map['price1']]).replace(',', '.').replace(' ', ''))
                price2 = float(str(row[col_map['price2']]).replace(',', '.').replace(' ', ''))
                price3 = float(str(row[col_map['price3']]).replace(',', '.').replace(' ', ''))
            except (ValueError, AttributeError):
                continue

            qty_str = str(row[col_map['qty']]).replace(',', '.').replace(' ', '')
            try:
                qty = float(qty_str)
            except ValueError:
                qty = 1.0

            positions.append({
                "name": str(row[col_map['name']]).strip(),
                "okpd": str(row[col_map['okpd']]).strip(),
                "unit": str(row[col_map['unit']]).strip(),
                "quantity": qty,
                "prices": [price1, price2, price3]
            })

        if not positions:
            await message.answer("❌ Не найдено данных для расчёта. Проверьте заполнение файла.")
            return

        await state.update_data(positions=positions)
        await calculate_multi_position_nmck(message, state, positions=positions)

    except Exception as e:
        await message.answer(f"❌ Ошибка парсинга: {e}\n\nПроверьте, что файл соответствует шаблону.")


# ============================================================
# РАСЧЁТ НМЦК ДЛЯ МНОГИХ ПОЗИЦИЙ
# ============================================================

async def calculate_multi_position_nmck(message: types.Message, state: FSMContext, positions=None):
    if positions is None:
        data = await state.get_data()
        positions = data.get("positions", [])
    
    if not positions:
        await message.answer("❌ Нет данных для расчёта.")
        return
    
    data = await state.get_data()
    method = data.get("calculation_method", "average")
    method_text = "средней цене" if method == "average" else "минимальной цене"
    
    all_prices = []
    for pos in positions:
        if 'prices' in pos:
            all_prices.extend(pos['prices'])
        else:
            all_prices.append(pos.get('price', 0))
    
    if len(all_prices) < 3:
        await message.answer("❌ Недостаточно цен для расчёта. Нужно минимум 3 цены.")
        return
    
    result = NMCKCalculator.calculate_nmck(prices=all_prices, method=method)
    
    total_nmck = 0
    for pos in positions:
        qty = pos.get('quantity', 1)
        if 'prices' in pos:
            avg_price = sum(pos['prices']) / len(pos['prices'])
        else:
            avg_price = pos.get('price', result['nmck'])
        total_nmck += avg_price * qty
    
    await state.update_data(
        nmck_result=result, 
        nmck=result['nmck'], 
        nmck_total=total_nmck, 
        positions=positions,
        calculation_method=method,
        nmck_for_terms=total_nmck
    )
    
    await state.set_state(NMCKStates.waiting_for_item_name)
    await message.answer(
        "📝 Введите **наименование позиции** (или 'все' для общей позиции):"
    )


# ============================================================
# ОБРАБОТЧИК КНОПКИ "НОВАЯ ЗАКУПКА" (из главного меню)
# ============================================================

@router.callback_query(lambda c: c.data == "new_procurement")
async def new_procurement(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "🔄 Начинаем новую закупку.\n"
        "Выберите закон:",
        reply_markup=InlineKeyboardBuilder().button(
            text="🔵 44-ФЗ", callback_data="law_44"
        ).button(
            text="🟢 223-ФЗ", callback_data="law_223"
        ).adjust(1).as_markup()
    )


# ============================================================
# КОМАНДА /template (скачивание Excel-шаблона)
# ============================================================

@router.message(Command("template"))
async def send_template(message: types.Message):
    """Отправка Excel-шаблона для заполнения НМЦК"""
    file_path = "static/nmck_template_v2.xlsx"
    if os.path.exists(file_path):
        await message.answer_document(
            types.FSInputFile(file_path),
            caption="📥 **Шаблон для заполнения НМЦК**\n\n"
                    "Заполните столбцы:\n"
                    "• Наименование позиции\n"
                    "• ОКПД2/КТРУ\n"
                    "• Ед. изм.\n"
                    "• Кол-во\n"
                    "• Цена КП1, КП2, КП3\n\n"
                    "После заполнения отправьте файл боту."
        )
    else:
        await message.answer("❌ Шаблон не найден. Обратитесь к администратору.")


# ============================================================
# ОБРАБОТЧИК НАЗАД (ГЛАВНОЕ МЕНЮ)
# ============================================================

@router.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
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


@router.callback_query(lambda c: c.data == "download_template_direct")
async def download_template_direct(callback: CallbackQuery):
    await callback.answer()
    await send_template(callback.message)