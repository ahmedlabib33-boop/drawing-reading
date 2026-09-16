from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import fitz
from app.boq_parser import parse_boq
from app.cir import SpecSection
from app.drawing_engine import drawing_elements_from_text
from app.engine.cycle import run_cycle
from app.integrated import build_integrated


def make_pdf(lines: list[str]) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 18
    return doc.tobytes()


def main() -> None:
    boq_pdf = make_pdf([
        "BILL OF QUANTITIES",
        "BRIDGE 7",
        "Section 1.1 - Concrete and Reinforcement",
        "Concrete footing m3 12.5",
    ])
    boq = parse_boq(boq_pdf)
    assert len(boq.all_items) == 1, boq.model_dump()
    assert boq.all_items[0].code == "03 30 00"

    drawing_pdf = make_pdf(["GENERAL ARRANGEMENT DRAWING FOR BRIDGE 7 WITH STRUCTURAL STEEL DETAILS", "SHS100X4 HANDRAIL AND ASSOCIATED SUPPORT MEMBERS", "NOTES: ALL DIMENSIONS ARE IN MILLIMETRES UNLESS NOTED OTHERWISE"])
    cycle = run_cycle("Bridge-7-test.pdf", drawing_pdf, 0)
    assert cycle.mode == "vector"
    assert "SHS100X4" in cycle.text

    elements = drawing_elements_from_text("Bridge-7-test.pdf", "SHS100X4\nHANDRAIL", page=1)
    assert elements

    specs = [SpecSection(code="03 30 00", title="Cast-in-Place Concrete", division="03")]
    integrated = build_integrated(
        boq=boq,
        specs=specs,
        contract_findings={"findings": {"time_for_completion": ["Time for Completion 15 Months"]}},
        hoarding=None,
        drawings={"Bridge-7-test.pdf": elements},
        source_files=["boq.pdf", "spec.pdf", "contract.pdf", "Bridge-7-test.pdf"],
    )
    assert integrated.coverage["total_csi_entries"] >= 2
    assert any(e.csi_code == "03 30 00" for e in integrated.entries)
    print(json.dumps({"ok": True, "boq_items": len(boq.all_items), "cycle_mode": cycle.mode, "entries": len(integrated.entries)}, indent=2))


if __name__ == "__main__":
    main()
