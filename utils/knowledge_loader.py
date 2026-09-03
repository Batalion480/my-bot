"""
Скрипт для заполнения базы знаний актуальными правилами 44-ФЗ и 223-ФЗ
Запускается один раз или при обновлении законодательства
"""

import asyncio
import sys
import os

# Добавляем корневую папку в путь, чтобы импортировать database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import Database


async def load_knowledge_base():
    """Загружает правила в базу знаний"""
    db = Database()
    await db.connect()

    # Очищаем старые данные
    await db.clear_knowledge_base()
    print("🧹 База знаний очищена")

    # ============================================================
    # 44-ФЗ: ЭЛЕКТРОННЫЙ АУКЦИОН
    # ============================================================
    rules_44_auction = [
        {
            "stage": "bid_submission",
            "article": "ст. 42 ч. 3 п. 2",
            "rule_text": "Срок подачи заявок — не менее 7 рабочих дней, если НМЦК ≤ 300 млн руб., и не менее 15 рабочих дней, если НМЦК > 300 млн руб.",
            "calculation_type": "nmck_based",
            "source": "ч. 3 п. 2 ст. 42 44-ФЗ (ред. 2022-2026)"
        },
        {
            "stage": "auction",
            "article": "ст. 49 ч. 3",
            "rule_text": "Аукцион проводится через 2 часа после окончания приема заявок (дата не меняется).",
            "calculation_type": "fixed_0_days",
            "source": "ч. 3 ст. 49 44-ФЗ (ред. 2022-2026)"
        },
        {
            "stage": "review",
            "article": "ст. 49 ч. 5",
            "rule_text": "Рассмотрение заявок — не позднее 2 рабочих дней после аукциона.",
            "calculation_type": "fixed_2_days",
            "source": "ч. 5 ст. 49 44-ФЗ (ред. 2022-2026)"
        },
        {
            "stage": "protocol",
            "article": "ст. 49 ч. 5",
            "rule_text": "Протокол подведения итогов размещается после рассмотрения заявок (в тот же день).",
            "calculation_type": "fixed_0_days",
            "source": "ч. 5 ст. 49 44-ФЗ (ред. 2022-2026)"
        },
        {
            "stage": "signing",
            "article": "ст. 51 ч. 1",
            "rule_text": "Подписание контракта — не ранее 10 календарных дней с даты протокола.",
            "calculation_type": "calendar_10_days",
            "source": "ч. 1 ст. 51 44-ФЗ (ред. 2022-2026)"
        }
    ]

    for rule in rules_44_auction:
        await db.insert_rule(
            law_type="44-FZ",
            procedure_type="auction",
            stage=rule["stage"],
            article=rule["article"],
            rule_text=rule["rule_text"],
            calculation_type=rule["calculation_type"],
            source=rule.get("source")
        )
    print("✅ 44-ФЗ (аукцион) загружен")

    # ============================================================
    # 44-ФЗ: ЗАПРОС КОТИРОВОК
    # ============================================================
    rules_44_quote = [
        {
            "stage": "bid_submission",
            "article": "ст. 50 ч. 1 (ст. 42 ч. 3 п. 3)",
            "rule_text": "Срок подачи заявок на запрос котировок — не менее 4 рабочих дней.",
            "calculation_type": "fixed_4_days",
            "source": "ч. 3 п. 3 ст. 42 44-ФЗ (ред. 2022-2026)"
        },
        {
            "stage": "review",
            "article": "ст. 50 ч. 3",
            "rule_text": "Рассмотрение заявок — не позднее 2 рабочих дней после окончания подачи.",
            "calculation_type": "fixed_2_days",
            "source": "ч. 3 ст. 50 44-ФЗ (ред. 2022-2026)"
        },
        {
            "stage": "signing",
            "article": "ст. 51 ч. 1",
            "rule_text": "Подписание контракта — не ранее 10 календарных дней с даты протокола.",
            "calculation_type": "calendar_10_days",
            "source": "ч. 1 ст. 51 44-ФЗ (ред. 2022-2026)"
        }
    ]

    for rule in rules_44_quote:
        await db.insert_rule(
            law_type="44-FZ",
            procedure_type="quote",
            stage=rule["stage"],
            article=rule["article"],
            rule_text=rule["rule_text"],
            calculation_type=rule["calculation_type"],
            source=rule.get("source")
        )
    print("✅ 44-ФЗ (запрос котировок) загружен")

    # ============================================================
    # 44-ФЗ: ЭЛЕКТРОННЫЙ КОНКУРС
    # ============================================================
    rules_44_competition = [
        {
            "stage": "bid_submission",
            "article": "ст. 42 ч. 3 п. 1",
            "rule_text": "Срок подачи заявок на конкурс — не менее 15 рабочих дней.",
            "calculation_type": "fixed_15_days",
            "source": "ч. 3 п. 1 ст. 42 44-ФЗ (ред. 2022-2026)"
        },
        {
            "stage": "review",
            "article": "ст. 48 ч. 3",
            "rule_text": "Рассмотрение заявок — не позднее 2 рабочих дней после окончания подачи.",
            "calculation_type": "fixed_2_days",
            "source": "ч. 3 ст. 48 44-ФЗ (ред. 2022-2026)"
        },
        {
            "stage": "signing",
            "article": "ст. 51 ч. 1",
            "rule_text": "Подписание контракта — не ранее 10 календарных дней с даты протокола.",
            "calculation_type": "calendar_10_days",
            "source": "ч. 1 ст. 51 44-ФЗ (ред. 2022-2026)"
        }
    ]

    for rule in rules_44_competition:
        await db.insert_rule(
            law_type="44-FZ",
            procedure_type="competition",
            stage=rule["stage"],
            article=rule["article"],
            rule_text=rule["rule_text"],
            calculation_type=rule["calculation_type"],
            source=rule.get("source")
        )
    print("✅ 44-ФЗ (конкурс) загружен")

    # ============================================================
    # 223-ФЗ: ЭЛЕКТРОННЫЙ АУКЦИОН (по Положению)
    # ============================================================
    rules_223_auction = [
        {
            "stage": "bid_submission",
            "article": "Положение заказчика (п. 2.1)",
            "rule_text": "Срок подачи заявок определяется Положением заказчика (вводится пользователем).",
            "calculation_type": "user_defined",
            "source": "223-ФЗ, Положение заказчика"
        },
        {
            "stage": "review",
            "article": "Положение заказчика (п. 3.1)",
            "rule_text": "Срок рассмотрения заявок определяется Положением заказчика (вводится пользователем).",
            "calculation_type": "user_defined",
            "source": "223-ФЗ, Положение заказчика"
        },
        {
            "stage": "signing",
            "article": "Положение заказчика (п. 4.1)",
            "rule_text": "Срок подписания контракта определяется Положением заказчика (вводится пользователем).",
            "calculation_type": "user_defined",
            "source": "223-ФЗ, Положение заказчика"
        }
    ]

    for rule in rules_223_auction:
        await db.insert_rule(
            law_type="223-FZ",
            procedure_type="auction",
            stage=rule["stage"],
            article=rule["article"],
            rule_text=rule["rule_text"],
            calculation_type=rule["calculation_type"],
            source=rule.get("source")
        )
    print("✅ 223-ФЗ (аукцион) загружен")

    # 223-ФЗ: ЗАПРОС КОТИРОВОК (по Положению)
    rules_223_quote = [
        {
            "stage": "bid_submission",
            "article": "Положение заказчика",
            "rule_text": "Срок подачи заявок определяется Положением заказчика (вводится пользователем).",
            "calculation_type": "user_defined",
            "source": "223-ФЗ, Положение заказчика"
        },
        {
            "stage": "review",
            "article": "Положение заказчика",
            "rule_text": "Срок рассмотрения заявок определяется Положением заказчика (вводится пользователем).",
            "calculation_type": "user_defined",
            "source": "223-ФЗ, Положение заказчика"
        },
        {
            "stage": "signing",
            "article": "Положение заказчика",
            "rule_text": "Срок подписания контракта определяется Положением заказчика (вводится пользователем).",
            "calculation_type": "user_defined",
            "source": "223-ФЗ, Положение заказчика"
        }
    ]

    for rule in rules_223_quote:
        await db.insert_rule(
            law_type="223-FZ",
            procedure_type="quote",
            stage=rule["stage"],
            article=rule["article"],
            rule_text=rule["rule_text"],
            calculation_type=rule["calculation_type"],
            source=rule.get("source")
        )
    print("✅ 223-ФЗ (запрос котировок) загружен")

    # 223-ФЗ: КОНКУРС (по Положению)
    rules_223_competition = [
        {
            "stage": "bid_submission",
            "article": "Положение заказчика",
            "rule_text": "Срок подачи заявок определяется Положением заказчика (вводится пользователем).",
            "calculation_type": "user_defined",
            "source": "223-ФЗ, Положение заказчика"
        },
        {
            "stage": "review",
            "article": "Положение заказчика",
            "rule_text": "Срок рассмотрения заявок определяется Положением заказчика (вводится пользователем).",
            "calculation_type": "user_defined",
            "source": "223-ФЗ, Положение заказчика"
        },
        {
            "stage": "signing",
            "article": "Положение заказчика",
            "rule_text": "Срок подписания контракта определяется Положением заказчика (вводится пользователем).",
            "calculation_type": "user_defined",
            "source": "223-ФЗ, Положение заказчика"
        }
    ]

    for rule in rules_223_competition:
        await db.insert_rule(
            law_type="223-FZ",
            procedure_type="competition",
            stage=rule["stage"],
            article=rule["article"],
            rule_text=rule["rule_text"],
            calculation_type=rule["calculation_type"],
            source=rule.get("source")
        )
    print("✅ 223-ФЗ (конкурс) загружен")

    print("\n🎉 База знаний загружена успешно!")
    print("📊 Всего правил загружено:", 
          len(rules_44_auction) + len(rules_44_quote) + len(rules_44_competition) +
          len(rules_223_auction) + len(rules_223_quote) + len(rules_223_competition))

    await db.close()


if __name__ == "__main__":
    asyncio.run(load_knowledge_base())