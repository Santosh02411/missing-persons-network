"""Generates a one-page, printable missing-person flyer PDF for a case:
photo, key details, and a QR code that opens the case directly on the
website (for reporting a sighting on the spot)."""
import io

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from app.core.config import settings
from app.models.case import Case
from app.services.upload_service import read_upload_bytes

PAGE_WIDTH, PAGE_HEIGHT = letter
MARGIN = 0.55 * inch

INK = colors.HexColor("#0f1c33")
SLATE = colors.HexColor("#3d5a80")
GRAYTEXT = colors.HexColor("#5b6472")
BEACON = colors.HexColor("#c8871f")
MIST = colors.HexColor("#dce3ec")


def _build_qr_image(case_id) -> ImageReader:
    url = f"{settings.FRONTEND_URL.rstrip('/')}/cases/{case_id}"
    qr = qrcode.QRCode(border=1, box_size=8, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#" + INK.hexval()[2:], back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def _draw_wrapped_text(c: canvas.Canvas, text: str, x: float, y: float, width: float, style: ParagraphStyle) -> float:
    """Draws a paragraph of wrapped body text and returns the y position
    just below it, so the caller can keep stacking content underneath."""
    para = Paragraph(text.replace("\n", "<br/>"), style)
    _, h = para.wrap(width, PAGE_HEIGHT)
    para.drawOn(c, x, y - h)
    return y - h


def generate_flyer_pdf(case: Case) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)

    content_width = PAGE_WIDTH - 2 * MARGIN
    y = PAGE_HEIGHT - MARGIN

    # -- Masthead --------------------------------------------------------
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(MARGIN, y - 12, "REUNIFICATION NETWORK")
    c.setFont("Helvetica", 9)
    c.setFillColor(GRAYTEXT)
    c.drawRightString(PAGE_WIDTH - MARGIN, y - 12, "National Missing Persons Registry")
    c.setStrokeColor(MIST)
    c.setLineWidth(1)
    c.line(MARGIN, y - 22, PAGE_WIDTH - MARGIN, y - 22)
    y -= 45

    # -- "MISSING" headline ------------------------------------------------
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 34)
    c.drawString(MARGIN, y - 30, "MISSING")
    y -= 50

    # -- Photo (left) + key facts (right) --------------------------------
    photo_size = 2.3 * inch
    photo_x = MARGIN
    photo_y = y - photo_size

    photo_bytes = read_upload_bytes(case.photo_url)
    if photo_bytes:
        try:
            img = ImageReader(io.BytesIO(photo_bytes))
            c.drawImage(
                img, photo_x, photo_y, width=photo_size, height=photo_size,
                preserveAspectRatio=True, anchor="n", mask="auto",
            )
        except Exception:
            photo_bytes = None
    if not photo_bytes:
        c.setFillColor(MIST)
        c.rect(photo_x, photo_y, photo_size, photo_size, fill=1, stroke=0)
        c.setFillColor(GRAYTEXT)
        c.setFont("Helvetica", 9)
        c.drawCentredString(photo_x + photo_size / 2, photo_y + photo_size / 2, "No photo provided")
    c.setStrokeColor(MIST)
    c.setLineWidth(1)
    c.rect(photo_x, photo_y, photo_size, photo_size, fill=0, stroke=1)

    facts_x = photo_x + photo_size + 0.35 * inch
    facts_width = PAGE_WIDTH - MARGIN - facts_x
    fy = y

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(facts_x, fy - 22, case.name)
    fy -= 40

    label_style = ParagraphStyle("label", fontName="Helvetica-Bold", fontSize=8.5, textColor=GRAYTEXT, leading=11)
    value_style = ParagraphStyle("value", fontName="Helvetica", fontSize=11, textColor=INK, leading=14)

    def fact_row(label: str, value: str, yy: float) -> float:
        yy = _draw_wrapped_text(c, label.upper(), facts_x, yy, facts_width, label_style)
        yy = _draw_wrapped_text(c, value, facts_x, yy - 2, facts_width, value_style)
        return yy - 10

    if case.age_at_disappearance is not None:
        fy = fact_row("Age at disappearance", str(case.age_at_disappearance), fy)
    fy = fact_row("Last seen", case.last_seen_address, fy)
    fy = fact_row("Date last seen", case.last_seen_at.strftime("%d %b %Y"), fy)

    y = min(photo_y, fy) - 0.3 * inch

    # -- Description -------------------------------------------------------
    # A flyer is one page -- capped rather than shrunk-to-fit, so it never
    # collides with the CTA strip anchored at the bottom (below) regardless
    # of how long the case description happens to be. The full description
    # is always still one tap away via the QR code / case link.
    MAX_DESCRIPTION_CHARS = 480
    description = case.description
    if len(description) > MAX_DESCRIPTION_CHARS:
        description = description[:MAX_DESCRIPTION_CHARS].rsplit(" ", 1)[0] + "… (full details on the case page)"

    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(MARGIN, y, "DESCRIPTION")
    y -= 16
    desc_style = ParagraphStyle("desc", fontName="Helvetica", fontSize=10.5, textColor=INK, leading=15)
    y = _draw_wrapped_text(c, description, MARGIN, y, content_width, desc_style)

    # -- Call to action strip + QR code -------------------------------------
    # Anchored to the bottom margin (not "right after the description") so
    # the flyer fills the page like a real poster regardless of how long the
    # description happens to be, instead of leaving a large blank gap.
    strip_height = 1.7 * inch
    strip_y = MARGIN
    c.setFillColor(INK)
    c.roundRect(MARGIN, strip_y, content_width, strip_height, 8, fill=1, stroke=0)

    qr_size = strip_height - 0.3 * inch
    qr_img = _build_qr_image(case.id)
    c.drawImage(
        qr_img, PAGE_WIDTH - MARGIN - qr_size - 0.2 * inch, strip_y + 0.15 * inch,
        width=qr_size, height=qr_size,
    )

    text_x = MARGIN + 0.3 * inch
    text_width = content_width - qr_size - 0.9 * inch
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(text_x, strip_y + strip_height - 0.35 * inch, "Have you seen this person?")
    cta_style = ParagraphStyle("cta", fontName="Helvetica", fontSize=9.5, textColor=colors.HexColor("#c3d0e3"), leading=13)
    _draw_wrapped_text(
        c,
        "Scan the QR code, or visit the link below, to view this case and report a sighting "
        "directly to the police/NGO handling it.",
        text_x, strip_y + strip_height - 0.6 * inch, text_width, cta_style,
    )
    c.setFillColor(BEACON)
    c.setFont("Helvetica-Bold", 9)
    case_url = f"{settings.FRONTEND_URL.rstrip('/')}/cases/{case.id}"
    c.drawString(text_x, strip_y + 0.25 * inch, case_url)

    # -- Footer --------------------------------------------------------------
    c.setFillColor(GRAYTEXT)
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(
        PAGE_WIDTH / 2, MARGIN * 0.4,
        f"Case ID: {case.id} — Generated by the Reunification Network. Please report sightings through the website, not this flyer alone.",
    )

    c.showPage()
    c.save()
    return buf.getvalue()
