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
    """
    Преобразует число в пропись (рубли) с копейками
    
    Args:
        n: Сумма в рублях
    
    Returns:
        Строка с суммой прописью
    """
    # Простая версия для демонстрации
    rubles = int(n)
    kopecks = int(round((n - rubles) * 100))
    
    # Словари для склонения
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
        
        # Миллионы
        if num >= 1000000:
            millions = num // 1000000
            num %= 1000000
            if millions == 1:
                result.append('один миллион')
            elif 2 <= millions <= 4:
                result.append(f'{num_to_words(millions)} миллиона')
            else:
                result.append(f'{num_to_words(millions)} миллионов')
        
        # Тысячи
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
        
        # Сотни
        if num >= 100:
            hundreds_part = num // 100
            num %= 100
            result.append(hundreds[hundreds_part])
        
        # Десятки и единицы
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
    
    # Формируем результат
    rubles_words = num_to_words(rubles) if rubles > 0 else 'ноль'
    
    # Склонение "рубль"
    if rubles % 10 == 1 and rubles % 100 != 11:
        ruble_word = 'рубль'
    elif 2 <= rubles % 10 <= 4 and (rubles % 100 < 10 or rubles % 100 >= 20):
        ruble_word = 'рубля'
    else:
        ruble_word = 'рублей'
    
    # Копейки
    kopecks_word = f"{kopecks:02d} коп."
    
    return f"{rubles_words} {ruble_word} {kopecks_word}"


def get_template_dir() -> str:
    """Возвращает путь к папке с шаблонами"""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')


# ============================================================
# ПОДГОТОВКА ДАННЫХ ДЛЯ PDF
# ============================================================

def prepare_pdf_data(
    procurement: Dict[str, Any],
    suppliers: List[Dict[str, Any]],
    timeline: List[Dict[str, Any]] = None,
    company_name: str = "ООО «Ваша компания»",
    responsible_person: str = "Иванов И.И.",
    positions: List[Dict] = None,
    method: str = "average"
) -> Dict[str, Any]:
    """
    Подготавливает данные для генерации PDF
    
    Args:
        procurement: Данные закупки
        suppliers: Список поставщиков с ценами
        timeline: Временная шкала (для сроков)
        company_name: Название компании
        responsible_person: ФИО ответственного
        positions: Список позиций с детальными данными (для НМЦК)
        method: 'average' или 'minimum'
    
    Returns:
        Словарь с подготовленными данными для шаблона
    """
    if positions is None:
        # Если позиции не переданы, формируем из suppliers
        positions = []
        for i, sup in enumerate(suppliers[:3], 1):
            price = sup.get('price', 0)
            positions.append({
                "name": sup.get('note', f'Товар/услуга {i}'),
                "okpd": "",
                "quantity": 1,
                "unit": "шт.",
                "prices": [price, 0, 0],
                "avg_price": price,
                "variation": 0,
                "total_price": price
            })
    
    # Рассчитываем среднюю цену и вариацию для каждой позиции
    formatted_positions = []
    for pos in positions:
        prices = pos.get('prices', [0, 0, 0])
        # Дополняем до 3 цен
        while len(prices) < 3:
            prices.append(0)
        prices = prices[:3]
        
        avg_price = sum(prices) / 3 if prices else 0
        variation = 0
        if avg_price > 0 and len(prices) >= 3:
            variance = sum((p - avg_price) ** 2 for p in prices) / 3
            std_dev = variance ** 0.5
            variation = (std_dev / avg_price) * 100 if avg_price > 0 else 0
        
        total_price = avg_price * pos.get('quantity', 1)
        
        formatted_positions.append({
            "name": pos.get('name', ''),
            "okpd": pos.get('okpd', ''),
            "quantity": pos.get('quantity', 1),
            "unit": pos.get('unit', 'шт.'),
            "prices": prices,
            "avg_price": avg_price,
            "variation": variation,
            "total_price": total_price
        })
    
    total_nmck = sum(p['total_price'] for p in formatted_positions)
    
    return {
        "procurement": {
            "title": procurement.get('title', 'Закупка'),
            "law_type": procurement.get('law_type', '44-ФЗ'),
            "nmck": procurement.get('nmck', total_nmck),
            "nmck_method": "Средняя арифметическая" if method == "average" else "Минимальная цена (письмо Минфина)",
            "nmck_source": procurement.get('nmck_source', 'ч. 6 ст. 22 44-ФЗ'),
            "company_name": company_name,
            "responsible_person": responsible_person,
            "created_date": datetime.now().strftime("%d.%m.%Y")
        },
        "suppliers": suppliers,
        "positions": formatted_positions,
        "total_nmck": total_nmck,
        "total_nmck_word": number_to_words_rubles(total_nmck),
        "method": method,
        "timeline": timeline or []
    }


# ============================================================
# ГЕНЕРАЦИЯ PDF
# ============================================================

class PDFGenerator:
    """Класс для генерации PDF-документов"""
    
    def __init__(self, template_name: str = 'procurement_report.html'):
        self.template_dir = get_template_dir()
        self.env = Environment(loader=FileSystemLoader(self.template_dir))
        self.template_name = template_name
    
    def generate(self, data: Dict[str, Any]) -> bytes:
        """
        Генерирует PDF из данных
        
        Args:
            data: Словарь с данными для шаблона
        
        Returns:
            Байты PDF-файла
        """
        template = self.env.get_template(self.template_name)
        html_content = template.render(**data)
        
        # Создаём PDF в памяти
        pdf_bytes = HTML(string=html_content).write_pdf()
        return pdf_bytes
    
    def generate_to_file(self, data: Dict[str, Any], filename: str = None) -> str:
        """
        Генерирует PDF и сохраняет в файл
        
        Args:
            data: Словарь с данными для шаблона
            filename: Имя файла (если None - создаётся временный)
        
        Returns:
            Путь к созданному PDF-файлу
        """
        if filename is None:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                filename = tmp.name
        
        template = self.env.get_template(self.template_name)
        html_content = template.render(**data)
        
        HTML(string=html_content).write_pdf(filename)
        return filename


# ============================================================
# УПРОЩЁННЫЕ ФУНКЦИИ ДЛЯ БЫСТРОГО ВЫЗОВА
# ============================================================

def generate_nmck_pdf(
    positions: List[Dict],
    total_nmck: float,
    method: str = 'average',
    variation_warning: bool = False,
    law_type: str = "44-ФЗ",
    company_name: str = "ООО «Ваша компания»",
    responsible_person: str = "Иванов И.И."
) -> str:
    """
    Генерирует PDF-отчёт обоснования НМЦК
    
    Args:
        positions: список позиций с полями:
            - name: название
            - okpd: ОКПД2/КТРУ
            - quantity: количество
            - unit: единица измерения
            - prices: список из 3 цен
            - avg_price: средняя цена
            - variation: коэффициент вариации
            - total_price: итоговая цена позиции
        total_nmck: общая НМЦК
        method: 'average' или 'minimum'
        variation_warning: превышен ли коэффициент вариации
        law_type: тип закона
        company_name: название компании
        responsible_person: ФИО ответственного
    
    Returns:
        Путь к созданному PDF-файлу
    """
    # Подготавливаем данные
    data = {
        "positions": positions,
        "total_nmck": total_nmck,
        "total_nmck_word": number_to_words_rubles(total_nmck),
        "method": method,
        "variation_warning": variation_warning,
        "procurement": {
            "law_type": law_type,
            "company_name": company_name,
            "responsible_person": responsible_person,
            "created_date": datetime.now().strftime("%d.%m.%Y")
        }
    }
    
    # Генерируем PDF
    generator = PDFGenerator('procurement_report.html')
    return generator.generate_to_file(data)


def generate_terms_pdf(
    dates: Dict[str, Any],
    law_type: str = "44-ФЗ",
    nmck: float = None,
    company_name: str = "ООО «Ваша компания»",
    responsible_person: str = "Иванов И.И."
) -> Optional[str]:
    """
    Генерирует PDF-отчёт со сроками (планируется)
    
    Args:
        dates: Словарь с датами
        law_type: Тип закона
        nmck: НМЦК
        company_name: Название компании
        responsible_person: ФИО ответственного
    
    Returns:
        Путь к созданному PDF-файлу или None (если не реализовано)
    """
    # TODO: Реализовать полноценную генерацию PDF для сроков
    # Создаём временный файл-заглушку
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        # Простая заглушка
        from weasyprint import HTML
        html = f"""
        <html>
        <head><meta charset="UTF-8"></head>
        <body style="font-family: Times New Roman; padding: 40px;">
            <h1 style="text-align: center;">КАЛЕНДАРНЫЙ ПЛАН ЗАКУПКИ</h1>
            <p><strong>Закон:</strong> {law_type}</p>
            <p><strong>НМЦК:</strong> {nmck:,.2f} руб.</p>
            <p><strong>Дата публикации:</strong> {format_date(dates.get('publication_date'))}</p>
            <p><strong>Окончание подачи заявок:</strong> {format_date(dates.get('bid_end_date'))}</p>
            <p><strong>Рассмотрение:</strong> {format_date(dates.get('review_date', dates.get('consideration_date')))}</p>
            <p><strong>Подписание контракта:</strong> {format_date(dates.get('signing_date'))}</p>
            <hr>
            <p style="text-align: center;">Документ сгенерирован автоматически</p>
            <p style="text-align: center;">{company_name}</p>
        </body>
        </html>
        """
        HTML(string=html).write_pdf(tmp.name)
        return tmp.name


# Для обратной совместимости с старым кодом
def prepare_nmck_pdf_data(
    procurement: Dict,
    suppliers: List[Dict],
    positions: List[Dict] = None,
    method: str = "average"
) -> Dict:
    """Устаревшая функция, используйте prepare_pdf_data"""
    return prepare_pdf_data(
        procurement=procurement,
        suppliers=suppliers,
        positions=positions,
        method=method
    )