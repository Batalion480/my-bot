import os
import tempfile
from datetime import datetime
from typing import List, Dict, Any, Optional
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import locale
import re

try:
    locale.setlocale(locale.LC_ALL, 'ru_RU.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'Russian_Russia.1251')
    except:
        pass

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'fonts')
FONT_FILE = os.path.join(FONT_DIR, 'DejaVuSans.ttf')
if os.path.exists(FONT_FILE):
    pdfmetrics.registerFont(TTFont('DejaVuSans', FONT_FILE))
    FONT_NAME = 'DejaVuSans'
else:
    FONT_NAME = 'Helvetica'


def rubles_to_words(n: int) -> str:
    if n == 0:
        return "ноль"

    units = ["", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
    units_feminine = ["", "одна", "две", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
    teens = ["десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
             "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"]
    tens = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят",
            "шестьдесят", "семьдесят", "восемьдесят", "девяносто"]
    hundreds = ["", "сто", "двести", "триста", "четыреста", "пятьсот",
                "шестьсот", "семьсот", "восемьсот", "девятьсот"]

    def num_to_words(num, feminine=False):
        if num == 0:
            return ""
        parts = []
        if num >= 100:
            parts.append(hundreds[num // 100])
            num %= 100
        if num >= 20:
            parts.append(tens[num // 10])
            num %= 10
        if 10 <= num < 20:
            parts.append(teens[num - 10])
            num = 0
        if num > 0:
            if feminine:
                parts.append(units_feminine[num])
            else:
                parts.append(units[num])
        return " ".join(parts).strip()

    def get_thousands(num):
        if num == 0:
            return ""
        if num == 1:
            return f"{num_to_words(num, feminine=True)} тысяча"
        elif 2 <= num <= 4:
            return f"{num_to_words(num, feminine=True)} тысячи"
        else:
            return f"{num_to_words(num, feminine=True)} тысяч"

    def get_millions(num):
        if num == 0:
            return ""
        if num == 1:
            return f"{num_to_words(num)} миллион"
        elif 2 <= num <= 4:
            return f"{num_to_words(num)} миллиона"
        else:
            return f"{num_to_words(num)} миллионов"

    result = []
    if n >= 1000000:
        millions = n // 1000000
        n %= 1000000
        result.append(get_millions(millions))
    if n >= 1000:
        thousands = n // 1000
        n %= 1000
        result.append(get_thousands(thousands))
    if n > 0:
        result.append(num_to_words(n))
    return " ".join(result).strip()


def format_date(d) -> str:
    if d is None:
        return "—"
    if isinstance(d, str):
        return d
    return d.strftime("%d.%m.%Y")


def format_number_with_spaces(x: float) -> str:
    """Форматирует число с пробелами как разделителями тысяч."""
    s = f"{x:,.2f}"
    parts = s.split('.')
    integer_part = parts[0].replace(',', ' ')
    if len(parts) == 2:
        return f"{integer_part}.{parts[1]}"
    return integer_part


class PDFGenerator:
    def __init__(self):
        pass

    def generate(self, data: Dict[str, Any]) -> bytes:
        import io
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=1,
            spaceAfter=20,
            fontName=FONT_NAME
        )
        normal_style = ParagraphStyle(
            'NormalStyle',
            parent=styles['Normal'],
            fontName=FONT_NAME,
            fontSize=11
        )
        cell_style = ParagraphStyle(
            'CellStyle',
            parent=styles['Normal'],
            fontName=FONT_NAME,
            fontSize=8,
            alignment=1,
            leading=10
        )
        cell_left_style = ParagraphStyle(
            'CellLeftStyle',
            parent=cell_style,
            alignment=0
        )

        story.append(Paragraph("ОБОСНОВАНИЕ НАЧАЛЬНОЙ (МАКСИМАЛЬНОЙ) ЦЕНЫ КОНТРАКТА", title_style))
        story.append(Spacer(1, 12))

        positions = data.get('positions', [])
        if not positions:
            story.append(Paragraph("Нет данных для отображения", normal_style))
        else:
            kp_numbers = positions[0].get('kp_numbers', ['', '', ''])
            kp_dates = positions[0].get('kp_dates', ['', '', ''])

            kp_headers = []
            for i in range(3):
                label = "Коммерческое предложение"
                if kp_dates[i] and kp_numbers[i]:
                    label += f"<br/>от {kp_dates[i]} Вх. № {kp_numbers[i]}"
                elif kp_dates[i]:
                    label += f"<br/>от {kp_dates[i]}"
                elif kp_numbers[i]:
                    label += f"<br/>Вх. № {kp_numbers[i]}"
                kp_headers.append(label)

            first_row = [
                "№ п/п",
                "Наименование позиции",
                "ОКПД2/КТРУ",
                "Кол-во",
                "Ед. изм.",
                Paragraph(kp_headers[0], cell_style), "",
                Paragraph(kp_headers[1], cell_style), "",
                Paragraph(kp_headers[2], cell_style), "",
                "Средняя цена<br/>за ед. (руб.)",
                "Коэф.<br/>вариации (%)",
                "Итого (руб.)"
            ]
            second_row = [
                "", "", "", "", "",
                "Цена за ед.<br/>изм.",
                "Цена",
                "Цена за ед.<br/>изм.",
                "Цена",
                "Цена за ед.<br/>изм.",
                "Цена",
                "", "", ""
            ]

            table_data = [first_row, second_row]
            total_nmck = 0

            for idx, pos in enumerate(positions, 1):
                prices = pos.get('prices', [0, 0, 0])
                qty = pos.get('quantity', 1)
                avg_price = pos.get('avg_price', sum(prices) / len(prices) if prices else 0)
                variation = pos.get('variation', 0)
                total_price = pos.get('total_price', avg_price * qty)
                total_nmck += total_price

                row = [
                    str(idx),
                    pos.get('name', ''),
                    pos.get('okpd', ''),
                    str(qty),
                    pos.get('unit', 'шт.'),
                ]
                for price in prices:
                    total = price * qty
                    row.append(f"{price:.2f}")
                    row.append(f"{total:.2f}")
                row.append(f"{avg_price:.2f}")
                row.append(f"{variation:.2f}")
                row.append(f"{total_price:.2f}")
                table_data.append(row)

            total_row = ["", "", "", "", "", "", "", "", "", "", "", "", "ИТОГО:", f"{total_nmck:.2f}"]
            table_data.append(total_row)

            col_widths = [
                0.8*cm, 4.5*cm, 2.8*cm, 1.2*cm, 1.2*cm,
                1.8*cm, 1.8*cm, 1.8*cm, 1.8*cm, 1.8*cm, 1.8*cm,
                1.8*cm, 1.8*cm, 1.8*cm
            ]

            table = Table(table_data, colWidths=col_widths, repeatRows=2)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), FONT_NAME),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                ('FONTNAME', (0, -1), (-1, -1), FONT_NAME),
                ('FONTSIZE', (0, -1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('ALIGN', (1, 2), (1, -2), 'LEFT'),
                ('SPAN', (5, 0), (6, 0)),
                ('SPAN', (7, 0), (8, 0)),
                ('SPAN', (9, 0), (10, 0)),
                ('BACKGROUND', (0, 1), (-1, 1), colors.lightgrey),
                ('FONTSIZE', (0, 1), (-1, 1), 7),
                ('BOTTOMPADDING', (0, 1), (-1, 1), 4),
            ]))
            story.append(table)
            story.append(Spacer(1, 12))

        method = data.get('method', 'average')
        story.append(Spacer(1, 20))
        if method == 'minimum':
            note_text = (
                "Расчет начальной (максимальной) цены контракта производится по минимальному ценовому предложению "
                "в соответствии с письмом Минфина России от 08.09.2017 № 24-01-09/58179 «Об определении и обосновании НМЦК "
                "методом сопоставимых рыночных цен» и частью 2 статьи 72 Бюджетного кодекса Российской Федерации."
            )
        else:
            note_text = (
                "Для определения однородности совокупности значений средняя цена за единицу товара рассчитана по формуле "
                "Цед.ср. = (∑ni=1 Цi.)/n в соответствии с Приказом МЭР РФ от 02.10.2013 № 567, где:<br/>"
                "Цед.ср. – средняя цена за единицу товара;<br/>"
                "n – количество значений, используемых в расчете;<br/>"
                "i – номер источника ценовой информации;<br/>"
                "Цi – цена единицы товара."
            )
        story.append(Paragraph(note_text, normal_style))

        # Решение
        story.append(Spacer(1, 30))
        total_num = data.get('total_nmck', 0)
        rubles = int(total_num)
        kopecks = int(round((total_num - rubles) * 100))
        rubles_word = rubles_to_words(rubles)
        # Склонение копеек
        if kopecks % 10 == 1 and kopecks % 100 != 11:
            kopecks_word = "копейка"
        elif 2 <= kopecks % 10 <= 4 and (kopecks % 100 < 10 or kopecks % 100 >= 20):
            kopecks_word = "копейки"
        else:
            kopecks_word = "копеек"
        formatted_total = format_number_with_spaces(total_num)
        solution_text = (
            f"<b>Решение:</b> Признать начальной (максимальной) ценой контракта "
            f"{formatted_total} ({rubles_word}) рублей {kopecks:02d} {kopecks_word}"
        )
        story.append(Paragraph(solution_text, normal_style))

        story.append(Spacer(1, 40))
        story.append(Paragraph("_________________ / _________________ /", normal_style))
        story.append(Paragraph("«___» ___________ 2026 г.", normal_style))

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
        avg_price = pos.get('avg_price', sum(prices) / len(prices) if prices else 0)
        variation = pos.get('variation', 0)
        total_price = pos.get('total_price', avg_price * pos.get('quantity', 1))
        formatted_positions.append({
            "name": pos.get('name', ''),
            "okpd": pos.get('okpd', ''),
            "quantity": pos.get('quantity', 1),
            "unit": pos.get('unit', 'шт.'),
            "prices": prices,
            "kp_numbers": pos.get('kp_numbers', ['', '', '']),
            "kp_dates": pos.get('kp_dates', ['', '', '']),
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
            "company_name": company_name,
            "responsible_person": responsible_person,
            "created_date": datetime.now().strftime("%d.%m.%Y")
        },
        "suppliers": suppliers,
        "positions": formatted_positions,
        "total_nmck": total_nmck,
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
        from reportlab.lib.units import inch

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, alignment=1, spaceAfter=20, fontName=FONT_NAME)
        heading_style = ParagraphStyle('HeadingStyle', parent=styles['Heading2'], fontSize=13, spaceAfter=8, spaceBefore=12, fontName=FONT_NAME)
        normal_style = ParagraphStyle('NormalStyle', parent=styles['Normal'], fontName=FONT_NAME, fontSize=11)
        rule_style = ParagraphStyle('RuleStyle', parent=styles['Normal'], fontName=FONT_NAME, fontSize=10, leftIndent=20, spaceAfter=4)
        article_style = ParagraphStyle('ArticleStyle', parent=styles['Normal'], fontName=FONT_NAME, fontSize=10, leftIndent=40, textColor=colors.grey, spaceAfter=8)

        story.append(Paragraph("КАЛЕНДАРНЫЙ ПЛАН ЗАКУПКИ", title_style))
        story.append(Spacer(1, 12))

        story.append(Paragraph(f"<b>Закон:</b> {law_type}", normal_style))
        story.append(Paragraph(f"<b>НМЦК:</b> {nmck:,.2f} руб. ({rubles_to_words(int(nmck))} рублей {int(round((nmck-int(nmck))*100)):02d} копеек)", normal_style))
        story.append(Paragraph(f"<b>Дата публикации:</b> {format_date(dates.get('publication_date'))}", normal_style))
        story.append(Paragraph(f"<b>Дата подписания:</b> {format_date(dates.get('signing_date'))}", normal_style))
        story.append(Spacer(1, 16))

        story.append(Paragraph("<b>Применены правила:</b>", heading_style))
        story.append(Spacer(1, 6))

        rules = dates.get('rules', [])
        if rules:
            stage_names = {
                "bid_submission": "📩 Подача заявок",
                "auction": "⚡ Аукцион",
                "review": "🔍 Рассмотрение заявок",
                "protocol": "📋 Протокол",
                "signing": "✍️ Подписание контракта"
            }
            for rule in rules:
                stage_name = stage_names.get(rule.get('stage'), rule.get('stage'))
                story.append(Paragraph(f"<b>{stage_name}</b>", heading_style))
                story.append(Paragraph(f"📌 {rule.get('rule_text', '')}", rule_style))
                story.append(Paragraph(f"📎 {rule.get('article', '')}", article_style))
                story.append(Spacer(1, 4))
        else:
            story.append(Paragraph("Правила не найдены", normal_style))

        story.append(Spacer(1, 16))

        story.append(Paragraph("<b>Рассчитанные даты:</b>", heading_style))
        story.append(Spacer(1, 6))

        table_data = [["Этап", "Дата", "Кол-во дней"]]
        stages = [
            ("Публикация", dates.get('publication_date'), "—"),
            ("Окончание подачи", dates.get('bid_end_date'), dates.get('applied_bid_days', '—')),
            ("Аукцион", dates.get('auction_date', dates.get('bid_end_date')), "—"),
            ("Рассмотрение", dates.get('review_date', dates.get('consideration_date')), dates.get('applied_review_days', '—')),
            ("Протокол", dates.get('protocol_date', dates.get('consideration_date')), "—"),
            ("Подписание", dates.get('signing_date'), dates.get('applied_signing_days', '—'))
        ]
        for stage_name, stage_date, days in stages:
            table_data.append([stage_name, format_date(stage_date), str(days)])

        table = Table(table_data, colWidths=[3*inch, 2*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), FONT_NAME),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('FONTNAME', (0, 1), (-1, -1), FONT_NAME),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        story.append(table)

        story.append(Spacer(1, 40))
        story.append(Paragraph("_________________ / _________________ /", normal_style))
        story.append(Paragraph("«___» ___________ 2026 г.", normal_style))
        story.append(Spacer(1, 20))
        story.append(Paragraph("Документ сгенерирован автоматически в боте «Смета+Срок»", normal_style))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(pdf_bytes)
            return tmp.name
    except Exception as e:
        print(f"❌ Ошибка генерации PDF: {e}")
        import traceback
        traceback.print_exc()
        return None