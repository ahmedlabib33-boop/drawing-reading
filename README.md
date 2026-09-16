# Construction Drawing AI v3.1

Unified construction document and drawing converter. Upload BOQ, specifications, contract documents, hoarding requirements and PDF/DXF drawings; the application parses them into structured slices and merges them into one CSI-keyed project JSON.

## What is wired

- PDF -> PNG rasterization
- PDF -> SVG native-vector conversion
- PNG -> OCR text + bounding boxes when Tesseract is installed
- PNG + OCR -> searchable SVG
- SVG -> text loop closure
- BOQ parser
- Specification parser
- Contract term parser
- Hoarding parser
- DXF and PDF drawing extraction
- Pattern-based CSI inference
- CSI-keyed integration
- BOQ/drawing conflict flags
- QS report
- Browser UI with JSON/CSV export
- Stateless `/api/parse` + `/api/merge` workflow for serverless deployment
- Compatibility in-memory `/api/integrate` workflow for local/Docker use

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Health and compatibility accumulator state |
| POST | `/api/parse` | Parse one PDF/DXF into a portable structured slice |
| POST | `/api/merge` | Merge structured slices into integrated CSI JSON |
| POST | `/api/classify-text` | Classify browser-OCR text into drawing CSI elements |
| POST | `/api/integrate` | Compatibility upload using process-local accumulator |
| GET | `/api/integrated` | Integrated JSON from process-local accumulator |
| GET | `/api/integrated/csi/{code}` | CSI lookup from process-local accumulator |
| GET | `/api/integrated/bridge/{name}` | Bridge lookup from process-local accumulator |
| GET | `/api/integrated/conflicts` | Conflicts from process-local accumulator |
| GET | `/api/report` | QS report from process-local BOQ |
| POST | `/api/report/from-slices` | Stateless QS report |
| POST | `/api/cycle/run` | Run one PDF page through vector/OCR cycle |
| POST | `/api/cycle/text` | Text-only cycle output |
| POST | `/api/reset` | Reset compatibility accumulator |

## Local run

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.pipeline:app --reload
```

Open `http://127.0.0.1:8000`.

## Docker / Railway / Render / Fly with server-side OCR

```bash
docker build -t construction-ai .
docker run --rm -p 8000:8000 construction-ai
```

The Docker image installs Tesseract and `requirements-ocr.txt`, enabling native server-side OCR.

## Vercel

Push the repository and import it into Vercel. `vercel.json` routes `/api/*` to FastAPI and serves `public/index.html` at `/`.

The frontend deliberately uses the stateless API: each file is parsed independently, its structured slice stays in browser memory, and `/api/merge` combines the slices. This avoids depending on the process-local `ACC` object between serverless requests.

## Honest notes

- **Vercel has no Tesseract in this package.** When a PDF page has insufficient native text, `/api/cycle/run` returns a PNG and the included frontend uses Tesseract.js in the browser. For full server-side OCR, deploy the Docker image to Railway, Render, Fly, or another container host.
- **`ACC` is in-memory.** It is retained only for backward-compatible endpoints and local/container use. The shipped frontend does **not** depend on it. If you want persistent server-side project sessions, replace it with Redis or a database.
- **CSI inference on drawings is pattern-based, not ML.** Known symbols such as `SHS100*4` can map directly, while novel symbols may be missed or require project-specific mapping updates.
- **Integration is a first pass.** Specification sections and BOQ items can use different granularity, so `has_spec` without `has_boq` can be a legitimate data condition rather than a software defect.
- **Hoarding values are project-specific seed values from the supplied specification.** If the source document changes, update the parser to extract and validate those values instead of treating the seed dictionary as authoritative.
- Provider request/response size and execution limits still apply. Large drawing sets are better suited to the Docker deployment or a persistent worker architecture.

## Deploy

```bash
git init
git add .
git commit -m "Construction AI v3.1"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

Then import the repository in Vercel, or deploy the Dockerfile to your preferred container platform.
