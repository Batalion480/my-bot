"""
Модуль анализа рисков при сдвиге дат публикации
Для Telegram-бота «Смета+Срок»
"""

from datetime import date, timedelta
from typing import Dict, List, Tuple, Optional

from utils.calendar_data import is_working_day, is_holiday, is_weekend


def analyze_shift_risks(
    old_dates: Dict,
    new_dates: Dict,
    law_type: str,
    nmck: Optional[float] = None,
    shift_days: int = 0
) -> List[Tuple[str, str]]:
    """
    Анализирует риски при сдвиге дат публикации.

    Args:
        old_dates: Словарь с исходными датами
        new_dates: Словарь с новыми датами
        law_type: "44-FZ" или "223-FZ"
        nmck: НМЦК (для проверки минимального срока по 44-ФЗ)
        shift_days: Количество дней сдвига (положительное = вперед, отрицательное = назад)

    Returns:
        Список кортежей (тип_риска, описание)
        Тип риска: "warning" - предупреждение, "critical" - критическая ошибка
    """
    risks = []

    # ============================================================
    # 1. Проверка на выходные и праздничные дни
    # ============================================================
    date_fields = ["publication_date", "bid_end_date", "consideration_date", "auction_date", "signing_date"]
    
    for key in date_fields:
        if key in new_dates and new_dates.get(key):
            dt = new_dates[key]
            if is_weekend(dt):
                risks.append((
                    "warning",
                    f"📅 Дата **{key.replace('_', ' ')}** ({dt.strftime('%d.%m.%Y')}) выпадает на **выходной день**."
                ))
            elif is_holiday(dt):
                risks.append((
                    "warning",
                    f"📅 Дата **{key.replace('_', ' ')}** ({dt.strftime('%d.%m.%Y')}) выпадает на **праздничный день**."
                ))

    # ============================================================
    # 2. Проверка минимального срока подачи заявок (только для 44-ФЗ)
    # ============================================================
    if law_type == "44-FZ" and nmck is not None:
        # Считаем рабочие дни между публикацией и окончанием подачи
        working_days = 0
        current = new_dates["publication_date"]
        end_date = new_dates["bid_end_date"]
        
        while current < end_date:
            if is_working_day(current):
                working_days += 1
            current += timedelta(days=1)
        
        # Определяем минимальный срок
        min_days = 7 if nmck <= 3_000_000 else 15
        
        if working_days < min_days:
            risks.append((
                "critical",
                f"⛔ Срок подачи заявок составляет **{working_days}** рабочих дней, "
                f"что меньше минимального **{min_days}** дней по 44-ФЗ.\n"
                f"Требуется увеличить сдвиг или изменить дату публикации."
            ))
        elif working_days < min_days + 3:
            risks.append((
                "warning",
                f"⚠️ Срок подачи заявок составляет **{working_days}** рабочих дней. "
                f"Минимальный срок по 44-ФЗ — **{min_days}** дней. "
                f"Рекомендуется добавить 1-2 дня для запаса."
            ))

    # ============================================================
    # 3. Проверка срока передачи банковской гарантии
    # ============================================================
    if "bg_deadline_date" in new_dates and new_dates.get("bg_deadline_date"):
        bg_days = 0
        current = new_dates["bg_deadline_date"]
        signing_date = new_dates["signing_date"]
        
        while current < signing_date:
            if is_working_day(current):
                bg_days += 1
            current += timedelta(days=1)
        
        if bg_days < 5:
            risks.append((
                "critical",
                f"❌ На проверку банковской гарантии остается **{bg_days}** рабочих дней "
                f"вместо рекомендованных **5**.\n"
                f"Это высокий риск отклонения банковской гарантии."
            ))
        elif bg_days < 7:
            risks.append((
                "warning",
                f"⚠️ На проверку банковской гарантии остается **{bg_days}** рабочих дней. "
                f"Рекомендуется закладывать минимум 5 дней."
            ))

    # ============================================================
    # 4. Проверка на затягивание сроков (сдвиг вперед более чем на 10 дней)
    # ============================================================
    if shift_days > 10:
        risks.append((
            "warning",
            f"⚠️ Вы отложили публикацию на **{shift_days}** дней.\n"
            f"Это может привести к срыву исполнения контракта, "
            f"особенно если закупка планируется на конец года."
        ))
    elif shift_days > 5:
        risks.append((
            "warning",
            f"⚠️ Вы отложили публикацию на **{shift_days}** дней.\n"
            f"Рекомендуется согласовать новый график с руководством."
        ))

    # ============================================================
    # 5. Проверка на ускорение (сдвиг назад более чем на 5 дней)
    # ============================================================
    if shift_days < -5:
        risks.append((
            "warning",
            f"⚠️ Вы ускорили публикацию на **{abs(shift_days)}** дней.\n"
            f"Убедитесь, что все документы готовы к размещению."
        ))

    # ============================================================
    # 6. Проверка на попадание подписания в праздничные периоды
    # ============================================================
    signing_date = new_dates.get("signing_date")
    if signing_date:
        # Новогодние каникулы
        if signing_date.month == 1 and signing_date.day <= 15:
            risks.append((
                "warning",
                f"❌ Подписание контракта ({signing_date.strftime('%d.%m.%Y')}) "
                f"попадает на **новогодние каникулы**.\n"
                f"Фактический перенос на рабочие дни позже."
            ))
        # Майские праздники
        elif signing_date.month == 5 and signing_date.day <= 15:
            risks.append((
                "warning",
                f"❌ Подписание контракта ({signing_date.strftime('%d.%m.%Y')}) "
                f"попадает на **майские праздники**.\n"
                f"Фактический перенос на рабочие дни позже."
            ))

    # ============================================================
    # 7. Проверка на общий срок закупки (не более 90 дней)
    # ============================================================
    total_days = (new_dates["signing_date"] - new_dates["publication_date"]).days
    if total_days > 90:
        risks.append((
            "warning",
            f"⚠️ Общий срок закупки составляет **{total_days}** календарных дней.\n"
            f"Рекомендуется не превышать 90 дней для соблюдения бюджетного планирования."
        ))

    # ============================================================
    # 8. Проверка: не слишком ли близко окончание подачи к праздникам
    # ============================================================
    bid_end = new_dates.get("bid_end_date")
    if bid_end:
        # Проверяем, не выпадает ли окончание подачи на пятницу перед длинными выходными
        if bid_end.weekday() == 4:  # Пятница
            # Проверяем, есть ли праздник в понедельник
            next_monday = bid_end + timedelta(days=3)
            if is_holiday(next_monday):
                risks.append((
                    "warning",
                    f"⚠️ Окончание подачи заявок ({bid_end.strftime('%d.%m.%Y')}) "
                    f"выпадает на пятницу перед праздничными выходными.\n"
                    f"Убедитесь, что у вас есть запас времени на обработку заявок."
                ))

    return risks


def format_risks_for_output(risks: List[Tuple[str, str]]) -> str:
    """
    Форматирует список рисков для вывода в Telegram.

    Args:
        risks: Список кортежей (тип_риска, описание)

    Returns:
        Отформатированный текст с эмодзи
    """
    if not risks:
        return "✅ **Рисков не обнаружено.** Все сроки соблюдены."

    # Разделяем на критические и предупреждения
    critical = []
    warnings = []

    for risk_type, description in risks:
        if risk_type == "critical":
            critical.append(description)
        else:
            warnings.append(description)

    result = ""

    if critical:
        result += "⛔ **КРИТИЧЕСКИЕ РИСКИ!**\n\n"
        for item in critical:
            result += f"{item}\n\n"
        result += "─" * 30 + "\n\n"

    if warnings:
        result += "⚠️ **Предупреждения:**\n\n"
        for item in warnings:
            result += f"{item}\n\n"

    return result.strip()


def get_risk_level(risks: List[Tuple[str, str]]) -> str:
    """
    Определяет общий уровень риска.

    Args:
        risks: Список рисков

    Returns:
        "critical" - есть критические риски
        "warning" - есть предупреждения
        "safe" - рисков нет
    """
    if any(r[0] == "critical" for r in risks):
        return "critical"
    elif risks:
        return "warning"
    return "safe"


def get_risk_emoji(risks: List[Tuple[str, str]]) -> str:
    """Возвращает эмодзи в зависимости от уровня риска"""
    level = get_risk_level(risks)
    if level == "critical":
        return "🔴"
    elif level == "warning":
        return "🟡"
    return "🟢"