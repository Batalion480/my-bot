import os
import tempfile
from datetime import datetime
from typing import List, Dict, Any, Optional
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
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


def format_date(d) -> str:
    if d is None:
        return "—"
    if isinstance(d, str):
        return d
    return d.strftime("%d.%m.%Y")


class PDFGenerator:
    def __init__(self):
        pass

    def generate(self, data: Dict[str, Any]) -> bytes:
        import io
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
        styles = getSampleStyleSheet()
        story = []

        # Заголовок
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=1,
            spaceAfter=20
        )
        story.append(Paragraph("Обоснование начальной (максимальной) цены контракта", title_style))
        story.append(Spacer(1, 12))

        # Информация о закупке
        procurement = data.get('procurement', {})
        info = [
            f"Наименование заказчика: {procurement.get('company_name', 'ООО «Ваша компания»')}",
            f"Ответственное лицо: {procurement.get('responsible_person', 'Иванов И.И.')}",
            f"Закон: {procurement.get('law_type', '44-ФЗ')}",
            f"Дата формирования: {procurement.get('created_date', datetime.now().strftime('%d.%m.%Y'))}"
        ]
        for line in info:
            story.append(Paragraph(line, styles['Normal']))
        story.append(Spacer(1, 12))

        # Таблица позиций
        positions = data.get('positions', [])
        if positions:
            table_data = [["№", "Наименование", "Кол-во", "Ед.", "Цена1", "Цена2", "Цена3", "Средняя", "Итого"]]
            for i, pos in enumerate(positions, 1):
                row = [
                    str(i),
                    pos.get('name', ''),
                    str(pos.get('quantity', 1)),
                    pos.get('unit', 'шт.'),
                    f"{pos.get('prices', [0,0,0])[0]:.2f}",
                    f"{pos.get('prices', [0,0,0])[1]:.2f}",
                    f"{pos.get('prices', [0,0,0])[2]:.2f}",
                    f"{pos.get('avg_price', 0):.2f}",
                    f"{pos.get('total_price', 0):.2f}"
                ]
                table_data.append(row)
            
            total_nmck = data.get('total_nmck', 0)
            table_data.append(["", "", "", "", "", "", "", "ИТОГО:", f"{total_nmck:.2f}"])

            table = Table(table_data, colWidths=[0.5*inch, 2*inch, 0.7*inch, 0.5*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.8*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(table)
        else:
            story.append(Paragraph("Нет данных для отображения", styles['Normal']))

        # Подпись
        story.append(Spacer(1, 30))
        story.append(Paragraph(f"НМЦК: {data.get('total_nmck_word', '')}", styles['Normal']))
        story.append(Spacer(1, 20))
        story.append(Paragraph("_________________ / _________________ /", styles['Normal']))
        story.append(Paragraph("«___» ___________ 2026 г.", styles['Normal']))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
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
        import io
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, alignment=1, spaceAfter=20)
        story.append(Paragraph("Календарный план закупки", title_style))
        story.append(Spacer(1, 12))

        story.append(Paragraph(f"<b>Закон:</b> {law_type}", styles['Normal']))
        story.append(Paragraph(f"<b>НМЦК:</b> {nmck:,.2f} руб.", styles['Normal']))
        story.append(Paragraph(f"<b>Публикация:</b> {format_date(dates.get('publication_date'))}", styles['Normal']))
        story.append(Paragraph(f"<b>Подписание:</b> {format_date(dates.get('signing_date'))}", styles['Normal']))
        story.append(Spacer(1, 20))
        story.append(Paragraph("Документ сгенерирован автоматически", styles['Normal']))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(pdf_bytes)
            return tmp.name
    except Exception as e:
        print(f"❌ Ошибка генерации PDF: {e}")
        return None