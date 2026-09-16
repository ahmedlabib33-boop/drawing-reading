from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class LineItem(BaseModel):
    code: str
    description: str
    unit: str
    quantity: float
    unit_cost: Optional[float] = None
    amount: Optional[float] = None
    division: Optional[str] = None
    bridge: Optional[str] = None
    section: Optional[str] = None


class SpecSection(BaseModel):
    code: str
    title: str
    division: str
    body: str = ""


class BridgeBOQ(BaseModel):
    bridge: str
    line_items: list[LineItem] = Field(default_factory=list)
    totals_by_unit: dict[str, float] = Field(default_factory=dict)


class ProjectBOQ(BaseModel):
    project: str = "Marassi Red Sea Bridges"
    package: str = "PK#18"
    bridges: list[BridgeBOQ] = Field(default_factory=list)
    all_items: list[LineItem] = Field(default_factory=list)
    totals_by_unit: dict[str, float] = Field(default_factory=dict)
    by_division: dict[str, float] = Field(default_factory=dict)


class DrawingElement(BaseModel):
    id: str
    type: str
    text: str = ""
    csi_code: Optional[str] = None
    geometry: dict[str, Any] = Field(default_factory=dict)
    source: str = "pdf_text"
    confidence: float = 1.0
    page: int = 1
    sheet: Optional[str] = None


class IntegratedCSIEntry(BaseModel):
    csi_code: str
    csi_title: str = ""
    division: str = ""
    bridge: Optional[str] = None
    spec_sections: list[dict] = Field(default_factory=list)
    boq_items: list[dict] = Field(default_factory=list)
    boq_total_quantity: float = 0.0
    boq_unit: Optional[str] = None
    contract_references: list[dict] = Field(default_factory=list)
    drawing_elements: list[dict] = Field(default_factory=list)
    drawing_sheets: list[str] = Field(default_factory=list)
    drawing_count: int = 0
    conflicts: list[str] = Field(default_factory=list)
    completeness: dict[str, bool] = Field(default_factory=dict)


class IntegratedProject(BaseModel):
    project: str = "Marassi Red Sea Bridges"
    package: str = "PK#18"
    source_files: list[str] = Field(default_factory=list)
    total_files: int = 0
    entries: list[IntegratedCSIEntry] = Field(default_factory=list)
    by_division: dict[str, list[str]] = Field(default_factory=dict)
    by_bridge: dict[str, list[str]] = Field(default_factory=dict)
    totals_by_unit: dict[str, float] = Field(default_factory=dict)
    coverage: dict[str, int] = Field(default_factory=dict)
    cycle_stats: dict[str, int] = Field(default_factory=dict)
