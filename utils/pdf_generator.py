# ============================================================
# utils/pdf_generator.py
# Генерация PDF-документов (НМЦК и сроки)
# ============================================================

import os
import tempfile
from datetime import datetime
from typing import List, Dict, Any, Optional

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

import locale

# Устанавливаем локаль для форматирования чисел
try:
    locale.setlocale(locale.LC_ALL, 'ru_RU.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'Russian_Russia.1251')
    except:
        pass


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def number_to_words_rubles(n: float) -> str:
    """Преобразует число в пропись (рубли) с копейками"""
    rubles = int(n)
    kopecks = int(round((n - rubles) * 100))
    
    units = ['', 'один', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять']
    teens = ['десять', 'одиннадцать', 'двенадцать', 'тринадцать', 'четырнадцать', 
             'пятнадцать', 'шестнадцать', 'семнадцать', 'восемнадцать', 'девятнадцать']
    tens = ['', '', 'двадцать', 'тридцать', 'сорок', 'пятьдесят', 
            'шестьдесят', 'семьдесят', 'восемьдесят', 'девяносто']
    hundreds = ['', 'сто', 'двести', 'триста', 'четыреста', 'пятьсот', 
                'шестьсот', 'семьсот', 'восемьсот', 'девятьсот']
    
    def num_to_words(num: int) -> str:
        if num == 0:
            return 'ноль'
        if num < 0:
            return 'минус ' + num_to_words(abs(num))
        
        result = []
        
        if num >= 1000000:
            millions = num // 1000000
            num %= 1000000
            if millions == 1:
                result.append('один миллион')
            elif 2 <= millions <= 4:
                result.append(f'{num_to_words(millions)} миллиона')
            else:
                result.append(f'{num_to_words(millions)} миллионов')
        
        if num >= 1000:
            thousands = num // 1000
            num %= 1000
            if thousands == 1:
                result.append('одна тысяча')
            elif thousands == 2:
                result.append('две тысячи')
            elif 3 <= thousands <= 4:
                result.append(f'{num_to_words(thousands)} тысячи')
            else:
                result.append(f'{num_to_words(thousands)} тысяч')
        
        if num >= 100:
            hundreds_part = num // 100
            num %= 100
            result.append(hundreds[hundreds_part])
        
        if num >= 20:
            tens_part = num // 10
            num %= 10
            result.append(tens[tens_part])
            if num > 0:
                result.append(units[num])
        elif 10 <= num <= 19:
            result.append(teens[num - 10])
        elif num > 0:
            result.append(units[num])
        
        return ' '.join([r for r in result if r])
    
    rubles_words = num_to_words(rubles) if rubles > 0 else 'ноль'
    
    if rubles % 10 == 1 and rubles % 100 != 11:
        ruble_word = 'рубль'
    elif 2 <= rubles % 10 <= 4 and (rubles % 100 < 10 or rubles % 100 >= 20):
        ruble_word = 'рубля'
    else:
        ruble_word = 'рублей'
    
    kopecks_word = f"{kopecks:02d} коп."
    
    return f"{rubles_words} {ruble_word} {kopecks_word}"


def get_template_dir() -> str:
    """Возвращает путь к папке с шаблонами"""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')


def format_date(d) -> str:
    """Форматирует дату в формат ДД.ММ.ГГГГ"""
    if d is None:
        return "—"
    if isinstance(d, str):
        return d
    return d.strftime("%d.%m.%Y")


# ============================================================
# ГЕНЕРАЦИЯ PDF ДЛЯ СРОКОВ
# ============================================================

def generate_terms_pdf(
    dates: Dict[str, Any],
    law_type: str = "44-ФЗ",
    nmck: float = None,
    company_name: str = "ООО «Ваша компания»",
    responsible_person: str = "Иванов И.И."
) -> Optional[str]:
    """
    Генерирует PDF-отчёт со сроками
    
    Args:
        dates: Словарь с датами
        law_type: Тип закона
        nmck: НМЦК
        company_name: Название компании
        responsible_person: ФИО ответственного
    
    Returns:
        Путь к созданному PDF-файлу
    """
    
    # Шаблон HTML для сроков
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>Календарный план закупки</title>
        <style>
            body {{
                font-family: 'Times New Roman', Times, serif;
                font-size: 14px;
                margin: 40px;
                line-height: 1.6;
            }}
            h1 {{
                text-align: center;
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 30px;
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .info-block {{
                margin-bottom: 20px;
            }}
            .info-block table {{
                width: 100%;
                border-collapse: collapse;
            }}
            .info-block td {{
                padding: 8px 10px;
                border: 1px solid #000;
            }}
            .info-block td:first-child {{
                font-weight: bold;
                width: 35%;
                background-color: #f5f5f5;
            }}
            .info-block td:last-child {{
                width: 65%;
            }}
            .dates-table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }}
            .dates-table th {{
                background-color: #e8e8e8;
                border: 1px solid #000;
                padding: 10px;
                text-align: center;
                font-weight: bold;
            }}
            .dates-table td {{
                border: 1px solid #000;
                padding: 8px 10px;
                text-align: center;
            }}
            .dates-table tr:nth-child(even) {{
                background-color: #f9f9f9;
            }}
            .footer {{
                margin-top: 40px;
                text-align: right;
            }}
            .signature {{
                margin-top: 50px;
            }}
            .signature-line {{
                display: inline-block;
                width: 200px;
                border-bottom: 1px solid #000;
                margin: 0 10px;
            }}
            .note {{
                font-size: 12px;
                margin-top: 30px;
                color: #555;
                border-top: 1px solid #ddd;
                padding-top: 15px;
            }}
        </style>
    </head>
    <body>
        <h1>КАЛЕНДАРНЫЙ ПЛАН ЗАКУПКИ</h1>
        
        <div class="header">
            <p><strong>Обоснование сроков проведения закупки</strong></p>
            <p>по {law_type}</p>
        </div>
        
        <div class="info-block">
            <table>
                <tr>
                    <td>Наименование заказчика</td>
                    <td>{company_name}</td>
                </tr>
                <tr>
                    <td>Ответственное лицо</td>
                    <td>{responsible_person}</td>
                </tr>
                <tr>
                    <td>НМЦК</td>
                    <td>{nmck:,.2f} руб. ({number_to_words_rubles(nmck)})</td>
                </tr>
                <tr>
                    <td>Дата формирования</td>
                    <td>{datetime.now().strftime("%d.%m.%Y")}</td>
                </tr>
            </table>
        </div>
        
        <h2 style="text-align: center; font-size: 16px;">График проведения закупки</h2>
        
        <table class="dates-table">
            <thead>
                <tr>
                    <th>№ п/п</th>
                    <th>Этап закупки</th>
                    <th>Дата</th>
                    <th>Кол-во дней</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>1</td>
                    <td>Публикация извещения</td>
                    <td>{format_date(dates.get('publication_date'))}</td>
                    <td>—</td>
                </tr>
                <tr>
                    <td>2</td>
                    <td>Окончание подачи заявок</td>
                    <td>{format_date(dates.get('bid_end_date'))}</td>
                    <td>{dates.get('applied_bid_days', '—')}</td>
                </tr>
                <tr>
                    <td>3</td>
                    <td>Аукцион / Вскрытие конвертов</td>
                    <td>{format_date(dates.get('auction_date', dates.get('bid_end_date')))}</td>
                    <td>—</td>
                </tr>
                <tr>
                    <td>4</td>
                    <td>Рассмотрение заявок</td>
                    <td>{format_date(dates.get('review_date', dates.get('consideration_date', dates.get('bid_end_date'))))}</td>
                    <td>{dates.get('applied_review_days', '—')}</td>
                </tr>
                <tr>
                    <td>5</td>
                    <td>Протокол подведения итогов</td>
                    <td>{format_date(dates.get('protocol_date', dates.get('consideration_date', dates.get('bid_end_date'))))}</td>
                    <td>—</td>
                </tr>
                <tr>
                    <td>6</td>
                    <td>Подписание контракта</td>
                    <td>{format_date(dates.get('signing_date'))}</td>
                    <td>{dates.get('applied_signing_days', '—')}</td>
                </tr>
            </tbody>
        </table>
        
        <div class="note">
            <p><strong>Примечания:</strong></p>
            <p>• Сроки рассчитаны с учётом рабочих дней (без учёта выходных и праздничных дней).</p>
            <p>• Источник: {dates.get('law_source', law_type)}</p>
            <p>• Документ сгенерирован автоматически в боте «Смета+Срок».</p>
        </div>
        
        <div class="signature">
            <p style="text-align: center;">
                Руководитель: _________________ / {responsible_person} /
            </p>
            <p style="text-align: center; margin-top: 10px;">
                М.П.
            </p>
        </div>
    </body>
    </html>
    """
    
    try:
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            pdf_path = tmp.name
            HTML(string=html_content).write_pdf(pdf_path)
            return pdf_path
    except Exception as e:
        print(f"❌ Ошибка генерации PDF: {e}")
        return None


# ============================================================
# ГЕНЕРАЦИЯ PDF ДЛЯ НМЦК
# ============================================================

class PDFGenerator:
    """Класс для генерации PDF-документов"""
    
    def __init__(self, template_name: str = 'procurement_report.html'):
        self.template_dir = get_template_dir()
        self.env = Environment(loader=FileSystemLoader(self.template_dir))
        self.template_name = template_name
    
    def generate(self, data: Dict[str, Any]) -> bytes:
        """Генерирует PDF из данных"""
        template = self.env.get_template(self.template_name)
        html_content = template.render(**data)
        return HTML(string=html_content).write_pdf()


# Функция для обратной совместимости
def prepare_pdf_data(
    procurement: Dict,
    suppliers: List[Dict],
    timeline: List[Dict] = None,
    company_name: str = "ООО «Ваша компания»",
    responsible_person: str = "Иванов И.И.",
    positions: List[Dict] = None,
    method: str = "average"
) -> Dict:
    """Подготавливает данные для PDF"""
    return {
        "procurement": procurement,
        "suppliers": suppliers,
        "timeline": timeline or [],
        "company_name": company_name,
        "responsible_person": responsible_person,
        "positions": positions or [],
        "method": method,
        "total_nmck_word": number_to_words_rubles(procurement.get('nmck', 0))
    }