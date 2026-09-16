from __future__ import annotations
from collections import defaultdict
from .cir import ProjectBOQ
from .csi_master import CSI_DIVISIONS


def qs_report(project: ProjectBOQ) -> dict:
    by_code: dict[str, dict] = defaultdict(lambda: {"code": "", "description": "", "unit": "", "quantity": 0.0, "by_bridge": defaultdict(float)})
    for item in project.all_items:
        key = f"{item.code}|{item.unit}"
        entry = by_code[key]
        entry["code"] = item.code
        entry["description"] = item.description[:120]
        entry["unit"] = item.unit
        entry["quantity"] += item.quantity
        if item.bridge:
            entry["by_bridge"][item.bridge] += item.quantity

    by_division: dict[str, dict] = defaultdict(lambda: {"division": "", "title": "", "items": [], "subtotal_by_unit": defaultdict(float)})
    for entry in by_code.values():
        div = entry["code"][:2] if entry["code"] else "00"
        bucket = by_division[div]
        bucket["division"] = div
        bucket["title"] = CSI_DIVISIONS.get(div, "Unknown")
        bucket["items"].append({
            "code": entry["code"], "description": entry["description"], "unit": entry["unit"],
            "quantity": round(entry["quantity"], 3), "by_bridge": dict(entry["by_bridge"]),
        })
        bucket["subtotal_by_unit"][entry["unit"]] += entry["quantity"]

    report = []
    for div in sorted(by_division):
        bucket = by_division[div]
        bucket["subtotal_by_unit"] = {k: round(v, 3) for k, v in bucket["subtotal_by_unit"].items()}
        bucket["items"] = sorted(bucket["items"], key=lambda x: x["code"])
        report.append(bucket)
    return {
        "project": project.project, "package": project.package,
        "bridges_counted": [b.bridge for b in project.bridges], "total_line_items": len(project.all_items),
        "totals_by_unit": project.totals_by_unit, "by_division": report,
    }
