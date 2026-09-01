"""
Модуль генерации PDF-документов для Telegram-бота «Смета+Срок»
Использует Jinja2 для рендеринга HTML и WeasyPrint для конвертации в PDF
"""

import os
import base64
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

from config import TEMPLATE_DIR, STATIC_DIR


class PDFGenerator:
    """
    Класс для генерации PDF-отчетов на основе HTML-шаблонов.
    """

    def __init__(self, template_dir: str = TEMPLATE_DIR, static_dir: str = STATIC_DIR):
        """
        Инициализация генератора PDF.

        Args:
            template_dir: Путь к папке с HTML-шаблонами
            static_dir: Путь к папке со статическими файлами (логотип, CSS)
        """
        self.template_dir = Path(template_dir)
        self.static_dir = Path(static_dir)

        # Настройка Jinja2
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=True
        )

        # Настройка шрифтов для WeasyPrint (поддержка кириллицы)
        self.font_config = FontConfiguration()

    def _load_logo(self, logo_path: Optional[str] = None) -> Optional[str]:
        """
        Загружает логотип и конвертирует его в base64 для вставки в HTML.

        Args:
            logo_path: Путь к файлу логотипа (PNG, JPG)

        Returns:
            Base64-строка с изображением или None
        """
        if not logo_path:
            # Ищем логотип в папке static по умолчанию
            default_logo = self.static_dir / "logo.png"
            if not default_logo.exists():
                return None
            logo_path = str(default_logo)

        try:
            with open(logo_path, "rb") as f:
                logo_data = f.read()
            logo_base64 = base64.b64encode(logo_data).decode("utf-8")

            # Определяем MIME-тип
            ext = os.path.splitext(logo_path)[1].lower()
            mime_types = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".svg": "image/svg+xml"
            }
            mime_type = mime_types.get(ext, "image/png")

            return f"data:{mime_type};base64,{logo_base64}"
        except Exception as e:
            print(f"Ошибка загрузки логотипа: {e}")
            return None

    def generate(
        self,
        data: Dict[str, Any],
        output_path: Optional[str] = None,
        logo_path: Optional[str] = None
    ) -> bytes:
        """
        Генерирует PDF из переданных данных.

        Args:
            data: Словарь с данными для шаблона
            output_path: Путь для сохранения PDF (если None, возвращает bytes)
            logo_path: Путь к логотипу (опционально)

        Returns:
            PDF-документ в виде bytes (если output_path не указан)
        """
        # Загружаем логотип
        logo_base64 = self._load_logo(logo_path)
        if logo_base64:
            data["logo_base64"] = logo_base64

        # Добавляем дату генерации, если не указана
        if "generated_date" not in data:
            data["generated_date"] = datetime.now().strftime("%d.%m.%Y")

        # Добавляем номер документа, если не указан
        if "doc_number" not in data:
            data["doc_number"] = f"НМЦК-{datetime.now().strftime('%Y%m%d')}-{data.get('user_id', '00')}"

        # Загружаем и рендерим шаблон
        template = self.env.get_template("procurement_report.html")
        html_content = template.render(**data)

        # Генерируем PDF с поддержкой кириллицы
        html = HTML(string=html_content, base_url=str(self.static_dir))

        # Настройки CSS для печати
        css = CSS(string="""
            @page {
                size: A4;
                margin: 20mm 25mm;
            }
        """)

        pdf_bytes = html.write_pdf(
            stylesheets=[css],
            font_config=self.font_config,
            optimize_size=True
        )

        # Сохраняем в файл, если указан путь
        if output_path:
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)
            return pdf_bytes

        return pdf_bytes


# ============================================================
# ФУНКЦИЯ-ПОМОЩНИК ДЛЯ ПОДГОТОВКИ ДАННЫХ ИЗ БД
# ============================================================

def prepare_pdf_data(
    procurement: Dict[str, Any],
    suppliers: List[Dict[str, Any]],
    timeline: List[Dict[str, Any]],
    company_name: str = "Наименование организации",
    responsible_person: str = "",
    logo_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Подготавливает данные из БД к формату для PDF-шаблона.

    Args:
        procurement: Словарь с данными закупки (из таблицы procurements)
        suppliers: Список поставщиков (из таблицы suppliers)
        timeline: Список версий (из таблицы procurement_timeline)
        company_name: Название организации
        responsible_person: ФИО ответственного лица
        logo_path: Путь к логотипу

    Returns:
        Словарь для передачи в PDFGenerator.generate()
    """

    def format_date(value):
        if value:
            if hasattr(value, 'strftime'):
                return value.strftime("%d.%m.%Y")
            return str(value)
        return "—"

    # Форматируем даты
    dates = {
        "publication_date": format_date(procurement.get("publication_date")),
        "bid_end_date": format_date(procurement.get("bid_end_date")),
        "consideration_date": format_date(procurement.get("consideration_date")),
        "auction_date": format_date(procurement.get("auction_date")),
        "signing_date": format_date(procurement.get("signing_date")),
        "bg_deadline_date": format_date(procurement.get("bg_deadline_date")),
        "applied_bid_days": procurement.get("custom_bid_days") or procurement.get("applied_bid_days") or 0,
        "applied_review_days": procurement.get("custom_review_days") or procurement.get("applied_review_days") or 0,
        "applied_signing_days": 5,
    }

    # Формируем журнал изменений
    timeline_data = []
    for entry in timeline:
        timeline_data.append({
            "revision_number": entry.get("revision_number", 1),
            "shift_days": entry.get("shift_days", 0),
            "publication_date": format_date(entry.get("publication_date")),
            "bid_end_date": format_date(entry.get("bid_end_date")),
            "consideration_date": format_date(entry.get("consideration_date")),
            "signing_date": format_date(entry.get("signing_date")),
            "risk_warning": entry.get("risk_warning", ""),
            "is_final": entry.get("is_final", False),
        })

    # Подготовка данных для таблицы поставщиков
    suppliers_data = []
    for supplier in suppliers:
        suppliers_data.append({
            "name": supplier.get("name", "Не указан"),
            "inn": supplier.get("inn", "—"),
            "price": supplier.get("price", 0),
            "note": supplier.get("note", ""),
        })

    # Если поставщиков меньше 3, добавляем заглушки
    while len(suppliers_data) < 3:
        suppliers_data.append({
            "name": f"Поставщик {len(suppliers_data) + 1}",
            "inn": "—",
            "price": 0,
            "note": "—",
        })

    return {
        "company_name": company_name,
        "responsible_person": responsible_person or "_______________",
        "doc_number": procurement.get("doc_number", f"НМЦК-{datetime.now().strftime('%Y%m%d')}"),
        "law_type": procurement.get("law_type", "44-ФЗ"),
        "nmck_final": procurement.get("nmck", 0),
        "nmck_average": procurement.get("nmck", 0),
        "nmck_method": "average",
        "suppliers": suppliers_data,
        "dates": dates,
        "timeline": timeline_data,
        "critical_dates": [],
        "scatter_warning": procurement.get("scatter_warning", ""),
        "logo_path": logo_path,
        "user_id": procurement.get("user_id"),
    }