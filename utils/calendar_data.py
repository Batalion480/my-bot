"""
Производственный календарь РФ на 2026-2027 годы
Для расчета рабочих дней с учетом праздников
"""

from datetime import date
from typing import Set, List


# Производственный календарь РФ на 2026-2027 гг.
# Формат: "YYYY-MM-DD" -> тип дня
# "holiday" - нерабочий праздничный день
# "preholiday" - сокращенный рабочий день (не влияет на расчет, но для справки)

RUSSIAN_HOLIDAYS = {
    # ===== 2026 год =====
    # Новогодние каникулы
    "2026-01-01": "holiday",
    "2026-01-02": "holiday",
    "2026-01-03": "holiday",
    "2026-01-04": "holiday",
    "2026-01-05": "holiday",
    "2026-01-06": "holiday",
    "2026-01-07": "holiday",  # Рождество
    "2026-01-08": "holiday",
    # День защитника Отечества
    "2026-02-23": "holiday",
    "2026-02-24": "holiday",
    "2026-02-25": "holiday",
    "2026-02-26": "holiday",
    "2026-02-27": "holiday",
    "2026-02-28": "holiday",
    # Международный женский день
    "2026-03-08": "holiday",
    "2026-03-09": "holiday",
    "2026-03-10": "holiday",
    "2026-03-11": "holiday",
    # Первомай
    "2026-05-01": "holiday",
    "2026-05-02": "holiday",
    "2026-05-03": "holiday",
    "2026-05-04": "holiday",
    "2026-05-05": "holiday",
    "2026-05-06": "holiday",
    "2026-05-07": "holiday",
    "2026-05-08": "holiday",
    "2026-05-09": "holiday",  # День Победы
    "2026-05-10": "holiday",
    "2026-05-11": "holiday",
    # День России
    "2026-06-12": "holiday",
    "2026-06-13": "holiday",
    "2026-06-14": "holiday",
    # День народного единства
    "2026-11-04": "holiday",
    "2026-11-05": "holiday",
    "2026-11-06": "holiday",
    "2026-11-07": "holiday",
    "2026-11-08": "holiday",
    # Предпраздничные дни (сокращенные, не влияют на расчет)
    "2026-02-20": "preholiday",
    "2026-03-06": "preholiday",
    "2026-04-30": "preholiday",
    "2026-06-11": "preholiday",
    "2026-11-03": "preholiday",
    "2026-12-31": "preholiday",
    
    # ===== 2027 год =====
    # Новогодние каникулы
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
    # День защитника Отечества
    "2027-02-23": "holiday",
    "2027-02-24": "holiday",
    "2027-02-25": "holiday",
    "2027-02-26": "holiday",
    "2027-02-27": "holiday",
    "2027-02-28": "holiday",
    # Международный женский день
    "2027-03-08": "holiday",
    "2027-03-09": "holiday",
    "2027-03-10": "holiday",
    "2027-03-11": "holiday",
    # Первомай
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
    # День России
    "2027-06-12": "holiday",
    "2027-06-13": "holiday",
    "2027-06-14": "holiday",
    # День народного единства
    "2027-11-04": "holiday",
    "2027-11-05": "holiday",
    "2027-11-06": "holiday",
    "2027-11-07": "holiday",
    "2027-11-08": "holiday",
    # Предпраздничные дни
    "2027-02-20": "preholiday",
    "2027-03-05": "preholiday",
    "2027-04-30": "preholiday",
    "2027-06-11": "preholiday",
    "2027-11-03": "preholiday",
    "2027-12-31": "preholiday",
}


def is_weekend(date_obj: date) -> bool:
    """
    Проверяет, является ли день выходным (суббота или воскресенье)
    
    Args:
        date_obj: Объект даты
    
    Returns:
        True, если день выходной
    """
    return date_obj.weekday() >= 5


def is_holiday(date_obj: date) -> bool:
    """
    Проверяет, является ли день праздничным по производственному календарю
    
    Args:
        date_obj: Объект даты
    
    Returns:
        True, если день праздничный
    """
    date_str = date_obj.strftime("%Y-%m-%d")
    return RUSSIAN_HOLIDAYS.get(date_str) == "holiday"


def is_working_day(date_obj: date) -> bool:
    """
    Проверяет, является ли день рабочим
    
    Args:
        date_obj: Объект даты
    
    Returns:
        True, если день рабочий
    """
    return not is_weekend(date_obj) and not is_holiday(date_obj)


def get_holidays_for_year(year: int) -> List[str]:
    """
    Возвращает список праздничных дней для указанного года
    
    Args:
        year: Год (например, 2026)
    
    Returns:
        Список строк с датами в формате "YYYY-MM-DD"
    """
    result = []
    for date_str, day_type in RUSSIAN_HOLIDAYS.items():
        if date_str.startswith(str(year)) and day_type == "holiday":
            result.append(date_str)
    return result


def get_holidays_set_for_year(year: int) -> Set[str]:
    """
    Возвращает множество праздничных дней для указанного года
    
    Args:
        year: Год (например, 2026)
    
    Returns:
        Множество строк с датами в формате "YYYY-MM-DD"
    """
    return set(get_holidays_for_year(year))