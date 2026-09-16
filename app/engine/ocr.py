from __future__ import annotations
import base64
import io
from dataclasses import dataclass
from PIL import Image

try:
    import pytesseract
    _HAS_TESS = True
except ImportError:
    pytesseract = None
    _HAS_TESS = False


@dataclass
class OCRWord:
    text: str
    x: float
    y: float
    w: float
    h: float
    conf: float


def ocr_image(pil_img: Image.Image, psm: int = 6) -> list[OCRWord]:
    if not _HAS_TESS:
        return []
    try:
        data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT, config=f"--psm {psm}")
    except Exception:
        return []
    words: list[OCRWord] = []
    for i in range(len(data.get("text", []))):
        txt = (data["text"][i] or "").strip()
        if not txt:
            continue
        try:
            conf = float(data["conf"][i])
        except Exception:
            conf = 0.0
        if conf < 30:
            continue
        words.append(OCRWord(text=txt, x=float(data["left"][i]), y=float(data["top"][i]), w=float(data["width"][i]), h=float(data["height"][i]), conf=conf))
    return words


def available() -> bool:
    if not _HAS_TESS:
        return False
    try:
        _ = pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def to_base64_png(pil_img: Image.Image) -> str:
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")
