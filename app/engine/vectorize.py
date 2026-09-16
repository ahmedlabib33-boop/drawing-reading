from __future__ import annotations
from xml.sax.saxutils import escape
import fitz


def pdf_page_to_svg(pdf_bytes: bytes, page_index: int = 0) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if page_index < 0 or page_index >= len(doc):
        raise IndexError(f"page_index {page_index} outside 0..{len(doc)-1}")
    page = doc[page_index]
    width, height = page.rect.width, page.rect.height
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.2f} {height:.2f}" width="{width:.2f}" height="{height:.2f}">',
        '<rect width="100%" height="100%" fill="white"/>',
    ]
    for drawing in page.get_drawings():
        stroke = _rgb_hex(drawing.get("color")) or "black"
        fill = _rgb_hex(drawing.get("fill")) or "none"
        stroke_width = drawing.get("width") or 0.5
        path_d = _path_from(drawing)
        if path_d:
            parts.append(f'<path d="{path_d}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width:.2f}"/>')

    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                txt = (span.get("text") or "").strip()
                if not txt:
                    continue
                x, y = span["origin"]
                size = span.get("size", 10)
                fill = _int_hex(span.get("color", 0))
                font = escape(str(span.get("font", "sans-serif")))
                parts.append(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size:.2f}" font-family="{font}" fill="{fill}">{escape(txt)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _path_from(drawing: dict) -> str:
    segs: list[str] = []
    for item in drawing.get("items", []):
        try:
            kind = item[0]
            if kind == "l":
                segs.append(f"M {item[1].x:.2f} {item[1].y:.2f} L {item[2].x:.2f} {item[2].y:.2f}")
            elif kind == "re":
                rect = item[1]
                segs.append(f"M {rect.x0:.2f} {rect.y0:.2f} H {rect.x1:.2f} V {rect.y1:.2f} H {rect.x0:.2f} Z")
            elif kind == "c":
                segs.append(f"M {item[1].x:.2f} {item[1].y:.2f} C {item[2].x:.2f} {item[2].y:.2f} {item[3].x:.2f} {item[3].y:.2f} {item[4].x:.2f} {item[4].y:.2f}")
        except Exception:
            continue
    return " ".join(segs)


def _rgb_hex(color) -> str | None:
    if color is None:
        return None
    try:
        r, g, b = (max(0, min(255, int(255 * value))) for value in color)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return None


def _int_hex(value: int) -> str:
    try:
        return f"#{(value >> 16) & 0xFF:02x}{(value >> 8) & 0xFF:02x}{value & 0xFF:02x}"
    except Exception:
        return "#000000"
