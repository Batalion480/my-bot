# ============================================================
# utils/date_calculator.py
# Модуль для расчёта НМЦК и дат по 44-ФЗ и 223-ФЗ
# ============================================================

from datetime import date, timedelta
from typing import List, Dict, Any, Optional
import re

from utils.calendar_data import is_working_day, is_holiday, is_weekend


# ============================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С ДАТАМИ
# ============================================================

def add_working_days(start_date: date, days: int) -> date:
    """
    Прибавляет указанное количество рабочих дней к дате
    (с учётом выходных и праздничных дней)
    
    Args:
        start_date: Дата старта
        days: Количество рабочих дней для добавления
    
    Returns:
        Новая дата
    """
    if days <= 0:
        return start_date
    
    current = start_date
    added = 0
    
    while added < days:
        current += timedelta(days=1)
        if is_working_day(current):
            added += 1
    
    return current


def add_calendar_days(start_date: date, days: int) -> date:
    """
    Прибавляет указанное количество календарных дней к дате
    (без учёта выходных)
    
    Args:
        start_date: Дата старта
        days: Количество календарных дней для добавления
    
    Returns:
        Новая дата
    """
    return start_date + timedelta(days=days)


def format_date(d: date) -> str:
    """Форматирует дату в формате ДД.ММ.ГГГГ"""
    if d is None:
        return "—"
    return d.strftime("%d.%m.%Y")


def parse_date(date_str: str) -> Optional[date]:
    """Парсит дату из строки в формате ДД.ММ.ГГГГ"""
    try:
        return datetime.strptime(date_str.strip(), "%d.%m.%Y").date()
    except (ValueError, TypeError):
        return None


def format_nmck_result(result: Dict) -> str:
    """
    Форматирует результат расчёта НМЦК для вывода в Telegram
    
    Args:
        result: Словарь с результатами от NMCKCalculator.calculate_nmck
    
    Returns:
        Отформатированный текст
    """
    nmck = result.get('nmck', 0)
    variation = result.get('variation_coefficient', 0) * 100
    warning = result.get('scatter_warning', '')
    
    text = (
        f"📊 **Результат расчёта НМЦК:**\n\n"
        f"💰 **НМЦК:** {nmck:,.2f} руб.\n"
        f"📊 Коэффициент вариации: {variation:.1f}%\n"
    )
    
    if warning:
        text += f"\n⚠️ {warning}"
    
    if result.get('prices'):
        text += f"\n\n📋 Использованы цены:\n"
        for i, price in enumerate(result['prices'], 1):
            text += f"  {i}. {price:,.2f} руб.\n"
    
    return text


# ============================================================
# КЛАСС NMCKCalculator
# ============================================================

class NMCKCalculator:
    """Класс для расчёта начальной (максимальной) цены контракта"""
    
    @staticmethod
    def calculate_nmck(prices: List[float], method: str = "average") -> Dict:
        """
        Рассчитывает НМЦК методом сопоставимых рыночных цен

        Args:
            prices: список цен (минимум 3)
            method: "average" - средняя цена, "minimum" - минимальная цена

        Returns:
            Словарь с результатами:
            - nmck: итоговая цена
            - variation_coefficient: коэффициент вариации
            - scatter_warning: предупреждение о разбросе цен
            - prices: использованные цены
            - avg_price: средняя цена
        """
        # Проверка на минимальное количество цен
        if len(prices) < 3:
            return {
                "nmck": 0,
                "variation_coefficient": 0,
                "scatter_warning": "⚠️ Для расчёта нужно минимум 3 цены.",
                "prices": prices,
                "avg_price": 0
            }

        # Удаляем нулевые значения
        valid_prices = [p for p in prices if p > 0]
        if len(valid_prices) < 3:
            return {
                "nmck": 0,
                "variation_coefficient": 0,
                "scatter_warning": "⚠️ После фильтрации осталось менее 3 цен.",
                "prices": valid_prices,
                "avg_price": 0
            }

        # Расчёт средней и дисперсии
        avg_price = sum(valid_prices) / len(valid_prices)
        variance = sum((p - avg_price) ** 2 for p in valid_prices) / len(valid_prices)
        std_dev = variance ** 0.5
        variation_coef = std_dev / avg_price if avg_price > 0 else 0

        # Итоговая цена
        if method == "minimum":
            nmck = min(valid_prices)
        else:
            nmck = avg_price

        # Предупреждение о разбросе
        scatter_warning = ""
        if variation_coef > 0.33:
            scatter_warning = "⚠️ Коэффициент вариации > 33%! Цены неоднородны. Рекомендуется проверить коммерческие предложения."

        return {
            "nmck": nmck,
            "variation_coefficient": variation_coef,
            "scatter_warning": scatter_warning,
            "prices": valid_prices,
            "avg_price": avg_price,
            "std_dev": std_dev,
            "method": method
        }

    @staticmethod
    def calculate_multiposition_nmck(positions: List[Dict], method: str = "average") -> Dict:
        """
        Рассчитывает НМЦК для нескольких позиций

        Args:
            positions: список позиций с полями:
                - name: наименование
                - okpd: ОКПД2/КТРУ
                - unit: единица измерения
                - quantity: количество
                - prices: список из 3 цен
            method: "average" или "minimum"

        Returns:
            Словарь с результатами по каждой позиции и итогом
        """
        result_positions = []
        total_nmck = 0
        total_scatter_warnings = []

        for idx, pos in enumerate(positions):
            prices = pos.get('prices', [])
            if not prices or len(prices) < 3:
                # Пропускаем позицию, если нет цен
                continue

            # Расчёт для позиции
            calc_result = NMCKCalculator.calculate_nmck(prices, method)

            qty = pos.get('quantity', 1)
            pos_nmck = calc_result['nmck'] * qty
            total_nmck += pos_nmck

            if calc_result.get('scatter_warning'):
                total_scatter_warnings.append({
                    "position": pos.get('name', f"Позиция {idx+1}"),
                    "warning": calc_result['scatter_warning']
                })

            result_positions.append({
                "name": pos.get('name', ''),
                "okpd": pos.get('okpd', ''),
                "unit": pos.get('unit', 'шт.'),
                "quantity": qty,
                "prices": prices,
                "avg_price": calc_result.get('avg_price', calc_result['nmck']),
                "variation": calc_result['variation_coefficient'] * 100,
                "total_price": pos_nmck,
                "scatter_warning": calc_result.get('scatter_warning', '')
            })

        # Формируем общее предупреждение
        scatter_warning_text = ""
        if total_scatter_warnings:
            scatter_warning_text = "⚠️ Есть позиции с неоднородными ценами:\n"
            for warn in total_scatter_warnings:
                scatter_warning_text += f"  • {warn['position']}: {warn['warning']}\n"

        return {
            "positions": result_positions,
            "total_nmck": total_nmck,
            "method": method,
            "scatter_warning": scatter_warning_text
        }


# ============================================================
# РАСЧЕТ ДАТ НА ОСНОВЕ БАЗЫ ЗНАНИЙ
# ============================================================

async def calculate_dates_from_db(
    law_type: str,
    procedure_type: str,
    publication_date: date,
    nmck: Optional[float],
    db,
    custom_params: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Рассчитывает даты на основе правил из базы знаний (knowledge_base).

    Args:
        law_type: "44-FZ" или "223-FZ"
        procedure_type: "auction", "quote", "competition"
        publication_date: дата публикации
        nmck: НМЦК (для 44-ФЗ)
        db: экземпляр Database
        custom_params: для 223-ФЗ: {'bid_days': int, 'review_days': int, 'signing_days': int}

    Returns:
        Словарь с датами и применёнными правилами
    """
    # Получаем правила для процедуры
    rules = await db.get_all_rules_for_procedure(law_type, procedure_type)
    rules_dict = {rule['stage']: rule for rule in rules}

    dates = {
        'publication_date': publication_date,
        'law_type': law_type,
        'procedure_type': procedure_type
    }
    applied_rules = {}

    # ---- 1. Подача заявок ----
    bid_rule = rules_dict.get('bid_submission')
    if bid_rule:
        calc_type = bid_rule['calculation_type']
        if calc_type == 'nmck_based':
            # Для 44-ФЗ: 7 или 15 дней в зависимости от НМЦК
            if nmck is not None and nmck <= 300_000_000:
                bid_days = 7
            else:
                bid_days = 15
        elif calc_type == 'fixed_7_days':
            bid_days = 7
        elif calc_type == 'fixed_15_days':
            bid_days = 15
        elif calc_type == 'fixed_4_days':
            bid_days = 4
        elif calc_type == 'user_defined':
            bid_days = custom_params.get('bid_days', 7) if custom_params else 7
        else:
            bid_days = 7
        
        dates['bid_end_date'] = add_working_days(publication_date, bid_days)
        dates['applied_bid_days'] = bid_days
        dates['bid_rule'] = bid_rule
        applied_rules['bid_submission'] = bid_rule
    else:
        # fallback
        bid_days = 7 if nmck and nmck <= 300_000_000 else 15
        dates['bid_end_date'] = add_working_days(publication_date, bid_days)
        dates['applied_bid_days'] = bid_days

    # ---- 2. Аукцион (если есть) ----
    auction_rule = rules_dict.get('auction')
    if auction_rule and auction_rule.get('calculation_type') in ('fixed_0_days', 'user_defined'):
        dates['auction_date'] = dates['bid_end_date']
        applied_rules['auction'] = auction_rule
    else:
        dates['auction_date'] = dates['bid_end_date']

    # ---- 3. Рассмотрение ----
    review_rule = rules_dict.get('review')
    if review_rule:
        calc_type = review_rule['calculation_type']
        if calc_type == 'fixed_2_days':
            review_days = 2
        elif calc_type == 'user_defined':
            review_days = custom_params.get('review_days', 2) if custom_params else 2
        else:
            review_days = 2
        
        dates['review_date'] = add_working_days(dates['auction_date'], review_days)
        dates['applied_review_days'] = review_days
        dates['review_rule'] = review_rule
        applied_rules['review'] = review_rule
    else:
        dates['review_date'] = add_working_days(dates['auction_date'], 2)
        dates['applied_review_days'] = 2

    # ---- 4. Протокол ----
    protocol_rule = rules_dict.get('protocol')
    if protocol_rule and protocol_rule.get('calculation_type') in ('fixed_0_days', 'user_defined'):
        dates['protocol_date'] = dates['review_date']
        applied_rules['protocol'] = protocol_rule
    else:
        dates['protocol_date'] = dates['review_date']

    # ---- 5. Подписание ----
    signing_rule = rules_dict.get('signing')
    if signing_rule:
        calc_type = signing_rule['calculation_type']
        if calc_type == 'calendar_10_days':
            signing_days = 10
        elif calc_type == 'user_defined':
            signing_days = custom_params.get('signing_days', 10) if custom_params else 10
        else:
            signing_days = 10
        
        dates['signing_date'] = add_calendar_days(dates['protocol_date'], signing_days)
        dates['applied_signing_days'] = signing_days
        dates['signing_rule'] = signing_rule
        applied_rules['signing'] = signing_rule
    else:
        dates['signing_date'] = add_calendar_days(dates['protocol_date'], 10)
        dates['applied_signing_days'] = 10

    # ---- Собираем источники ----
    sources = []
    for rule in rules:
        if rule.get('source'):
            sources.append(rule['source'])
    dates['law_source'] = '; '.join(sources) if sources else f'{law_type} (база знаний)'
    dates['applied_rules'] = applied_rules

    return dates


# ============================================================
# ДОПОЛНИТЕЛЬНЫЕ УТИЛИТЫ
# ============================================================

def get_working_days_between(start_date: date, end_date: date) -> int:
    """
    Возвращает количество рабочих дней между двумя датами
    (не включая start_date, включая end_date)
    """
    if start_date >= end_date:
        return 0
    
    count = 0
    current = start_date + timedelta(days=1)
    while current <= end_date:
        if is_working_day(current):
            count += 1
        current += timedelta(days=1)
    return count


def get_calendar_days_between(start_date: date, end_date: date) -> int:
    """Возвращает количество календарных дней между двумя датами"""
    if start_date >= end_date:
        return 0
    return (end_date - start_date).days


def shift_date_by_working_days(date_obj: date, days: int) -> date:
    """
    Сдвигает дату на указанное количество рабочих дней
    (положительное значение - вперёд, отрицательное - назад)
    """
    if days == 0:
        return date_obj
    
    direction = 1 if days > 0 else -1
    remaining = abs(days)
    current = date_obj
    
    while remaining > 0:
        current += timedelta(days=direction)
        if is_working_day(current):
            remaining -= 1
    
    return current


def shift_date_by_calendar_days(date_obj: date, days: int) -> date:
    """Сдвигает дату на указанное количество календарных дней"""
    return date_obj + timedelta(days=days)