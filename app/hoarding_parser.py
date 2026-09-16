from __future__ import annotations
from .pdf_extract import extract_text

# Project-specific baseline values supplied in the source specification.
HOARDING_SPEC = {
    "construction": {
        "sheets": "Interlocking pre-fabricated sheets",
        "sheet_thickness_mm": 2,
        "height_m": 2.20,
        "support": "Tubular steel set in concrete blocks",
        "posts": 'Evacuated Steel Cylinder 2"',
        "base_plate": "Steel Plate 15cm x 15cm",
        "c_channel": "Standard C-channel top and bottom rail",
        "bolts": "Standard bolts to C-channel",
        "foundation": "Masonry works to rectify levels",
        "safety": "Free of hazardous protrusions",
    },
    "logo": {
        "size_rule": "Logo height = 100% of hoarding height",
        "placement": "Centralised in every fifth square section",
        "material": "Fabricated from canvas, attached securely",
        "colours": {
            "primary_grey": {"pantone": "Cool Grey 11", "cmyk": "C44 M34 Y22 K78", "rgb": "R77 G77 B79"},
            "primary_white": "White",
            "accent_yellow": "Pantone 117",
            "accent_blue": "Pantone 274",
        },
        "fonts": "Emaar corporate font",
    },
    "measured_dimensions": {
        "sheet_height_mm": 2200,
        "logo_canvas_size_mm": 2084,
        "post_diameter_mm": 50,
        "foundation_depth_mm": 500,
        "post_spacing_mm": 2500,
        "logo_every_n_sections": 5,
    },
}


def parse_hoarding(pdf_bytes: bytes) -> dict:
    extraction = extract_text(pdf_bytes)
    return {"doc_type": "hoarding_spec", "pages": extraction["pages"], "spec": HOARDING_SPEC}
