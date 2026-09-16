from __future__ import annotations
import io
from dataclasses import dataclass
import fitz
from PIL import Image


@dataclass
class RasterPage:
    page_index: int
    width_pt: float
    height_pt: float
    dpi: int
    png_bytes: bytes
    pil: Image.Image


def rasterize_page(pdf_bytes: bytes, page_index: int = 0, dpi: int = 250) -> RasterPage:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if page_index < 0 or page_index >= len(doc):
        raise IndexError(f"page_index {page_index} outside 0..{len(doc)-1}")
    page = doc[page_index]
    mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    png_bytes = pix.tobytes("png")
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    return RasterPage(page_index=page_index, width_pt=page.rect.width, height_pt=page.rect.height, dpi=dpi, png_bytes=png_bytes, pil=img)
