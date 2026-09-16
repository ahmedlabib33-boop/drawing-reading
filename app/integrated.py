from __future__ import annotations
from collections import defaultdict
from .cir import IntegratedProject, IntegratedCSIEntry, ProjectBOQ, SpecSection, DrawingElement
from .csi_master import CSI_DIVISIONS


def _bridge_from_sheet(sheet: str) -> str | None:
    upper = sheet.upper()
    if any(token in upper for token in ("BRIDGE-7", "BRIDGE 7", "AR-004", "AR-005", "AR-008")):
        return "Bridge 7"
    if "BRIDGE-8" in upper or "BRIDGE 8" in upper:
        return "Bridge 8"
    if "BRIDGE-9" in upper or "BRIDGE 9" in upper:
        return "Bridge 9"
    return None


def build_integrated(boq: ProjectBOQ | None, specs: list[SpecSection] | None, contract_findings: dict | None,
                     hoarding: dict | None, drawings: dict[str, list[DrawingElement]] | None,
                     source_files: list[str]) -> IntegratedProject:
    specs = specs or []
    drawings = drawings or {}
    buckets: dict[tuple[str, str | None], dict] = defaultdict(lambda: {
        "spec_sections": [], "boq_items": [], "contract_references": [], "drawing_elements": [], "drawing_sheets": set()
    })

    for spec in specs:
        if spec.code and spec.code != "00 00 00":
            buckets[(spec.code, None)]["spec_sections"].append({
                "code": spec.code, "title": spec.title, "division": spec.division, "body_preview": spec.body[:500]
            })

    boq_totals: dict[str, float] = {}
    if boq:
        for item in boq.all_items:
            if not item.code or item.code == "00 00 00":
                continue
            buckets[(item.code, item.bridge)]["boq_items"].append(item.model_dump())
            boq_totals[item.unit] = boq_totals.get(item.unit, 0.0) + item.quantity

    if contract_findings:
        for term_key, matches in contract_findings.get("findings", {}).items():
            for match in matches[:2]:
                buckets[("01 00 00", None)]["contract_references"].append({"term": term_key, "excerpt": match})

    if hoarding:
        buckets[("10 00 00", None)]["contract_references"].append({
            "term": "hoarding_spec", "excerpt": str(hoarding.get("spec", {}).get("measured_dimensions", {}))[:400]
        })

    for sheet, elements in drawings.items():
        for el in elements:
            if not el.csi_code:
                continue
            bridge = _bridge_from_sheet(sheet)
            key = (el.csi_code, bridge)
            buckets[key]["drawing_elements"].append(el.model_dump(mode="json"))
            buckets[key]["drawing_sheets"].add(sheet)

    entries: list[IntegratedCSIEntry] = []
    by_division: dict[str, list[str]] = defaultdict(list)
    by_bridge: dict[str, list[str]] = defaultdict(list)
    cycle_stats = {"cycle_sourced_elements": 0, "client_ocr_sourced_elements": 0}

    for (csi, bridge), bucket in sorted(buckets.items(), key=lambda item: (item[0][0], item[0][1] or "")):
        div = csi[:2]
        boq_items = bucket["boq_items"]
        units = sorted({item["unit"] for item in boq_items if item.get("unit")})
        boq_total = sum(float(item.get("quantity", 0)) for item in boq_items)
        conflicts: list[str] = []
        if bucket["drawing_elements"] and not boq_items:
            conflicts.append(f"Drawing has {len(bucket['drawing_elements'])} classified elements but no BOQ items at this CSI/bridge key")
        if boq_items and not bucket["drawing_elements"]:
            conflicts.append("BOQ item present but no classified drawing evidence at this CSI/bridge key")
        if len(units) > 1:
            conflicts.append(f"Multiple BOQ units share this CSI key: {', '.join(units)}")
        completeness = {
            "has_spec": bool(bucket["spec_sections"]), "has_boq": bool(boq_items),
            "has_drawing": bool(bucket["drawing_elements"]), "has_contract": bool(bucket["contract_references"]),
        }
        for element in bucket["drawing_elements"]:
            source = element.get("source") or ""
            if source.startswith("cycle_"):
                cycle_stats["cycle_sourced_elements"] += 1
            if source.startswith("client_ocr"):
                cycle_stats["client_ocr_sourced_elements"] += 1

        entry = IntegratedCSIEntry(
            csi_code=csi, csi_title=CSI_DIVISIONS.get(div, "Unknown"), division=div, bridge=bridge,
            spec_sections=bucket["spec_sections"], boq_items=boq_items, boq_total_quantity=round(boq_total, 3),
            boq_unit=units[0] if len(units) == 1 else None, contract_references=bucket["contract_references"],
            drawing_elements=bucket["drawing_elements"][:500], drawing_sheets=sorted(bucket["drawing_sheets"]),
            drawing_count=len(bucket["drawing_elements"]), conflicts=conflicts, completeness=completeness,
        )
        entries.append(entry)
        by_division[div].append(csi)
        if bridge:
            by_bridge[bridge].append(csi)

    coverage = {
        "total_csi_entries": len(entries),
        "with_spec": sum(1 for e in entries if e.completeness["has_spec"]),
        "with_boq": sum(1 for e in entries if e.completeness["has_boq"]),
        "with_drawing": sum(1 for e in entries if e.completeness["has_drawing"]),
        "with_contract": sum(1 for e in entries if e.completeness["has_contract"]),
        "fully_integrated": sum(1 for e in entries if e.completeness["has_spec"] and e.completeness["has_boq"] and e.completeness["has_drawing"]),
        "conflicts_found": sum(len(e.conflicts) for e in entries),
    }
    return IntegratedProject(
        source_files=source_files, total_files=len(source_files), entries=entries,
        by_division={k: sorted(set(v)) for k, v in by_division.items()},
        by_bridge={k: sorted(set(v)) for k, v in by_bridge.items()},
        totals_by_unit={k: round(v, 3) for k, v in boq_totals.items()}, coverage=coverage, cycle_stats=cycle_stats,
    )
