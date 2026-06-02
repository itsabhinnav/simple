"""Pydantic request/response models for the parsing controller."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ParseSubmitResponse(BaseModel):
    """Returned after enqueuing an async parse task."""

    model_config = ConfigDict(extra="ignore")

    task_id: str
    status_url: str
    result_url: str
    submitted_at: Optional[str] = None


class ParseSyncResponse(BaseModel):
    """Returned for synchronous parses."""

    model_config = ConfigDict(extra="ignore")

    file_type: str
    artifact_kind: str
    warnings: List[str] = Field(default_factory=list)
    structured_payload: Dict[str, Any] = Field(default_factory=dict)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    deterministic: Dict[str, Any] = Field(default_factory=dict)
    vlm: Dict[str, Any] = Field(default_factory=dict)


class ProviderListResponse(BaseModel):
    """Returned by GET /api/parsing/providers."""

    model_config = ConfigDict(extra="ignore")

    default: Optional[str]
    providers: List[str]


class ParseOptionsSchema(BaseModel):
    """Form/body-level options for /parse."""

    model_config = ConfigDict(extra="ignore")

    provider: Optional[str] = None
    mode: str = Field("async", pattern="^(async|sync)$")
    enable_visual: Optional[bool] = None
    enable_vlm: Optional[bool] = None
    target: Optional[str] = Field(
        default=None,
        pattern="^(specifications|requirements|design_tickets|test_cases)$",
    )


class SmartPreviewOptionsSchema(BaseModel):
    """Form/body-level options for /smart-preview."""

    model_config = ConfigDict(extra="ignore")

    target: Optional[str] = Field(
        default=None,
        pattern="^(specifications|requirements|design_tickets|test_cases|auto)$",
    )
    provider: Optional[str] = None
    sample_rows: int = Field(default=5, ge=1, le=50)
    enable_ai: bool = False
    enable_visual: bool = False
    enable_vlm: bool = False


class SmartPreviewResponse(BaseModel):
    """Returned by /smart-preview — combines deterministic + AI overlays."""

    model_config = ConfigDict(extra="ignore")

    file: str
    target: Optional[str] = None
    deterministic: Dict[str, Any] = Field(default_factory=dict)
    ai: Dict[str, Any] = Field(default_factory=dict)
    providers: Dict[str, Any] = Field(default_factory=dict)
    supported_targets: List[str] = Field(default_factory=list)
