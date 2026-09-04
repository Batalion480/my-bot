# ============================================================
# utils/pdf_generator.py
# ============================================================

import os
import tempfile
from datetime import datetime
from typing import List, Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS
from weasyprint.fonts import FontConfiguration
import locale

try:
    locale.setlocale(locale.LC_ALL, 'ru_RU.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'Russian_Russia.1251')
    except:
        pass


def number_to_words_rubles(n: float) -> str:
    if n is None:
        return "ноль рублей 00 коп."
    rubles = int(n)
    kopecks = int(round((n - rubles) * 100))
    return f"{rubles} руб. {kopecks:02d} коп."


def get_template_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')


def format_date(d) -> str:
    if d is None:
        return "—"
    if isinstance(d, str):
        return d
    return d.strftime("%d.%m.%Y")


class PDFGenerator:
    def __init__(self, template_name: str = 'procurement_report.html'):
        self.template_dir = get_template_dir()
        self.env = Environment(loader=FileSystemLoader(self.template_dir))
        self.template_name = template_name
    
    def generate(self, data: Dict[str, Any]) -> bytes:
        template = self.env.get_template(self.template_name)
        html_content = template.render(**data)
        
        font_config = FontConfiguration()
        pdf_bytes = HTML(string=html_content).write_pdf(font_config=font_config)
        return pdf_bytes


def prepare_pdf_data(
    procurement: Dict[str, Any],
    suppliers: List[Dict[str, Any]],
    timeline: List[Dict[str, Any]] = None,
    company_name: str = "ООО «Ваша компания»",
    responsible_person: str = "Иванов И.И.",
    positions: List[Dict] = None,
    method: str = "average"
) -> Dict[str, Any]:
    if positions is None:
        positions = []
    formatted_positions = []
    for pos in positions:
        prices = pos.get('prices', [0, 0, 0])
        while len(prices) < 3:
            prices.append(0)
        prices = prices[:3]
        avg_price = sum(prices) / 3 if prices else 0
        total_price = avg_price * pos.get('quantity', 1)
        formatted_positions.append({
            "name": pos.get('name', ''),
            "okpd": pos.get('okpd', ''),
            "quantity": pos.get('quantity', 1),
            "unit": pos.get('unit', 'шт.'),
            "prices": prices,
            "avg_price": avg_price,
            "variation": 0,
            "total_price": total_price
        })
    total_nmck = sum(p['total_price'] for p in formatted_positions)
    return {
        "procurement": {
            "title": procurement.get('title', 'Закупка'),
            "law_type": procurement.get('law_type', '44-ФЗ'),
            "nmck": procurement.get('nmck', total_nmck),
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


def generate_terms_pdf(dates, law_type="44-ФЗ", nmck=0, company_name="", responsible_person=""):
    try:
        html = f"""
        <html><head><meta charset="UTF-8"></head>
        <body style="font-family: Arial; padding:20px;">
            <h1>Календарный план закупки</h1>
            <p><strong>Закон:</strong> {law_type}</p>
            <p><strong>НМЦК:</strong> {nmck:,.2f} руб.</p>
            <p><strong>Публикация:</strong> {format_date(dates.get('publication_date'))}</p>
            <p><strong>Подписание:</strong> {format_date(dates.get('signing_date'))}</p>
            <hr>
            <p>Документ сгенерирован автоматически</p>
        </body></html>
        """
        font_config = FontConfiguration()
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            pdf_path = tmp.name
            HTML(string=html).write_pdf(pdf_path, font_config=font_config)
            return pdf_path
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None