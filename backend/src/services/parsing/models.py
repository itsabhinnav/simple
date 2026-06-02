"""Shared pydantic v2 models for the hybrid document parsing engine."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field


ArtifactKind = Literal["spec", "design", "requirements", "test_cases", "unknown"]


class Cell(BaseModel):
    """A single resolved cell from a deterministic parse."""

    model_config = ConfigDict(extra="ignore")

    sheet: str
    row: int
    col: int
    ref: str
    value: Optional[Any] = None
    raw_text: Optional[str] = None
    data_type: Optional[str] = None
    is_merged_origin: bool = False
    inherited_from: Optional[str] = None
    needs_evaluation: bool = False
    formula: Optional[str] = None


class MergedRange(BaseModel):
    """A merged cell range from <mergeCells>."""

    model_config = ConfigDict(extra="ignore")

    sheet: str
    ref: str
    start_row: int
    start_col: int
    end_row: int
    end_col: int


class BoundingBox(BaseModel):
    """Estimated bounding box for an image anchor in cell coordinates."""

    model_config = ConfigDict(extra="ignore")

    start_row: int
    start_col: int
    end_row: int
    end_col: int


class ImageAnchor(BaseModel):
    """A located image extracted from .xlsx or .docx."""

    model_config = ConfigDict(extra="ignore")

    image_id: str
    binary_storage_path: str
    sheet: Optional[str] = None
    anchor_cell: Optional[str] = None
    bounding_box_estimate: Optional[BoundingBox] = None
    emu_offsets: Optional[Dict[str, int]] = None
    paragraph_index: Optional[int] = None
    table_cell_ref: Optional[str] = None


class ContextWindow(BaseModel):
    """Localized text around an image anchor."""

    model_config = ConfigDict(extra="ignore")

    sheet: Optional[str] = None
    anchor: str
    image_id: Optional[str] = None
    radius: int
    rows: List[List[str]] = Field(default_factory=list)
    placeholder: Optional[str] = None
    paragraph_index: Optional[int] = None


class DeterministicExcelResult(BaseModel):
    """Result of the deterministic Excel parser."""

    model_config = ConfigDict(extra="ignore")

    sheets: List[str] = Field(default_factory=list)
    cells: List[Cell] = Field(default_factory=list)
    merged_ranges: List[MergedRange] = Field(default_factory=list)
    hidden: Dict[str, Dict[str, List[int]]] = Field(default_factory=dict)
    images: List[ImageAnchor] = Field(default_factory=list)
    context_windows: List[ContextWindow] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    dimensions: Dict[str, str] = Field(default_factory=dict)


class DocxParagraph(BaseModel):
    """A single paragraph from a docx document."""

    model_config = ConfigDict(extra="ignore")

    index: int
    text: str
    style: Optional[str] = None
    is_heading: bool = False
    heading_level: Optional[int] = None


class DocxTable(BaseModel):
    """A table from a docx document represented as a 2D cell grid."""

    model_config = ConfigDict(extra="ignore")

    index: int
    paragraph_index: Optional[int] = None
    rows: List[List[str]] = Field(default_factory=list)


class DeterministicDocxResult(BaseModel):
    """Result of the deterministic DOCX parser."""

    model_config = ConfigDict(extra="ignore")

    paragraphs: List[DocxParagraph] = Field(default_factory=list)
    tables: List[DocxTable] = Field(default_factory=list)
    images: List[ImageAnchor] = Field(default_factory=list)
    context_windows: List[ContextWindow] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ReconciliationConflict(BaseModel):
    """Recorded conflict between VLM output and deterministic ground truth."""

    model_config = ConfigDict(extra="ignore")

    coordinate: str
    deterministic_value: Any
    vlm_value: Any
    resolution: Literal["deterministic_wins"] = "deterministic_wins"
    notes: Optional[str] = None


class VLMUsage(BaseModel):
    """Token usage / cost telemetry for a VLM call."""

    model_config = ConfigDict(extra="ignore")

    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class VLMRequest(BaseModel):
    """Request envelope passed to a VLM provider."""

    model_config = ConfigDict(extra="ignore")

    image_path: str
    prompt: str
    context: Optional[str] = None
    schema_hint: Optional[Dict[str, Any]] = None
    model: Optional[str] = None
    options: Dict[str, Any] = Field(default_factory=dict)


class VLMResponse(BaseModel):
    """Normalized response from a VLM provider."""

    model_config = ConfigDict(extra="ignore")

    provider: str
    model: str
    usage: VLMUsage = Field(default_factory=VLMUsage)
    raw_text: str = ""
    parsed: Dict[str, Any] = Field(default_factory=dict)
    skipped: bool = False
    error: Optional[str] = None


class VLMError(BaseModel):
    """Error envelope (also exposed as exception subclass below)."""

    model_config = ConfigDict(extra="ignore")

    provider: str
    model: Optional[str] = None
    message: str
    cause: Optional[str] = None


class HybridParseResult(BaseModel):
    """Final aggregated result emitted to the API consumer."""

    model_config = ConfigDict(extra="ignore")

    file_type: Literal["xlsx", "docx", "unknown"]
    deterministic: Dict[str, Any] = Field(default_factory=dict)
    vlm: Dict[str, Any] = Field(default_factory=dict)
    conflicts: List[ReconciliationConflict] = Field(default_factory=list)
    structured_payload: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    artifact_kind: ArtifactKind = "unknown"


class ParseOptions(BaseModel):
    """Options accepted by the orchestrator and Celery task."""

    model_config = ConfigDict(extra="ignore")

    provider: Optional[str] = None
    enable_visual: bool = True
    enable_vlm: bool = True
    spatial_radius: Optional[int] = None
    tmp_dir: Optional[str] = None
    schema_hint: Optional[Dict[str, Any]] = None


class ParseRequest(BaseModel):
    """Request envelope used by the synchronous service entry."""

    model_config = ConfigDict(extra="ignore")

    file_path: str
    options: ParseOptions = Field(default_factory=ParseOptions)


class ParseTaskStatus(BaseModel):
    """Reported status for an async parse task."""

    model_config = ConfigDict(extra="ignore")

    task_id: str
    status: str
    progress: Optional[str] = None
    info: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    submitted_at: Optional[datetime] = None
