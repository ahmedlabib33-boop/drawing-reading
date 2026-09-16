from __future__ import annotations
import base64
import io
from xml.sax.saxutils import escape
from PIL import Image
from .ocr import OCRWord


def build_searchable_svg(pil_img: Image.Image, words: list[OCRWord], page_width_pt: float, page_height_pt: float) -> str:
    width_px, height_px = pil_img.size
    sx = page_width_pt / width_px
    sy = page_height_pt / height_px
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 {page_width_pt:.2f} {page_height_pt:.2f}" width="{page_width_pt:.2f}" height="{page_height_pt:.2f}">',
        f'<image x="0" y="0" width="{page_width_pt:.2f}" height="{page_height_pt:.2f}" xlink:href="data:image/png;base64,{b64}" preserveAspectRatio="none"/>',
        '<g fill="transparent" stroke="none" font-family="monospace">',
    ]
    for word in words:
        x = word.x * sx
        y = (word.y + word.h) * sy
        font_size = max(1.0, word.h * sy * 1.05)
        parts.append(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{font_size:.2f}" data-conf="{word.conf:.0f}">{escape(word.text)}</text>')
    parts.append("</g></svg>")
    return "".join(parts)
