"""
One-shot brand kit: 1-color SVG variants, PNG copies, QR codes for /order and /markets.

Run from the project root:
  .venv\\Scripts\\python.exe scripts/export_brand.py

Pillow and qrcode are optional (script-only). Production requirements.txt is unchanged.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_SVG = ROOT / "static" / "images" / "logo.svg"
SRC_PNG = ROOT / "static" / "images" / "logo.png"
OUT = ROOT / "static" / "brand"

BROWN = "#3D3229"
CREAM = "#FDF9F5"
BLACK = "#000000"

PUBLIC_BASE = os.getenv(
    "PUBLIC_BASE_URL",
    "https://scratchcookiecottage.pythonanywhere.com",
).rstrip("/")


def write_svg(fill: str, dest: Path) -> None:
    text = SRC_SVG.read_text(encoding="utf-8")
    text = text.replace("fill:#000000", f"fill:{fill}")
    dest.write_text(text, encoding="utf-8")


def copy_pngs() -> None:
    if SRC_PNG.is_file():
        shutil.copy2(SRC_PNG, OUT / "logo.png")
        shutil.copy2(SRC_PNG, OUT / "logo-1024.png")
    fav = ROOT / "static" / "images" / "favicon.png"
    if fav.is_file():
        shutil.copy2(fav, OUT / "favicon.png")


def try_qr(path: Path, url: str) -> None:
    try:
        import qrcode
    except ImportError:
        print("qrcode not installed — skip", path.name)
        return
    qr = qrcode.QRCode(border=2, box_size=12, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(path)


def try_resize_png() -> None:
    src = OUT / "logo.png"
    if not src.is_file():
        return
    try:
        from PIL import Image
    except ImportError:
        print("Pillow not installed — skip PNG sizes")
        return
    im = Image.open(src).convert("RGBA")
    for size, name in ((512, "logo-512.png"), (1024, "logo-1024.png")):
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        fitted = im.copy()
        fitted.thumbnail((size, size), Image.Resampling.LANCZOS)
        x = (size - fitted.width) // 2
        y = (size - fitted.height) // 2
        canvas.paste(fitted, (x, y), fitted)
        canvas.save(OUT / name, "PNG")


def write_readme() -> None:
    (OUT / "README.txt").write_text(
        f"""Scratch Cookie Cottage — logo & QR pack
Tagline: From Scratch. From the Cottage.
Palette: brown {BROWN} · cream {CREAM} · caramel #C68B59 · sage #A8B5A2 · charcoal #2C2C2C

Files
-----
logo.svg          1-color black, transparent background (print, vinyl, embroidery)
logo-brown.svg    1-color brown {BROWN}
logo-cream.svg    1-color cream {CREAM} — use on brown banners
logo.png          Raster copy of the current site logo
logo-512.png      Square transparent PNG
logo-1024.png     Square transparent PNG
qr-order.png      Points to {PUBLIC_BASE}/order
qr-markets.png    Points to {PUBLIC_BASE}/markets
favicon.png       Site favicon

Print notes
-----------
- Use the SVG for labels, stickers, and the booth banner.
- Cream logo on a brown (#3D3229) field; brown logo on cream.
- QR codes: print at least 1 inch square. Booth sign can say
  “Scan to order” (order QR) or “This week’s markets” (markets QR).
""",
        encoding="utf-8",
    )


def main() -> int:
    if not SRC_SVG.is_file():
        print("Missing", SRC_SVG, file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC_SVG, OUT / "logo.svg")
    write_svg(BROWN, OUT / "logo-brown.svg")
    write_svg(CREAM, OUT / "logo-cream.svg")
    copy_pngs()
    try_resize_png()
    try_qr(OUT / "qr-order.png", f"{PUBLIC_BASE}/order")
    try_qr(OUT / "qr-markets.png", f"{PUBLIC_BASE}/markets")
    write_readme()
    print("Wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
