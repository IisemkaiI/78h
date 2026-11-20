"""Generate the fixed landscape certificate PDF template (version 1)."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from threading import Lock
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
_FONT_LOCK = Lock()
_FONTS_REGISTERED = False
_MONTHS_RU = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)


def _register_fonts() -> None:
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    with _FONT_LOCK:
        if _FONTS_REGISTERED:
            return
        pdfmetrics.registerFont(TTFont("EducationNoto", str(ASSETS_DIR / "NotoSans-Regular.ttf")))
        pdfmetrics.registerFont(TTFont("EducationNotoBold", str(ASSETS_DIR / "NotoSans-Bold.ttf")))
        pdfmetrics.registerFontFamily(
            "EducationNoto",
            normal="EducationNoto",
            bold="EducationNotoBold",
            italic="EducationNoto",
            boldItalic="EducationNotoBold",
        )
        _FONTS_REGISTERED = True


def _format_date(value: datetime) -> str:
    local_date = value.astimezone(UTC)
    return f"{local_date.day} {_MONTHS_RU[local_date.month - 1]} {local_date.year}"


def _draw_paragraph(
    canvas: Canvas,
    text: str,
    *,
    x: float,
    top: float,
    width: float,
    font_size: int,
    leading: int,
    font_name: str = "EducationNoto",
    color: colors.Color,
) -> float:
    style = ParagraphStyle(
        name="CertificateText",
        fontName=font_name,
        fontSize=font_size,
        leading=leading,
        textColor=color,
        alignment=TA_CENTER,
        spaceAfter=0,
        spaceBefore=0,
    )
    paragraph = Paragraph(escape(text), style)
    _, height = paragraph.wrap(width, 200)
    paragraph.drawOn(canvas, x, top - height)
    return height


def render_certificate_pdf(
    *,
    recipient_name: str,
    course_title: str,
    completion_date: datetime,
    issued_at: datetime,
    certificate_number: str,
    verification_url: str,
    template_version: str = "1",
) -> bytes:
    """Return a standalone A4 landscape PDF from the immutable issue snapshot."""
    _register_fonts()
    page_width, page_height = landscape(A4)
    buffer = BytesIO()
    canvas = Canvas(buffer, pagesize=(page_width, page_height), pageCompression=1)
    canvas.setTitle(f"Certificate {certificate_number}")
    canvas.setAuthor("Education Platform")
    canvas.setSubject(f"Course completion certificate: {course_title}")

    forest = colors.HexColor("#173c2e")
    green = colors.HexColor("#276648")
    paper = colors.HexColor("#f5f4ee")
    ink = colors.HexColor("#1d2923")
    muted = colors.HexColor("#66736a")
    lime = colors.HexColor("#d8f36a")

    canvas.setFillColor(paper)
    canvas.rect(0, 0, page_width, page_height, stroke=0, fill=1)
    canvas.setStrokeColor(forest)
    canvas.setLineWidth(2)
    canvas.rect(25, 25, page_width - 50, page_height - 50, stroke=1, fill=0)
    canvas.setStrokeColor(colors.HexColor("#b7c6a7"))
    canvas.setLineWidth(.7)
    canvas.rect(35, 35, page_width - 70, page_height - 70, stroke=1, fill=0)

    canvas.setFillColor(forest)
    canvas.rect(36, page_height - 70, page_width - 72, 34, stroke=0, fill=1)
    canvas.setFillColor(lime)
    canvas.setFont("EducationNotoBold", 10)
    canvas.drawString(58, page_height - 58, "EDUCATION PLATFORM")
    canvas.setFillColor(colors.HexColor("#d5e0d0"))
    canvas.setFont("EducationNoto", 8)
    canvas.drawRightString(page_width - 58, page_height - 58, "БЕСПЛАТНОЕ ОТКРЫТОЕ ОБРАЗОВАНИЕ")

    canvas.setFillColor(green)
    canvas.setFont("EducationNotoBold", 27)
    canvas.drawCentredString(page_width / 2, page_height - 146, "СЕРТИФИКАТ")
    canvas.setFillColor(muted)
    canvas.setFont("EducationNoto", 11)
    canvas.drawCentredString(page_width / 2, page_height - 169, "о завершении образовательного курса")

    canvas.setFillColor(ink)
    canvas.setFont("EducationNoto", 11)
    canvas.drawCentredString(page_width / 2, page_height - 218, "Настоящий сертификат подтверждает, что")
    _draw_paragraph(
        canvas,
        recipient_name,
        x=80,
        top=page_height - 237,
        width=page_width - 160,
        font_size=27,
        leading=34,
        font_name="EducationNotoBold",
        color=forest,
    )
    canvas.setStrokeColor(colors.HexColor("#92aa86"))
    canvas.setLineWidth(1)
    canvas.line(page_width * .27, page_height - 284, page_width * .73, page_height - 284)
    canvas.setFillColor(muted)
    canvas.setFont("EducationNoto", 10)
    canvas.drawCentredString(page_width / 2, page_height - 310, "успешно завершил(а) курс")

    course_top = page_height - 328
    course_height = _draw_paragraph(
        canvas,
        course_title,
        x=105,
        top=course_top,
        width=page_width - 210,
        font_size=19,
        leading=25,
        font_name="EducationNotoBold",
        color=ink,
    )

    dates_y = max(124, course_top - course_height - 37)
    canvas.setStrokeColor(colors.HexColor("#d6ddce"))
    canvas.line(page_width * .33, dates_y + 20, page_width * .67, dates_y + 20)
    canvas.setFillColor(muted)
    canvas.setFont("EducationNoto", 9)
    canvas.drawCentredString(page_width / 2, dates_y, f"Дата завершения: {_format_date(completion_date)}")
    canvas.drawCentredString(page_width / 2, dates_y - 16, f"Дата выдачи: {_format_date(issued_at)}")

    footer_y = 56
    canvas.setFillColor(ink)
    canvas.setFont("EducationNotoBold", 8)
    canvas.drawString(58, footer_y + 17, f"Номер: {certificate_number}")
    canvas.setFillColor(muted)
    canvas.setFont("EducationNoto", 7)
    verification_label = "Проверить подлинность сертификата"
    label_width = pdfmetrics.stringWidth(verification_label, "EducationNoto", 7)
    label_x = page_width - 58 - label_width
    canvas.drawString(label_x, footer_y + 17, verification_label)
    canvas.linkURL(
        verification_url,
        (label_x, footer_y + 14, page_width - 58, footer_y + 28),
        relative=0,
        thickness=0,
    )
    canvas.setFillColor(muted)
    canvas.setFont("EducationNoto", 6)
    canvas.drawString(58, footer_y + 4, f"Версия шаблона {template_version}")
    canvas.drawRightString(page_width - 58, footer_y + 4, verification_url)

    canvas.showPage()
    canvas.save()
    return buffer.getvalue()
