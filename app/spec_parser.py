from __future__ import annotations
import re
from .cir import SpecSection
from .pdf_extract import extract_text

SECTION_HEADER_RE = re.compile(r"SECTION\s+(\d{2}\s*\d{2}\s*\d{2}|\d{5,6})(?:\s*[-–]\s*)?(.{0,120})", re.I)
DIVISION_RE = re.compile(r"DIVISION\s+(\d{2})\.?\s*(.+?)$", re.I | re.M)


def _normalize_code(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 5:
        digits += "0"
    if len(digits) == 6:
        return f"{digits[0:2]} {digits[2:4]} {digits[4:6]}"
    return raw.strip()


def parse_specs(pdf_bytes: bytes) -> list[SpecSection]:
    lines = extract_text(pdf_bytes)["full_text"].splitlines()
    sections: list[SpecSection] = []
    seen: set[str] = set()
    current_division = ""
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        dm = DIVISION_RE.search(line)
        if dm:
            current_division = dm.group(1)
            continue
        sm = SECTION_HEADER_RE.search(line)
        if not sm:
            continue
        code = _normalize_code(sm.group(1))
        title = (sm.group(2) or "").strip()
        if not title and i + 1 < len(lines):
            title = lines[i + 1].strip()[:100]
        if code in seen:
            continue
        seen.add(code)
        body = "\n".join(lines[i + 1:i + 30])
        sections.append(SpecSection(code=code, title=title or "Untitled", division=current_division or code[:2], body=body[:1500]))
    return sections
