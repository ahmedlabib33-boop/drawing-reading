from __future__ import annotations
import re
from .cir import LineItem, BridgeBOQ, ProjectBOQ
from .csi_master import BOQ_SECTION_TO_CSI, SYMBOL_TO_CSI
from .pdf_extract import extract_text

BRIDGE_MARKERS = [("BRIDGE 7", "Bridge 7"), ("BRIDGE 8", "Bridge 8"), ("BRIDGE 9", "Bridge 9")]
SECTION_RE = re.compile(r"Section\s+(\d+\.\d+)\s*[-–]\s*(.+?)(?:\n|$)", re.I)
UNIT_PATTERNS = [
    (re.compile(r"\b(Lm|LM|lf|LF)\s+([\d,]+(?:\.\d+)?)"), "Lm"),
    (re.compile(r"\b(m3|M3|m³)\s+([\d,]+(?:\.\d+)?)"), "m³"),
    (re.compile(r"\b(m2|M2|m²)\s+([\d,]+(?:\.\d+)?)"), "m²"),
    (re.compile(r"\b(Ton|TON|ton)\s+([\d,]+(?:\.\d+)?)"), "Ton"),
    (re.compile(r"\b(No\.|Nr|nr|NO)\s+([\d,]+(?:\.\d+)?)"), "No."),
]


def _guess_csi(section: str, description: str) -> str | None:
    for key, csi in BOQ_SECTION_TO_CSI.items():
        if key.lower() in section.lower():
            return csi
    for symbol, csi in SYMBOL_TO_CSI.items():
        if symbol.lower() in description.lower():
            return csi
    return None


def _parse_qty(line: str) -> tuple[str, float] | None:
    for pattern, unit in UNIT_PATTERNS:
        match = pattern.search(line)
        if match:
            try:
                return unit, float(match.group(2).replace(",", ""))
            except ValueError:
                pass
    return None


def parse_boq(pdf_bytes: bytes) -> ProjectBOQ:
    lines = extract_text(pdf_bytes)["full_text"].splitlines()
    project = ProjectBOQ()
    current_bridge: str | None = None
    current_section = ""
    bridges: dict[str, BridgeBOQ] = {}

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        upper = line.upper()
        for marker, name in BRIDGE_MARKERS:
            if marker in upper and len(line) < 40:
                current_bridge = name
                bridges.setdefault(name, BridgeBOQ(bridge=name))
                current_section = ""
                break

        section_match = SECTION_RE.search(line)
        if section_match:
            current_section = section_match.group(2).strip()
            continue

        if len(line) < 8 or any(k in upper for k in ["CARRIED TO", "SECTION SUMMARY", "BILL SUMMARY", "BILL NO.", "PROJECT NAME", "CONTRACTOR"]):
            continue
        qty_result = _parse_qty(line)
        if not qty_result:
            continue
        unit, qty = qty_result
        csi = _guess_csi(current_section, line) or "00 00 00"
        item = LineItem(code=csi, description=line[:300], unit=unit, quantity=qty, bridge=current_bridge, section=current_section)
        if current_bridge and current_bridge in bridges:
            bridges[current_bridge].line_items.append(item)

    project.bridges = list(bridges.values())
    project.all_items = [item for bridge in project.bridges for item in bridge.line_items]

    totals: dict[str, float] = {}
    for item in project.all_items:
        totals[item.unit] = round(totals.get(item.unit, 0.0) + item.quantity, 3)
    project.totals_by_unit = totals

    by_div: dict[str, float] = {}
    for item in project.all_items:
        div = item.code[:2] if item.code else "00"
        by_div[div] = round(by_div.get(div, 0.0) + item.quantity, 3)
    project.by_division = by_div
    return project
