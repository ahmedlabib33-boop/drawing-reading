"""FastAPI application for the unified Construction Drawing AI converter."""
from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Any

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .boq_parser import parse_boq
from .cir import BridgeBOQ, DrawingElement, ProjectBOQ, SpecSection
from .classifier import detect_doc_type
from .contract_parser import parse_contract
from .drawing_engine import drawing_elements_from_text, extract_drawing
from .engine import run_cycle
from .hoarding_parser import parse_hoarding
from .integrated import build_integrated
from .pdf_extract import extract_text
from .qto import qs_report
from .spec_parser import parse_specs

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", "50000000"))

app = FastAPI(title="Construction Drawing AI", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Accumulator:
    """Best-effort process-local accumulator for local/Docker use.

    It is intentionally not the primary frontend state mechanism because
    serverless providers may replace the process between requests.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.boq: ProjectBOQ | None = None
        self.specs: list[SpecSection] = []
        self.contract: dict | None = None
        self.hoarding: dict | None = None
        self.drawings: dict[str, list[DrawingElement]] = {}
        self.files: list[str] = []

    def integrated(self):
        return build_integrated(
            boq=self.boq,
            specs=self.specs,
            contract_findings=self.contract,
            hoarding=self.hoarding,
            drawings=self.drawings,
            source_files=self.files,
        )


ACC = Accumulator()


def _validate_file(name: str, data: bytes) -> None:
    if not data:
        raise HTTPException(400, "empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"file exceeds configured limit of {MAX_UPLOAD_BYTES} bytes")
    if not name:
        raise HTTPException(400, "missing filename")


def _count_csi(elements: list[DrawingElement]) -> dict[str, int]:
    hits: dict[str, int] = {}
    for el in elements:
        if el.csi_code:
            hits[el.csi_code] = hits.get(el.csi_code, 0) + 1
    return hits


def _parse_bytes(name: str, data: bytes) -> dict[str, Any]:
    lower = name.lower()
    if lower.endswith(".dxf"):
        elements, client_pages = extract_drawing(name, data)
        return {
            "filename": name,
            "doc_type": "drawing",
            "format": "dxf",
            "payload": {"elements": [e.model_dump(mode="json") for e in elements]},
            "summary": {"elements": len(elements), "csi_hits": _count_csi(elements)},
            "client_ocr_pages": client_pages,
        }

    if not lower.endswith(".pdf"):
        raise HTTPException(415, f"unsupported file type: {name}")

    extraction = extract_text(data)
    doc_type = detect_doc_type(name, extraction["full_text"])

    if doc_type == "boq":
        boq = parse_boq(data)
        return {
            "filename": name,
            "doc_type": "boq",
            "payload": boq.model_dump(mode="json"),
            "summary": {
                "bridges": [b.bridge for b in boq.bridges],
                "line_items": len(boq.all_items),
                "totals_by_unit": boq.totals_by_unit,
            },
            "client_ocr_pages": [],
        }
    if doc_type == "spec":
        sections = parse_specs(data)
        return {
            "filename": name,
            "doc_type": "spec",
            "payload": [s.model_dump(mode="json") for s in sections],
            "summary": {"sections_found": len(sections)},
            "client_ocr_pages": [],
        }
    if doc_type == "contract":
        contract = parse_contract(data)
        return {
            "filename": name,
            "doc_type": "contract",
            "payload": contract,
            "summary": {"terms_found": list(contract.get("findings", {}).keys())},
            "client_ocr_pages": [],
        }
    if doc_type == "hoarding":
        hoarding = parse_hoarding(data)
        return {
            "filename": name,
            "doc_type": "hoarding",
            "payload": hoarding,
            "summary": {"spec_extracted": True},
            "client_ocr_pages": [],
        }

    elements, client_pages = extract_drawing(name, data)
    return {
        "filename": name,
        "doc_type": "drawing" if elements or client_pages else "unknown",
        "format": "pdf",
        "payload": {"elements": [e.model_dump(mode="json") for e in elements]},
        "summary": {
            "elements": len(elements),
            "csi_hits": _count_csi(elements),
            "pages": extraction["pages"],
            "chars": extraction["chars"],
        },
        "client_ocr_pages": client_pages,
    }


def _combine_boq(payloads: list[dict]) -> ProjectBOQ | None:
    if not payloads:
        return None
    projects = [ProjectBOQ.model_validate(p) for p in payloads]
    if len(projects) == 1:
        return projects[0]
    merged = ProjectBOQ(project=projects[0].project, package=projects[0].package)
    bridge_map: dict[str, BridgeBOQ] = {}
    for project in projects:
        for bridge in project.bridges:
            target = bridge_map.setdefault(bridge.bridge, BridgeBOQ(bridge=bridge.bridge))
            target.line_items.extend(bridge.line_items)
        merged.all_items.extend(project.all_items)
    merged.bridges = list(bridge_map.values())
    totals: dict[str, float] = defaultdict(float)
    by_div: dict[str, float] = defaultdict(float)
    for item in merged.all_items:
        totals[item.unit] += item.quantity
        by_div[item.code[:2] if item.code else "00"] += item.quantity
    merged.totals_by_unit = {k: round(v, 3) for k, v in totals.items()}
    merged.by_division = {k: round(v, 3) for k, v in by_div.items()}
    return merged


def _combine_contracts(payloads: list[dict]) -> dict | None:
    if not payloads:
        return None
    findings: dict[str, list[str]] = defaultdict(list)
    pages = 0
    chars = 0
    for payload in payloads:
        pages += int(payload.get("pages", 0) or 0)
        chars += int(payload.get("chars", 0) or 0)
        for key, values in payload.get("findings", {}).items():
            for value in values:
                if value not in findings[key]:
                    findings[key].append(value)
    return {"doc_type": "contract", "pages": pages, "chars": chars, "findings": dict(findings)}


def _build_from_slices(slices: list[dict]) -> tuple[Any, ProjectBOQ | None]:
    boq_payloads: list[dict] = []
    specs: list[SpecSection] = []
    contract_payloads: list[dict] = []
    hoarding: dict | None = None
    drawings: dict[str, list[DrawingElement]] = defaultdict(list)
    source_files: list[str] = []

    for item in slices:
        filename = str(item.get("filename") or "unknown")
        doc_type = item.get("doc_type")
        payload = item.get("payload")
        source_files.append(filename)
        if doc_type == "boq" and isinstance(payload, dict):
            boq_payloads.append(payload)
        elif doc_type == "spec" and isinstance(payload, list):
            specs.extend(SpecSection.model_validate(x) for x in payload)
        elif doc_type == "contract" and isinstance(payload, dict):
            contract_payloads.append(payload)
        elif doc_type == "hoarding" and isinstance(payload, dict):
            hoarding = payload
        elif doc_type == "drawing" and isinstance(payload, dict):
            drawings[filename].extend(DrawingElement.model_validate(x) for x in payload.get("elements", []))

    boq = _combine_boq(boq_payloads)
    contract = _combine_contracts(contract_payloads)
    integrated = build_integrated(
        boq=boq,
        specs=specs,
        contract_findings=contract,
        hoarding=hoarding,
        drawings=dict(drawings),
        source_files=source_files,
    )
    return integrated, boq


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "version": app.version,
        "state_model": "stateless parse/merge supported; process-local accumulator retained for compatibility",
        "accumulated": {
            "boq": ACC.boq is not None,
            "specs": len(ACC.specs),
            "contract": ACC.contract is not None,
            "hoarding": ACC.hoarding is not None,
            "drawings": len(ACC.drawings),
            "files": len(ACC.files),
        },
    }


@app.post("/api/parse")
async def parse_file(file: UploadFile = File(...)):
    data = await file.read()
    name = file.filename or "upload"
    _validate_file(name, data)
    try:
        return JSONResponse(_parse_bytes(name, data))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"parse error: {type(exc).__name__}: {exc}") from exc


@app.post("/api/merge")
def merge_slices(body: dict = Body(...)):
    slices = body.get("slices")
    if not isinstance(slices, list) or not slices:
        raise HTTPException(400, "body.slices must be a non-empty list")
    try:
        integrated, _ = _build_from_slices(slices)
        return JSONResponse(json.loads(integrated.model_dump_json()))
    except Exception as exc:
        raise HTTPException(400, f"merge error: {type(exc).__name__}: {exc}") from exc


@app.post("/api/classify-text")
def classify_ocr_text(body: dict = Body(...)):
    filename = str(body.get("filename") or "drawing.pdf")
    text = str(body.get("text") or "")
    page = int(body.get("page") or 1)
    if not text.strip():
        return {"elements": [], "csi_hits": {}}
    elements = drawing_elements_from_text(filename, text, page=page, source="client_ocr")
    return {"elements": [e.model_dump(mode="json") for e in elements], "csi_hits": _count_csi(elements)}


@app.post("/api/integrate")
async def integrate(file: UploadFile = File(...)):
    """Compatibility endpoint using process-local memory.

    Prefer /api/parse + /api/merge on serverless deployments.
    """
    data = await file.read()
    name = file.filename or "upload"
    _validate_file(name, data)
    parsed = _parse_bytes(name, data)
    payload = parsed["payload"]
    doc_type = parsed["doc_type"]
    if doc_type == "boq":
        ACC.boq = ProjectBOQ.model_validate(payload)
    elif doc_type == "spec":
        ACC.specs.extend(SpecSection.model_validate(x) for x in payload)
    elif doc_type == "contract":
        ACC.contract = payload
    elif doc_type == "hoarding":
        ACC.hoarding = payload
    elif doc_type == "drawing":
        ACC.drawings[name] = [DrawingElement.model_validate(x) for x in payload.get("elements", [])]
    ACC.files.append(name)
    response = {"filename": name, "doc_type": doc_type, **parsed.get("summary", {})}
    if parsed.get("client_ocr_pages"):
        response["client_ocr_pages"] = parsed["client_ocr_pages"]
    return JSONResponse(response)


@app.get("/api/integrated")
def integrated():
    if not ACC.files:
        raise HTTPException(404, "no files uploaded to process-local accumulator")
    return JSONResponse(json.loads(ACC.integrated().model_dump_json()))


@app.get("/api/integrated/csi/{csi_code:path}")
def get_csi(csi_code: str):
    result = ACC.integrated()
    matches = [e for e in result.entries if e.csi_code == csi_code]
    if not matches:
        raise HTTPException(404, f"CSI {csi_code} not found")
    return JSONResponse([m.model_dump(mode="json") for m in matches])


@app.get("/api/integrated/bridge/{bridge}")
def get_bridge(bridge: str):
    matches = [e for e in ACC.integrated().entries if e.bridge and e.bridge.lower() == bridge.lower()]
    return JSONResponse({"bridge": bridge, "entry_count": len(matches), "entries": [m.model_dump(mode="json") for m in matches]})


@app.get("/api/integrated/conflicts")
def get_conflicts():
    conflicts = [
        {"csi_code": e.csi_code, "bridge": e.bridge, "conflicts": e.conflicts}
        for e in ACC.integrated().entries if e.conflicts
    ]
    return JSONResponse({"count": len(conflicts), "conflicts": conflicts})


@app.get("/api/report")
def report():
    if ACC.boq is None:
        raise HTTPException(404, "no BOQ uploaded to process-local accumulator")
    return JSONResponse(qs_report(ACC.boq))


@app.post("/api/report/from-slices")
def report_from_slices(body: dict = Body(...)):
    slices = body.get("slices")
    if not isinstance(slices, list) or not slices:
        raise HTTPException(400, "body.slices must be a non-empty list")
    _, boq = _build_from_slices(slices)
    if boq is None:
        raise HTTPException(404, "no BOQ slice provided")
    return JSONResponse(qs_report(boq))


@app.post("/api/cycle/run")
async def cycle_run(file: UploadFile = File(...), page: int = 0):
    data = await file.read()
    name = file.filename or "upload.pdf"
    _validate_file(name, data)
    try:
        result = run_cycle(name, data, page_index=page)
    except IndexError as exc:
        raise HTTPException(400, str(exc)) from exc
    return JSONResponse({
        "filename": result.filename,
        "mode": result.mode,
        "char_count": result.char_count,
        "text": result.text,
        "needs_client_ocr": result.needs_client_ocr,
        "png_b64": result.png_b64 if result.needs_client_ocr else None,
    })


@app.post("/api/cycle/text", response_class=PlainTextResponse)
async def cycle_text(file: UploadFile = File(...), page: int = 0):
    data = await file.read()
    name = file.filename or "upload.pdf"
    _validate_file(name, data)
    return run_cycle(name, data, page_index=page).text


@app.post("/api/reset")
def reset():
    ACC.reset()
    return {"ok": True}


# Local/Docker convenience. Vercel serves public/ with vercel.json instead.
_PUBLIC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "public"))
if os.path.isdir(_PUBLIC):
    app.mount("/", StaticFiles(directory=_PUBLIC, html=True), name="static")
