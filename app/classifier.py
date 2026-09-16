from __future__ import annotations

_KEYWORDS = {
    "boq": ["bill of quantities", "item description", "unit cost", "amount"],
    "spec": ["section ", "division ", "part 1 - general", "part 2 - products"],
    "contract": ["conditions of contract", "contract sum", "performance bond", "instructions to tenderers", "form of tender"],
    "hoarding": ["hoarding", "corrugated sheet", "c-channel"],
    "qc": ["quality control", "inspection request", "ncr", "material inspection"],
}


def detect_doc_type(filename: str, text: str) -> str:
    lower = filename.lower()
    if "boq" in lower:
        return "boq"
    if "spc" in lower or "spec" in lower:
        return "spec"
    if any(x in lower for x in ("contract", "itt", "poc", "ndc")):
        return "contract"
    if "hoarding" in lower:
        return "hoarding"
    if "control" in lower or "form" in lower:
        return "qc"

    sample = text[:20000].lower()
    scores = {k: sum(1 for kw in kws if kw.lower() in sample) for k, kws in _KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] >= 2 else "unknown"
