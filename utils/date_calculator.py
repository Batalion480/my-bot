"""
Модуль расчета НМЦК и рабочих дней для Telegram-бота «Смета+Срок»
Версия: 2.0
Дата: 01.09.2026

Содержит:
1. Производственный календарь РФ (2026-2027)
2. Расчет рабочих дней с учетом праздников
3. Расчет НМЦК с коэффициентом вариации
4. Расчет дат по 44-ФЗ и 223-ФЗ
"""

import math
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple, Any


# ============================================================
# БЛОК 1: ПРОИЗВОДСТВЕННЫЙ КАЛЕНДАРЬ
# ============================================================

# Производственный календарь РФ на 2026-2027 гг.
RUSSIAN_HOLIDAYS = {
    # ===== 2026 год =====
    "2026-01-01": "holiday",
    "2026-01-02": "holiday",
    "2026-01-03": "holiday",
    "2026-01-04": "holiday",
    "2026-01-05": "holiday",
    "2026-01-06": "holiday",
    "2026-01-07": "holiday",
    "2026-01-08": "holiday",
    "2026-02-23": "holiday",
    "2026-02-24": "holiday",
    "2026-02-25": "holiday",
    "2026-02-26": "holiday",
    "2026-02-27": "holiday",
    "2026-02-28": "holiday",
    "2026-03-08": "holiday",
    "2026-03-09": "holiday",
    "2026-03-10": "holiday",
    "2026-03-11": "holiday",
    "2026-05-01": "holiday",
    "2026-05-02": "holiday",
    "2026-05-03": "holiday",
    "2026-05-04": "holiday",
    "2026-05-05": "holiday",
    "2026-05-06": "holiday",
    "2026-05-07": "holiday",
    "2026-05-08": "holiday",
    "2026-05-09": "holiday",
    "2026-05-10": "holiday",
    "2026-05-11": "holiday",
    "2026-06-12": "holiday",
    "2026-06-13": "holiday",
    "2026-06-14": "holiday",
    "2026-11-04": "holiday",
    "2026-11-05": "holiday",
    "2026-11-06": "holiday",
    "2026-11-07": "holiday",
    "2026-11-08": "holiday",
    "2026-02-20": "preholiday",
    "2026-03-06": "preholiday",
    "2026-04-30": "preholiday",
    "2026-06-11": "preholiday",
    "2026-11-03": "preholiday",
    "2026-12-31": "preholiday",
    # ===== 2027 год =====
    "2027-01-01": "holiday",
    "2027-01-02": "holiday",
    "2027-01-03": "holiday",
    "2027-01-04": "holiday",
    "2027-01-05": "holiday",
    "2027-01-06": "holiday",
    "2027-01-07": "holiday",
    "2027-01-08": "holiday",
    "2027-01-09": "holiday",
    "2027-01-10": "holiday",
    "2027-01-11": "holiday",
    "2027-02-23": "holiday",
    "2027-02-24": "holiday",
    "2027-02-25": "holiday",
    "2027-02-26": "holiday",
    "2027-02-27": "holiday",
    "2027-02-28": "holiday",
    "2027-03-08": "holiday",
    "2027-03-09": "holiday",
    "2027-03-10": "holiday",
    "2027-03-11": "holiday",
    "2027-05-01": "holiday",
    "2027-05-02": "holiday",
    "2027-05-03": "holiday",
    "2027-05-04": "holiday",
    "2027-05-05": "holiday",
    "2027-05-06": "holiday",
    "2027-05-07": "holiday",
    "2027-05-08": "holiday",
    "2027-05-09": "holiday",
    "2027-05-10": "holiday",
    "2027-06-12": "holiday",
    "2027-06-13": "holiday",
    "2027-06-14": "holiday",
    "2027-11-04": "holiday",
    "2027-11-05": "holiday",
    "2027-11-06": "holiday",
    "2027-11-07": "holiday",
    "2027-11-08": "holiday",
    "2027-02-20": "preholiday",
    "2027-03-05": "preholiday",
    "2027-04-30": "preholiday",
    "2027-06-11": "preholiday",
    "2027-11-03": "preholiday",
    "2027-12-31": "preholiday",
}


def is_weekend(date_obj: date) -> bool:
    """Проверяет, является ли день выходным (суббота или воскресенье)"""
    return date_obj.weekday() >= 5


def is_holiday(date_obj: date) -> bool:
    """Проверяет, является ли день праздничным по производственному календарю"""
    date_str = date_obj.strftime("%Y-%m-%d")
    return RUSSIAN_HOLIDAYS.get(date_str) == "holiday"


def is_working_day(date_obj: date) -> bool:
    """Проверяет, является ли день рабочим"""
    return not is_weekend(date_obj) and not is_holiday(date_obj)


def add_working_days(start_date: date, days: int) -> date:
    """
    Прибавляет N рабочих дней к дате с учетом праздников и выходных.

    Args:
        start_date: Начальная дата
        days: Количество рабочих дней (может быть положительным или отрицательным)

    Returns:
        Дата через N рабочих дней
    """
    if days == 0:
        return start_date

    current_date = start_date
    added_days = 0
    step = 1 if days > 0 else -1

    while added_days < abs(days):
        current_date += timedelta(days=step)
        if is_working_day(current_date):
            added_days += 1

    return current_date


def count_working_days(start_date: date, end_date: date) -> int:
    """Подсчитывает количество рабочих дней между двумя датами"""
    if start_date >= end_date:
        raise ValueError("start_date должна быть меньше end_date")

    current = start_date
    count = 0

    while current < end_date:
        if is_working_day(current):
            count += 1
        current += timedelta(days=1)

    return count


def get_holidays_for_year(year: int) -> List[str]:
    """Возвращает список праздничных дней для указанного года"""
    result = []
    for date_str, day_type in RUSSIAN_HOLIDAYS.items():
        if date_str.startswith(str(year)) and day_type == "holiday":
            result.append(date_str)
    return result


# ============================================================
# БЛОК 2: РАСЧЕТ НМЦК С КОЭФФИЦИЕНТОМ ВАРИАЦИИ
# ============================================================

class NMCKCalculator:
    """Класс для расчета НМЦК с коэффициентом вариации"""

    MAX_VARIATION_COEFFICIENT = 0.33  # 33% — допустимый разброс

    @staticmethod
    def calculate_average(prices: List[float]) -> float:
        """Рассчитывает среднее арифметическое"""
        if not prices:
            raise ValueError("Список цен не может быть пустым")
        return round(sum(prices) / len(prices), 2)

    @staticmethod
    def calculate_standard_deviation(prices: List[float]) -> float:
        """Рассчитывает стандартное отклонение"""
        if len(prices) < 2:
            return 0.0
        mean = sum(prices) / len(prices)
        variance = sum((x - mean) ** 2 for x in prices) / (len(prices) - 1)
        return round(math.sqrt(variance), 2)

    @staticmethod
    def calculate_variation_coefficient(prices: List[float]) -> float:
        """Рассчитывает коэффициент вариации"""
        mean = sum(prices) / len(prices)
        if mean == 0:
            return 0.0
        std_dev = NMCKCalculator.calculate_standard_deviation(prices)
        return round(std_dev / mean, 4)

    @staticmethod
    def check_price_scatter(prices: List[float], max_variation: float = MAX_VARIATION_COEFFICIENT) -> Tuple[bool, str]:
        """Проверяет разброс цен с помощью коэффициента вариации"""
        if len(prices) < 2:
            return True, ""

        variation = NMCKCalculator.calculate_variation_coefficient(prices)
        variation_percent = variation * 100

        if variation > max_variation:
            max_price = max(prices)
            min_price = min(prices)
            avg = sum(prices) / len(prices)

            return False, (
                f"⚠️ Разброс цен слишком велик! Коэффициент вариации = {variation_percent:.1f}% "
                f"(допустимо ≤ {max_variation * 100:.0f}%).\n"
                f"Максимальная цена: {max_price:,.2f} руб., минимальная: {min_price:,.2f} руб., "
                f"средняя: {avg:,.2f} руб.\n"
                f"Рекомендуется запросить дополнительные коммерческие предложения."
            )

        return True, f"✅ Разброс цен в норме (коэффициент вариации = {variation_percent:.1f}%)"

    @staticmethod
    def calculate_nmck(
        prices: List[float],
        suppliers_info: Optional[List[Dict[str, Any]]] = None,
        weights: Optional[List[float]] = None,
        apply_inflation: bool = True,
        max_variation: float = MAX_VARIATION_COEFFICIENT,
    ) -> Dict[str, Any]:
        """Главный метод расчета НМЦК"""

        original_prices = prices.copy()
        adjusted_prices = prices.copy()
        suppliers_data = []

        # Применяем инфляцию
        if apply_inflation and suppliers_info:
            for i, supplier in enumerate(suppliers_info):
                if i < len(adjusted_prices):
                    months_ago = supplier.get("months_ago", 0)
                    if months_ago >= 6:
                        inflation_factor = 1 + (months_ago // 6) * 0.03
                        adjusted_prices[i] = round(adjusted_prices[i] * inflation_factor, 2)

        # Формируем данные о поставщиках
        for i, price in enumerate(original_prices):
            suppliers_data.append({
                "name": suppliers_info[i].get("name", f"Поставщик {i+1}") if suppliers_info else f"Поставщик {i+1}",
                "inn": suppliers_info[i].get("inn", "") if suppliers_info else "",
                "price": price,
                "adjusted_price": adjusted_prices[i] if i < len(adjusted_prices) else price,
                "months_ago": suppliers_info[i].get("months_ago", 0) if suppliers_info else 0,
            })

        # Проверка разброса
        is_valid, scatter_warning = NMCKCalculator.check_price_scatter(adjusted_prices, max_variation)

        # Среднее арифметическое
        average = NMCKCalculator.calculate_average(adjusted_prices)

        # Стандартное отклонение
        std_dev = NMCKCalculator.calculate_standard_deviation(adjusted_prices)

        # Коэффициент вариации
        variation = NMCKCalculator.calculate_variation_coefficient(adjusted_prices)

        # Средневзвешенное
        weighted_average = None
        if weights:
            try:
                weighted_average = NMCKCalculator.calculate_weighted_average(adjusted_prices, weights)
            except ValueError:
                weighted_average = None

        nmck = weighted_average if weighted_average is not None else average

        return {
            "nmck": nmck,
            "average": average,
            "weighted_average": weighted_average,
            "standard_deviation": std_dev,
            "variation_coefficient": variation,
            "original_prices": original_prices,
            "adjusted_prices": adjusted_prices,
            "scatter_warning": scatter_warning,
            "is_valid": is_valid,
            "suppliers": suppliers_data,
        }

    @staticmethod
    def calculate_weighted_average(prices: List[float], weights: List[float]) -> float:
        """Рассчитывает средневзвешенное значение"""
        if len(prices) != len(weights):
            raise ValueError("Количество цен и весов должно совпадать")
        if abs(sum(weights) - 1.0) > 0.001:
            raise ValueError("Сумма весов должна быть равна 1.0")
        return round(sum(p * w for p, w in zip(prices, weights)), 2)


# ============================================================
# БЛОК 3: РАСЧЕТ ДАТ ПО 44-ФЗ И 223-ФЗ
# ============================================================

def get_min_bid_days_by_44fz(nmck: float) -> int:
    """Определяет минимальный срок подачи заявок по 44-ФЗ"""
    return 7 if nmck <= 3_000_000 else 15


def calculate_44fz_dates(publication_date: date, nmck: float) -> Dict[str, Any]:
    """Рассчитывает даты по 44-ФЗ"""
    bid_days = get_min_bid_days_by_44fz(nmck)

    bid_end_date = add_working_days(publication_date, bid_days)
    consideration_date = add_working_days(bid_end_date, 7)
    auction_date = add_working_days(consideration_date, 2)
    signing_date = add_working_days(auction_date, 5)
    bg_deadline_date = add_working_days(signing_date, -5)

    return {
        "publication_date": publication_date,
        "bid_end_date": bid_end_date,
        "consideration_date": consideration_date,
        "auction_date": auction_date,
        "signing_date": signing_date,
        "bg_deadline_date": bg_deadline_date,
        "applied_bid_days": bid_days,
        "applied_review_days": 7,
        "applied_signing_days": 5,
    }


def calculate_223fz_dates(
    publication_date: date,
    bid_submission_days: int,
    bid_review_days: int,
    auction_delay_days: int = 2,
    signing_days: int = 5,
    bg_days_before_signing: int = 5,
) -> Dict[str, Any]:
    """Рассчитывает даты по 223-ФЗ"""
    bid_end_date = add_working_days(publication_date, bid_submission_days)
    consideration_date = add_working_days(bid_end_date, bid_review_days)
    auction_date = add_working_days(consideration_date, auction_delay_days)
    signing_date = add_working_days(auction_date, signing_days)
    bg_deadline_date = add_working_days(signing_date, -bg_days_before_signing)

    return {
        "publication_date": publication_date,
        "bid_end_date": bid_end_date,
        "consideration_date": consideration_date,
        "auction_date": auction_date,
        "signing_date": signing_date,
        "bg_deadline_date": bg_deadline_date,
        "applied_bid_days": bid_submission_days,
        "applied_review_days": bid_review_days,
        "applied_signing_days": signing_days,
    }


def calculate_dates(
    law_type: str,
    publication_date: date,
    nmck: Optional[float] = None,
    bid_submission_days: Optional[int] = None,
    bid_review_days: Optional[int] = None,
    signing_days: int = 5,
) -> Dict[str, Any]:
    """Универсальная функция расчета дат"""
    if law_type == "44-FZ":
        if nmck is None:
            raise ValueError("Для 44-ФЗ необходимо указать НМЦК")
        return calculate_44fz_dates(publication_date, nmck)
    elif law_type == "223-FZ":
        if bid_submission_days is None or bid_review_days is None:
            raise ValueError("Для 223-ФЗ необходимо указать сроки подачи и рассмотрения")
        return calculate_223fz_dates(
            publication_date,
            bid_submission_days,
            bid_review_days,
            signing_days=signing_days
        )
    else:
        raise ValueError(f"Неизвестный тип закона: {law_type}")


# ============================================================
# БЛОК 4: ФОРМАТИРОВАНИЕ ДЛЯ ВЫВОДА
# ============================================================

def format_date(d: date) -> str:
    """Форматирует дату в строку ДД.ММ.ГГГГ"""
    return d.strftime("%d.%m.%Y")


def format_dates_dict(dates: Dict[str, Any]) -> str:
    """Форматирует словарь с датами для вывода в Telegram"""
    lines = []
    lines.append(f"📄 Публикация: {format_date(dates['publication_date'])}")
    lines.append(f"📩 Окончание подачи: {format_date(dates['bid_end_date'])}")
    lines.append(f"🔍 Рассмотрение: {format_date(dates['consideration_date'])}")
    if dates.get('auction_date'):
        lines.append(f"⚡ Торги: {format_date(dates['auction_date'])}")
    lines.append(f"✍️ Подписание контракта: {format_date(dates['signing_date'])}")
    if dates.get('bg_deadline_date'):
        lines.append(f"🔒 Срок передачи БГ: {format_date(dates['bg_deadline_date'])}")
    return "\n".join(lines)


def format_nmck_result(result: Dict[str, Any]) -> str:
    """Форматирует результат расчета НМЦК для вывода в Telegram"""
    lines = []
    lines.append("📊 **Результат расчета НМЦК:**")
    lines.append("")

    for supplier in result.get("suppliers", []):
        price = supplier.get("price", 0)
        adjusted = supplier.get("adjusted_price", price)
        name = supplier.get("name", "Поставщик")
        if adjusted != price:
            lines.append(f"💰 {name}: {price:,.2f} руб. → с учетом инфляции: {adjusted:,.2f} руб.")
        else:
            lines.append(f"💰 {name}: {price:,.2f} руб.")

    lines.append("")
    lines.append(f"📈 Среднее арифметическое: **{result['average']:,.2f} руб.**")
    lines.append(f"📊 Коэффициент вариации: {result['variation_coefficient'] * 100:.1f}%")
    lines.append("")
    lines.append(f"✅ Итоговая НМЦК: **{result['nmck']:,.2f} руб.**")
    lines.append("")
    lines.append(result.get("scatter_warning", ""))

    return "\n".join(lines)