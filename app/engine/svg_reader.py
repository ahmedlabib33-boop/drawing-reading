from __future__ import annotations
import re
from xml.etree import ElementTree as ET

_TEXT_RE = re.compile(r"<text[^>]*>(.*?)</text>", re.DOTALL | re.I)


def extract_text_from_svg(svg: str) -> list[str]:
    out: list[str] = []
    try:
        root = ET.fromstring(svg)
        for el in root.iter():
            if el.tag.split("}")[-1] == "text":
                txt = "".join(el.itertext()).strip()
                if txt:
                    out.append(txt)
    except Exception:
        for match in _TEXT_RE.finditer(svg):
            txt = re.sub(r"<[^>]+>", "", match.group(1)).strip()
            if txt:
                out.append(txt)
    return out
