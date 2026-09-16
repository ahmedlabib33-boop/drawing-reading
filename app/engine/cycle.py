from __future__ import annotations
from dataclasses import dataclass, field
import fitz
from .raster import rasterize_page
from .ocr import OCRWord, available as ocr_available, ocr_image, to_base64_png
from .vectorize import pdf_page_to_svg
from .assembler import build_searchable_svg
from .svg_reader import extract_text_from_svg


@dataclass
class CycleResult:
    filename: str
    mode: str
    svg: str = ""
    text: str = ""
    words: list[OCRWord] = field(default_factory=list)
    png_b64: str = ""
    needs_client_ocr: bool = False
    char_count: int = 0


def run_cycle(filename: str, pdf_bytes: bytes, page_index: int = 0) -> CycleResult:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if page_index < 0 or page_index >= len(doc):
        raise IndexError(f"page_index {page_index} outside 0..{len(doc)-1}")
    page = doc[page_index]
    native_text = page.get_text("text")
    if len(native_text.strip()) >= 80:
        svg = pdf_page_to_svg(pdf_bytes, page_index)
        text = "\n".join(extract_text_from_svg(svg))
        return CycleResult(filename=filename, mode="vector", svg=svg, text=text, char_count=len(text))

    raster = rasterize_page(pdf_bytes, page_index, dpi=250)
    if ocr_available():
        words = ocr_image(raster.pil, psm=6) or ocr_image(raster.pil, psm=11)
        if words:
            svg = build_searchable_svg(raster.pil, words, raster.width_pt, raster.height_pt)
            text = "\n".join(extract_text_from_svg(svg))
            return CycleResult(filename=filename, mode="searchable", svg=svg, text=text, words=words, char_count=len(text))

    return CycleResult(filename=filename, mode="client_ocr", png_b64=to_base64_png(raster.pil), needs_client_ocr=True)
