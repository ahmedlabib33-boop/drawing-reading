from __future__ import annotations
import fitz


def extract_text(pdf_bytes: bytes) -> dict:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        pages.append({"page": i + 1, "text": text})
    full = "\n".join(p["text"] for p in pages)
    return {
        "pages": len(doc),
        "per_page": pages,
        "full_text": full,
        "chars": sum(len(p["text"]) for p in pages),
    }
