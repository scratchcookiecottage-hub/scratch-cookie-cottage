"""
Scratch Cookie Cottage — Texas cottage-food labels
Sized for Avery U-0090-01 / 5163 / 8163 / 18163 / 15513
10-up shipping labels: 2 in tall x 4 in wide on US Letter.

Uses DSHS unique identification number in place of the home address
(Texas Health & Safety Code §437.0193(b-1)).
"""

from io import BytesIO
from pathlib import Path

from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

DIR = Path(__file__).resolve().parent
LOGO = DIR / "logo.png"
QR = DIR / "qrcode.png"
OUT = DIR

# --- edit these before printing for sale ---
BUSINESS_NAME = "Scratch Cookie Cottage"
# Texas HSC §437.0193(b-1): DSHS unique ID may replace the home address
DSHS_ID = "17384"
PRODUCER_LINE = f"DSHS ID #{DSHS_ID}"
WEBSITE = "scratchcookiecottage.com"
NET_WT = "Net Wt. 90 g (3.17 oz)"
QR_CAPTION = ("Scan to order", "cookies")

# Texas Health & Safety Code §437.0193 — must be exact, all caps
DISCLOSURE = (
    "THIS PRODUCT WAS PRODUCED IN A PRIVATE RESIDENCE THAT IS NOT "
    "SUBJECT TO GOVERNMENTAL LICENSING OR INSPECTION."
)

CROSS_CONTACT = "Made in a kitchen that also processes peanuts and tree nuts."

FLAVORS = [
    {
        "id": "brown-butter-chocolate-chip",
        "name": "Brown Butter Chocolate Chip",
        "contains": "Contains: Wheat, Eggs, Milk, Soy",
        "ingredients": (
            "Unbleached Flour, Dark Brown Sugar, Butter, Chocolate, "
            "Eggs, Vanilla Bean Extract, Salt."
        ),
    },
    {
        "id": "macadamia-white-chocolate",
        "name": "Macadamia White Chocolate",
        "contains": "Contains: Wheat, Eggs, Milk, Soy, Tree nuts (Macadamia, Almonds)",
        "ingredients": (
            "Unbleached Flour, Sugar, Butter, Macadamia Nuts, White Chocolate, "
            "Brown Sugar, Eggs, Milk Powder, Salt, Vanilla Bean Extract, "
            "Almond Extract, Vanilla Bean."
        ),
    },
    {
        "id": "salted-caramel-chocolate-pecan",
        "name": "Salted Caramel Chocolate Pecan",
        "contains": "Contains: Wheat, Eggs, Milk, Soy, Tree nuts (Pecans)",
        "ingredients": (
            "Unbleached Flour, Dark Brown Sugar, Butter, Chocolate, Sugar, "
            "Eggs, Pecan, Milk Powder, Caramel, Vanilla Bean Extract, Salt."
        ),
    },
    {
        "id": "white-miso-peanut-butter",
        "name": "White Miso Peanut Butter",
        "contains": "Contains: Wheat, Eggs, Milk, Soy, Peanuts",
        "ingredients": (
            "Unbleached Flour, Peanut Butter, Butter, Sugar, Brown Sugar, "
            "Eggs, White Miso, Vanilla, Honey, Salt."
        ),
    },
]

# Order-catalog cookie_id -> label flavor id
COOKIE_ID_TO_FLAVOR_ID = {
    "chocolate_chip": "brown-butter-chocolate-chip",
    "macadamia": "macadamia-white-chocolate",
    "salted_caramel": "salted-caramel-chocolate-pecan",
    "peanut_butter": "white-miso-peanut-butter",
}
FLAVOR_BY_ID = {f["id"]: f for f in FLAVORS}

# Avery 5163 / 8163 / 18163 / 15513 / U-0090-01
# If a test print sits high/low or left/right, nudge these (inches).
# Positive X = move design right. Positive Y = move design down.
OFFSET_X_IN = 0.00
OFFSET_Y_IN = 0.00

PAGE_W = 8.5 * inch
PAGE_H = 11 * inch
LABEL_W = 4.0 * inch
LABEL_H = 2.0 * inch
LEFT = 0.15625 * inch + OFFSET_X_IN * inch
TOP = 0.5 * inch + OFFSET_Y_IN * inch
H_PITCH = 4.1875 * inch
V_PITCH = 2.0 * inch


def new_canvas(dest, title: str) -> canvas.Canvas:
    """US Letter PDF that printers must not scale. dest is a path or file object."""
    if isinstance(dest, Path):
        dest = str(dest)
    c = canvas.Canvas(dest, pagesize=(PAGE_W, PAGE_H))
    c.setTitle(title)
    c.setAuthor(BUSINESS_NAME)
    c.setViewerPreference("PrintScaling", "None")
    return c


def flavor_for_cookie_id(cookie_id: str):
    flavor_id = COOKIE_ID_TO_FLAVOR_ID.get(cookie_id, cookie_id)
    return FLAVOR_BY_ID.get(flavor_id)


def build_labels_pdf(qty_by_cookie_id, title=None, extra_flavors=None):
    """Build Avery 5163 sheets for the given cookie_id -> count map."""
    extra_flavors = extra_flavors or {}
    queue: list[dict] = []
    order = list(COOKIE_ID_TO_FLAVOR_ID.keys())
    for cookie_id in extra_flavors:
        if cookie_id not in order:
            order.insert(0, cookie_id)
    for cookie_id in order:
        qty = int(qty_by_cookie_id.get(cookie_id, 0) or 0)
        if qty <= 0:
            continue
        if cookie_id in extra_flavors:
            flavor = extra_flavors[cookie_id]
        else:
            flavor = FLAVOR_BY_ID[COOKIE_ID_TO_FLAVOR_ID[cookie_id]]
        queue.extend([flavor] * qty)
    if not queue:
        raise ValueError("No labels to print")

    buf = BytesIO()
    c = new_canvas(buf, title or f"{BUSINESS_NAME} — labels")
    for i, flavor in enumerate(queue):
        if i and i % 10 == 0:
            c.showPage()
        slot = i % 10
        row, col = divmod(slot, 2)
        x = LEFT + col * H_PITCH
        y = PAGE_H - TOP - (row + 1) * V_PITCH
        draw_label(c, x, y, flavor)
    c.save()
    return buf.getvalue()


def wrap(text: str, font: str, size: float, max_w: float) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = w if not cur else f"{cur} {w}"
        if stringWidth(trial, font, size) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def draw_block(c, text, font, size, x, y, max_w, leading) -> float:
    c.setFont(font, size)
    for line in wrap(text, font, size, max_w):
        c.drawString(x, y, line)
        y -= leading
    return y


def draw_label(c: canvas.Canvas, x: float, y: float, flavor: dict) -> None:
    pad = 6
    ix, iy = x + pad, y + pad
    iw, ih = LABEL_W - 2 * pad, LABEL_H - 2 * pad

    # Hairline on the die-cut so you can see if the printer is shifting.
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.3)
    c.rect(x, y, LABEL_W, LABEL_H, stroke=1, fill=0)

    # Lower band: DSHS ID + required cottage-food warning
    disc_size = 5.9
    disc_lead = 7.2
    disc_lines = wrap(DISCLOSURE, "Helvetica-Bold", disc_size, iw)
    id_line = f"{PRODUCER_LINE}  ·  {WEBSITE}"
    band_h = 11 + len(disc_lines) * disc_lead
    band_top = iy + band_h

    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.4)
    c.line(ix, band_top, ix + iw, band_top)

    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 6.3)
    c.drawCentredString(ix + iw / 2, band_top - 9, id_line)
    c.setFont("Helvetica-Bold", disc_size)
    dy = band_top - 18
    for line in disc_lines:
        c.drawCentredString(ix + iw / 2, dy, line)
        dy -= disc_lead

    qr_size = 62
    logo_size = 36
    qr_x = ix + iw - qr_size
    qr_y = iy + ih - qr_size + 1
    logo_x = ix
    logo_y = iy + ih - logo_size - 1

    if LOGO.exists():
        c.drawImage(
            ImageReader(str(LOGO)),
            logo_x,
            logo_y,
            width=logo_size,
            height=logo_size,
            mask="auto",
            preserveAspectRatio=True,
            anchor="c",
        )
    if QR.exists():
        c.setFillColorRGB(1, 1, 1)
        c.rect(qr_x - 1, qr_y - 1, qr_size + 2, qr_size + 2, stroke=0, fill=1)
        c.drawImage(
            ImageReader(str(QR)),
            qr_x,
            qr_y,
            width=qr_size,
            height=qr_size,
            mask="auto",
            preserveAspectRatio=True,
            anchor="c",
        )
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 5.5)
        cap_y = qr_y - 7
        for line in QR_CAPTION:
            c.drawCentredString(qr_x + qr_size / 2, cap_y, line)
            cap_y -= 6.4
        qr_bottom = cap_y + 3
    else:
        qr_bottom = qr_y

    text_left = logo_x + logo_size + 5
    text_w = qr_x - 5 - text_left

    c.setFillColorRGB(0, 0, 0)
    py = iy + ih - 10
    py = draw_block(c, BUSINESS_NAME.upper(), "Helvetica-Bold", 8, text_left, py, text_w, 10)
    py = draw_block(c, flavor["name"], "Helvetica-Bold", 9, text_left, py, text_w, 11)
    py = draw_block(c, NET_WT, "Helvetica-Bold", 6.5, text_left, py, text_w, 8.5)
    py = draw_block(c, flavor["contains"], "Helvetica-Bold", 6.4, text_left, py, text_w, 8)

    ingredients = (flavor.get("ingredients") or "").strip()
    if ingredients:
        ing = (
            ingredients
            if ingredients.lower().startswith("ingredients")
            else f"Ingredients: {ingredients}"
        )
        lines = wrap(ing, "Helvetica", 5.5, text_w)
        leftover: list[str] = []
        c.setFont("Helvetica", 5.5)
        for i, line in enumerate(lines):
            if py < qr_bottom + 1:
                leftover = lines[i:]
                break
            c.drawString(text_left, py, line)
            py -= 6.6
        if leftover:
            py = min(py, qr_bottom - 1)
            py = draw_block(c, " ".join(leftover), "Helvetica", 5.5, ix, py, iw, 6.6)

    # kitchen note follows the ingredients, above the lower band
    note_y = min(py - 3, qr_bottom - 1)
    if note_y > band_top + 7:
        draw_block(c, CROSS_CONTACT, "Helvetica", 5.6, ix, note_y, iw, 7)


def draw_sheet(c: canvas.Canvas, flavor: dict) -> None:
    c.setTitle(f"{BUSINESS_NAME} — {flavor['name']}")
    c.setAuthor(BUSINESS_NAME)
    for row in range(5):
        for col in range(2):
            x = LEFT + col * H_PITCH
            y = PAGE_H - TOP - (row + 1) * V_PITCH
            draw_label(c, x, y, flavor)


def write_flavor_pdf(flavor: dict) -> Path:
    path = OUT / f"print-{flavor['id']}.pdf"
    c = new_canvas(path, f"{BUSINESS_NAME} — {flavor['name']}")
    draw_sheet(c, flavor)
    c.save()
    return path


def write_all_flavors_pdf() -> Path:
    path = OUT / "Scratch-Cookie-Cottage-TX-Labels.pdf"
    c = new_canvas(path, f"{BUSINESS_NAME} — Texas cottage food labels")
    for i, flavor in enumerate(FLAVORS):
        if i:
            c.showPage()
        draw_sheet(c, flavor)
    c.save()
    return path


def write_sample_sheet() -> Path:
    """One Avery sheet: two of each flavor, last row blank."""
    path = OUT / "Scratch-Cookie-Cottage-TX-Labels-SAMPLE.pdf"
    c = new_canvas(path, f"{BUSINESS_NAME} — sample sheet (2 of each)")
    c.setFont("Helvetica", 6)
    c.setFillColorRGB(0.25, 0.25, 0.25)
    c.drawCentredString(
        PAGE_W / 2,
        PAGE_H - 22,
        "PRINT SETTINGS: Letter  ·  Actual size / 100%  ·  turn OFF Fit / Shrink to printable area",
    )
    slots = []
    for flavor in FLAVORS:
        slots.extend([flavor, flavor])
    for i, flavor in enumerate(slots):
        row, col = divmod(i, 2)
        x = LEFT + col * H_PITCH
        y = PAGE_H - TOP - (row + 1) * V_PITCH
        draw_label(c, x, y, flavor)
    c.save()
    return path


def write_align_test() -> Path:
    """Plain-paper overlay: empty boxes on the exact Avery grid."""
    path = OUT / "Scratch-Cookie-Cottage-ALIGN-TEST.pdf"
    c = new_canvas(path, f"{BUSINESS_NAME} — Avery 5163 alignment test")
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 20, "ALIGNMENT TEST — print on PLAIN paper, then lay over an unused label sheet")
    c.setFont("Helvetica", 7)
    c.drawCentredString(
        PAGE_W / 2,
        PAGE_H - 32,
        "Print Letter, Actual size / 100%. Do NOT use Fit, Shrink, or Fit to printable area.",
    )
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.4)
    for row in range(5):
        for col in range(2):
            x = LEFT + col * H_PITCH
            y = PAGE_H - TOP - (row + 1) * V_PITCH
            c.rect(x, y, LABEL_W, LABEL_H, stroke=1, fill=0)
            c.setFont("Helvetica", 8)
            n = row * 2 + col + 1
            c.drawCentredString(x + LABEL_W / 2, y + LABEL_H / 2 - 3, f"{n}")
    c.setFont("Helvetica", 7)
    c.drawCentredString(
        PAGE_W / 2,
        18,
        "Boxes should sit on the sticker outlines. If the whole grid is shifted, tell me which way (up/down/left/right).",
    )
    c.save()
    return path


def write_single_proofs() -> list[Path]:
    """One oversized 4x2 label per flavor for on-screen proofing."""
    paths = []
    for flavor in FLAVORS:
        path = OUT / f"proof-{flavor['id']}.pdf"
        c = canvas.Canvas(str(path), pagesize=(LABEL_W, LABEL_H))
        draw_label(c, 0, 0, flavor)
        c.save()
        paths.append(path)
    return paths


if __name__ == "__main__":
    made = [write_flavor_pdf(f) for f in FLAVORS]
    made.append(write_all_flavors_pdf())
    made.append(write_sample_sheet())
    made.append(write_align_test())
    proofs = write_single_proofs()
    print("Wrote:")
    for p in made + proofs:
        print(" ", p)
