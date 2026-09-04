import os
import tempfile
from datetime import datetime
from typing import List, Dict, Any, Optional
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import locale

try:
    locale.setlocale(locale.LC_ALL, 'ru_RU.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'Russian_Russia.1251')
    except:
        pass

# Регистрируем шрифт для кириллицы
FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'fonts')
FONT_FILE = os.path.join(FONT_DIR, 'DejaVuSans.ttf')
if os.path.exists(FONT_FILE):
    pdfmetrics.registerFont(TTFont('DejaVuSans', FONT_FILE))
    FONT_NAME = 'DejaVuSans'
else:
    # Если шрифта нет, используем Helvetica (кириллица не будет отображаться)
    FONT_NAME = 'Helvetica'


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
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        styles = getSampleStyleSheet()
        story = []

        # Стили
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=1,  # center
            spaceAfter=20,
            fontName=FONT_NAME
        )
        normal_style = ParagraphStyle(
            'NormalStyle',
            parent=styles['Normal'],
            fontName=FONT_NAME,
            fontSize=11
        )
        bold_style = ParagraphStyle(
            'BoldStyle',
            parent=normal_style,
            fontName=FONT_NAME,
            fontSize=11,
            alignment=1
        )
        table_header_style = ParagraphStyle(
            'TableHeaderStyle',
            parent=styles['Normal'],
            fontName=FONT_NAME,
            fontSize=9,
            alignment=1,
            textColor=colors.whitesmoke,
            leading=12
        )
        table_cell_style = ParagraphStyle(
            'TableCellStyle',
            parent=styles['Normal'],
            fontName=FONT_NAME,
            fontSize=8,
            alignment=1,
            leading=10
        )
        table_cell_left_style = ParagraphStyle(
            'TableCellLeftStyle',
            parent=table_cell_style,
            alignment=0  # left
        )

        # Заголовок
        story.append(Paragraph("ОБОСНОВАНИЕ НАЧАЛЬНОЙ (МАКСИМАЛЬНОЙ) ЦЕНЫ КОНТРАКТА", title_style))
        story.append(Spacer(1, 12))

        # Информация о закупке
        procurement = data.get('procurement', {})
        info_data = [
            ("Наименование заказчика:", procurement.get('company_name', 'ООО «Ваша компания»')),
            ("Ответственное лицо:", procurement.get('responsible_person', 'Иванов И.И.')),
            ("Закон:", procurement.get('law_type', '44-ФЗ')),
            ("Дата формирования:", procurement.get('created_date', datetime.now().strftime('%d.%m.%Y')))
        ]
        for label, value in info_data:
            story.append(Paragraph(f"<b>{label}</b> {value}", normal_style))
        story.append(Spacer(1, 12))

        # Таблица позиций
        positions = data.get('positions', [])
        if not positions:
            story.append(Paragraph("Нет данных для отображения", normal_style))
        else:
            # Заголовки таблицы
            table_data = [
                [
                    "№ п/п",
                    "Наименование позиции",
                    "ОКПД2/КТРУ",
                    "Кол-во",
                    "Ед. изм.",
                    "Коммерческое предложение 1",
                    "Коммерческое предложение 2",
                    "Коммерческое предложение 3",
                    "Средняя цена за ед. (руб.)",
                    "Коэф. вариации (%)",
                    "Итого (руб.)"
                ]
            ]
            # Добавляем подзаголовки для КП (цена за ед. и итоговая цена – мы показываем только цену за единицу)
            # Для соответствия образцу можно добавить две строки, но упростим, показывая только цену за ед.

            for i, pos in enumerate(positions, 1):
                row = [
                    str(i),
                    pos.get('name', ''),
                    pos.get('okpd', ''),
                    str(pos.get('quantity', 1)),
                    pos.get('unit', 'шт.'),
                    f"{pos.get('prices', [0,0,0])[0]:.2f}",
                    f"{pos.get('prices', [0,0,0])[1]:.2f}",
                    f"{pos.get('prices', [0,0,0])[2]:.2f}",
                    f"{pos.get('avg_price', 0):.2f}",
                    f"{pos.get('variation', 0):.2f}",
                    f"{pos.get('total_price', 0):.2f}"
                ]
                table_data.append(row)

            # Итоговая строка
            total_nmck = data.get('total_nmck', 0)
            table_data.append(["", "", "", "", "", "", "", "", "", "ИТОГО:", f"{total_nmck:.2f}"])

            # Ширина колонок
            col_widths = [
                0.6*cm,   # №
                4.0*cm,   # Наименование
                2.5*cm,   # ОКПД2
                1.2*cm,   # Кол-во
                1.2*cm,   # Ед.изм.
                1.8*cm,   # КП1
                1.8*cm,   # КП2
                1.8*cm,   # КП3
                1.8*cm,   # Средняя
                1.8*cm,   # Вариация
                1.8*cm    # Итого
            ]

            table = Table(table_data, colWidths=col_widths, repeatRows=1)
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
                ('ALIGN', (1, 1), (1, -2), 'LEFT'),  # Наименование выравниваем влево
            ]))
            story.append(table)

        # Примечание в зависимости от метода
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
                "Цед.ср. = (∑ni=1 Цi.)/n в соответствии с Приказом МЭР РФ от 02.10.2013 № 567, где:\n"
                "Цед.ср. – средняя цена за единицу товара;\n"
                "n – количество значений, используемых в расчете;\n"
                "i – номер источника ценовой информации;\n"
                "Цi – цена единицы товара."
            )
        # Заменяем переносы строк на <br/> для Paragraph
        note_text = note_text.replace('\n', '<br/>')
        story.append(Paragraph(note_text, normal_style))

        # Решение
        story.append(Spacer(1, 30))
        total_word = data.get('total_nmck_word', '')
        total_num = data.get('total_nmck', 0)
        story.append(Paragraph(
            f"<b>Решение:</b> Признать начальной (максимальной) ценой контракта <b>{total_word}</b> "
            f"({total_num:,.2f}) рублей 00 копеек",
            normal_style
        ))

        # Подпись
        story.append(Spacer(1, 40))
        story.append(Paragraph("_________________ / _________________ /", normal_style))
        story.append(Paragraph("«___» ___________ 2026 г.", normal_style))

        # Сборка PDF
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
        variation = pos.get('variation', 0)
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
    """Генерация PDF для календарного плана (упрощённая версия)"""
    try:
        import io
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, alignment=1, spaceAfter=20, fontName=FONT_NAME)
        normal_style = ParagraphStyle('NormalStyle', parent=styles['Normal'], fontName=FONT_NAME, fontSize=12)

        story.append(Paragraph("Календарный план закупки", title_style))
        story.append(Spacer(1, 12))

        story.append(Paragraph(f"<b>Закон:</b> {law_type}", normal_style))
        story.append(Paragraph(f"<b>НМЦК:</b> {nmck:,.2f} руб.", normal_style))
        story.append(Paragraph(f"<b>Публикация:</b> {format_date(dates.get('publication_date'))}", normal_style))
        story.append(Paragraph(f"<b>Подписание:</b> {format_date(dates.get('signing_date'))}", normal_style))
        story.append(Spacer(1, 20))
        story.append(Paragraph("Документ сгенерирован автоматически", normal_style))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(pdf_bytes)
            return tmp.name
    except Exception as e:
        print(f"❌ Ошибка генерации PDF: {e}")
        return None