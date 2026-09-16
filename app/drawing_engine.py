from __future__ import annotations
import io
import re
import fitz

try:
    import ezdxf
    _HAS_EZDXF = True
except ImportError:
    ezdxf = None
    _HAS_EZDXF = False

from .cir import DrawingElement
from .csi_master import SYMBOL_TO_CSI
from .engine.cycle import run_cycle

RE_PATTERNS = [
    (re.compile(r"SHS\s*\d+\s*[X×*]\s*\d+", re.I), "05 12 00"),
    (re.compile(r"SC[-\s]?\d{1,3}", re.I), "05 12 00"),
    (re.compile(r"SS[-\s]?\d{1,3}", re.I), "05 12 00"),
    (re.compile(r"GFRC|GLASS FIBER", re.I), "03 40 00"),
    (re.compile(r"BOX[- ]DRAIN", re.I), "33 40 00"),
    (re.compile(r"SHALLOW.{0,10}DRAIN", re.I), "22 14 00"),
    (re.compile(r"HANDRAIL|PARAPET", re.I), "05 50 00"),
    (re.compile(r"(?:Ø|DIA)\s*\d{2,4}\s*mm.*?(SEWAGE|SEWER|SANITARY)", re.I), "22 13 00"),
    (re.compile(r"(?:Ø|DIA)\s*\d{2,4}\s*mm.*?(WATER|FIRE|IRRIGATION)", re.I), "22 11 00"),
]


def classify_text(text: str) -> str | None:
    up = text.upper()
    norm = re.sub(r"[\s_]+", "-", up)
    for symbol, csi in SYMBOL_TO_CSI.items():
        if symbol.upper() in up or symbol.upper() in norm:
            return csi
    for pattern, csi in RE_PATTERNS:
        if pattern.search(text):
            return csi
    return None


def drawing_elements_from_text(filename: str, text: str, page: int = 1, source: str = "client_ocr") -> list[DrawingElement]:
    sheet = re.sub(r"\.pdf$", "", filename, flags=re.I)
    out: list[DrawingElement] = []
    for idx, raw in enumerate(text.splitlines()):
        line = raw.strip()
        if len(line) < 2:
            continue
        csi = classify_text(line)
        if csi:
            out.append(DrawingElement(
                id=f"{sheet}_client_p{page}_{idx}", type="TEXT", text=line[:500], csi_code=csi,
                geometry={"type": "client_ocr_text"}, source=source, confidence=0.65, page=page, sheet=sheet,
            ))
    return out


def _extract_dxf(data: bytes) -> list[DrawingElement]:
    if not _HAS_EZDXF:
        return []
    try:
        doc = ezdxf.read(io.StringIO(data.decode("utf-8", errors="ignore")))
        msp = doc.modelspace()
    except Exception:
        return []
    out: list[DrawingElement] = []
    for entity in msp:
        try:
            kind = entity.dxftype()
            handle = entity.dxf.handle or f"e{len(out)}"
            if kind == "INSERT":
                name = (entity.dxf.name or "").upper()
                csi = classify_text(name)
                if csi:
                    out.append(DrawingElement(id=handle, type=name, text=name, csi_code=csi,
                        geometry={"type": "insert", "insert": [entity.dxf.insert.x, entity.dxf.insert.y]}, source="dxf"))
            elif kind in ("TEXT", "MTEXT"):
                txt = entity.dxf.text if kind == "TEXT" else entity.text
                csi = classify_text(txt)
                if csi:
                    insert = getattr(entity.dxf, "insert", None)
                    geom = {"type": "text"}
                    if insert is not None:
                        geom["insert"] = [insert.x, insert.y]
                    out.append(DrawingElement(id=handle, type="TEXT", text=txt[:500], csi_code=csi, geometry=geom, source="dxf"))
        except Exception:
            continue
    return out


def _extract_pdf(data: bytes, filename: str) -> tuple[list[DrawingElement], list[int]]:
    sheet = re.sub(r"\.pdf$", "", filename, flags=re.I)
    out: list[DrawingElement] = []
    client_ocr_pages: list[int] = []
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception:
        return out, client_ocr_pages

    for pno, page in enumerate(doc):
        page_hits = 0
        try:
            blocks = page.get_text("dict").get("blocks", [])
        except Exception:
            blocks = []
        for block in blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    txt = (span.get("text") or "").strip()
                    if len(txt) < 2 or (txt.isdigit() and len(txt) <= 2):
                        continue
                    csi = classify_text(txt)
                    if csi:
                        out.append(DrawingElement(id=f"{sheet}_p{pno+1}_{len(out)}", type="TEXT", text=txt[:500], csi_code=csi,
                            geometry={"type": "bbox", "coords": list(span.get("bbox", []))}, source="pdf_text", page=pno + 1, sheet=sheet))
                        page_hits += 1
        if page_hits == 0:
            try:
                cycle = run_cycle(filename, data, page_index=pno)
            except Exception:
                continue
            if cycle.needs_client_ocr:
                client_ocr_pages.append(pno + 1)
            else:
                for line in cycle.text.splitlines():
                    csi = classify_text(line)
                    if csi:
                        out.append(DrawingElement(id=f"{sheet}_cyc_p{pno+1}_{len(out)}", type="TEXT", text=line[:500], csi_code=csi,
                            geometry={"type": "svg_ocr"}, source=f"cycle_{cycle.mode}", page=pno + 1, sheet=sheet, confidence=0.7))
    return out, client_ocr_pages


def extract_drawing(filename: str, data: bytes) -> tuple[list[DrawingElement], list[int]]:
    lower = filename.lower()
    if lower.endswith(".dxf"):
        return _extract_dxf(data), []
    if lower.endswith(".pdf"):
        return _extract_pdf(data, filename)
    return [], []
