from __future__ import annotations
import re
from .pdf_extract import extract_text

PATTERNS = {
    "contract_sum": [r"Contract Sum[^\n]{0,120}", r"Lump Sum price[^\n]{0,120}"],
    "time_for_completion": [r"Time for Completion[^\n]{0,160}", r"\b\w+\s*\(\d+\)\s*Months?\b"],
    "performance_bond_pct": [r"Performance Bond[^\n]{0,100}?\d+\s*%"],
    "advance_payment_pct": [r"advance payment[^\n]{0,100}?\d+\s*%"],
    "retention_pct": [r"Retention[^\n]{0,100}?\d+\s*%"],
    "liquidated_damages_pct": [r"Liquidated Damages[^\n]{0,100}?\d+\s*%"],
    "tender_bond_pct": [r"Tender Bond[^\n]{0,100}?\d+\s*%"],
    "governing_law": [r"governed by[^\n]{0,100}laws? of[^\n]{0,100}"],
}


def parse_contract(pdf_bytes: bytes) -> dict:
    extraction = extract_text(pdf_bytes)
    text = extraction["full_text"]
    findings: dict[str, list[str]] = {}
    for key, patterns in PATTERNS.items():
        matches: list[str] = []
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.I):
                value = re.sub(r"\s+", " ", match.group(0)).strip()[:240]
                if value not in matches:
                    matches.append(value)
        if matches:
            findings[key] = matches[:3]
    return {"doc_type": "contract", "pages": extraction["pages"], "chars": extraction["chars"], "findings": findings}
