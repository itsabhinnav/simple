"""Strict reconciliation: deterministic cell text OVERRIDES VLM text outputs."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple, Union

from src.infrastructure.logging_config import get_logger
from src.services.parsing.models import (
    DeterministicDocxResult,
    DeterministicExcelResult,
    HybridParseResult,
    ReconciliationConflict,
)

logger = get_logger(__name__)


REF_RE = re.compile(r"\b([A-Z]{1,3})(\d{1,7})\b")


_ARTIFACT_KEYWORDS = {
    "requirements": ("requirement id", "requirement", "given", "when", "then"),
    "test_cases": ("test case", "tc-", "expected result", "steps"),
    "design": ("design", "architecture", "module", "diagram"),
    "spec": ("specification", "spec id", "specification id"),
}


class StrictReconciler:
    """Reconcile deterministic + VLM outputs with deterministic-wins rule."""

    def reconcile(
        self,
        deterministic: Union[DeterministicExcelResult, DeterministicDocxResult],
        vlm_outputs: List[Dict[str, Any]],
        warnings: Optional[List[str]] = None,
    ) -> HybridParseResult:
        warnings = list(warnings or [])
        file_type = "xlsx" if isinstance(deterministic, DeterministicExcelResult) else "docx"
        det_cells = self._build_det_index(deterministic)
        conflicts, semantic = self._collect_vlm_semantics(vlm_outputs, det_cells)
        structured_payload = self._build_structured_payload(deterministic, semantic)
        artifact_kind = self._classify_artifact(deterministic)
        vlm_summary = {
            "skipped": all(out.get("skipped") for out in vlm_outputs) if vlm_outputs else True,
            "calls": vlm_outputs,
            "semantic_overlays": semantic,
        }
        deterministic_summary = self._deterministic_summary(deterministic)
        if isinstance(deterministic, DeterministicExcelResult):
            warnings.extend(deterministic.warnings)
        else:
            warnings.extend(deterministic.warnings)
        return HybridParseResult(
            file_type=file_type,
            deterministic=deterministic_summary,
            vlm=vlm_summary,
            conflicts=conflicts,
            structured_payload=structured_payload,
            warnings=warnings,
            artifact_kind=artifact_kind,
        )

    def _build_det_index(self, deterministic: Union[DeterministicExcelResult, DeterministicDocxResult]) -> Dict[str, Any]:
        index: Dict[str, Any] = {}
        if isinstance(deterministic, DeterministicExcelResult):
            for cell in deterministic.cells:
                index[f"{cell.sheet}!{cell.ref}"] = cell.value
                index[cell.ref] = cell.value
        else:
            for table_idx, table in enumerate(deterministic.tables):
                for r, row in enumerate(table.rows):
                    for c, val in enumerate(row):
                        index[f"table{table_idx}!{r},{c}"] = val
        return index

    def _collect_vlm_semantics(
        self,
        vlm_outputs: List[Dict[str, Any]],
        det_cells: Dict[str, Any],
    ) -> Tuple[List[ReconciliationConflict], List[Dict[str, Any]]]:
        conflicts: List[ReconciliationConflict] = []
        semantic_overlays: List[Dict[str, Any]] = []
        for out in vlm_outputs:
            if out.get("skipped"):
                continue
            parsed = out.get("parsed") or {}
            text_blob = out.get("raw_text", "")
            cell_claims = parsed.get("cells", {}) if isinstance(parsed, dict) else {}
            for ref, value in cell_claims.items() if isinstance(cell_claims, dict) else []:
                det_value = det_cells.get(ref)
                if det_value is None or det_value == "":
                    continue
                if self._values_differ(det_value, value):
                    conflicts.append(
                        ReconciliationConflict(
                            coordinate=str(ref),
                            deterministic_value=det_value,
                            vlm_value=value,
                            notes="cell-claim disagrees with deterministic grid",
                        )
                    )
            for match in REF_RE.finditer(text_blob):
                ref = match.group(0)
                det_value = det_cells.get(ref)
                if det_value is None:
                    continue
                start = max(0, match.start() - 30)
                end = min(len(text_blob), match.end() + 30)
                snippet = text_blob[start:end]
                if str(det_value) in snippet:
                    continue
                conflicts.append(
                    ReconciliationConflict(
                        coordinate=ref,
                        deterministic_value=det_value,
                        vlm_value=snippet,
                        notes="ref mentioned in VLM text without matching deterministic value",
                    )
                )
            semantic_overlays.append(
                {
                    "provider": out.get("provider"),
                    "model": out.get("model"),
                    "labels": parsed.get("labels", []) if isinstance(parsed, dict) else [],
                    "image_descriptions": parsed.get("image_descriptions", []) if isinstance(parsed, dict) else [],
                    "inferred_table_boundaries": parsed.get("inferred_table_boundaries", [])
                    if isinstance(parsed, dict)
                    else [],
                    "semantic_context": parsed.get("semantic_context") if isinstance(parsed, dict) else None,
                    "raw_text": text_blob,
                }
            )
        return conflicts, semantic_overlays

    def _values_differ(self, det_value: Any, vlm_value: Any) -> bool:
        if det_value is None and vlm_value is None:
            return False
        if det_value is None or vlm_value is None:
            return True
        return str(det_value).strip() != str(vlm_value).strip()

    def _build_structured_payload(
        self,
        deterministic: Union[DeterministicExcelResult, DeterministicDocxResult],
        semantic_overlays: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"semantics": semantic_overlays}
        if isinstance(deterministic, DeterministicExcelResult):
            sheets_payload: Dict[str, Any] = {}
            for sheet in deterministic.sheets:
                cells = [c for c in deterministic.cells if c.sheet == sheet]
                sheets_payload[sheet] = {
                    "cells": [
                        {"ref": c.ref, "value": c.value, "inherited_from": c.inherited_from}
                        for c in cells
                        if c.value is not None
                    ],
                    "merged_ranges": [
                        m.ref for m in deterministic.merged_ranges if m.sheet == sheet
                    ],
                    "hidden": deterministic.hidden.get(sheet, {}),
                    "images": [
                        {
                            "image_id": img.image_id,
                            "anchor_cell": img.anchor_cell,
                            "bounding_box_estimate": img.bounding_box_estimate.model_dump()
                            if img.bounding_box_estimate
                            else None,
                        }
                        for img in deterministic.images
                        if img.sheet == sheet
                    ],
                }
            payload["sheets"] = sheets_payload
        else:
            payload["paragraphs"] = [
                {"index": p.index, "text": p.text, "is_heading": p.is_heading}
                for p in deterministic.paragraphs
            ]
            payload["tables"] = [
                {"index": t.index, "rows": t.rows} for t in deterministic.tables
            ]
            payload["images"] = [
                {"image_id": img.image_id, "paragraph_index": img.paragraph_index}
                for img in deterministic.images
            ]
        return payload

    def _deterministic_summary(
        self, deterministic: Union[DeterministicExcelResult, DeterministicDocxResult]
    ) -> Dict[str, Any]:
        if isinstance(deterministic, DeterministicExcelResult):
            return {
                "sheets": deterministic.sheets,
                "cell_count": len(deterministic.cells),
                "merged_count": len(deterministic.merged_ranges),
                "image_count": len(deterministic.images),
                "context_windows": len(deterministic.context_windows),
                "dimensions": deterministic.dimensions,
                "hidden": deterministic.hidden,
            }
        return {
            "paragraphs": len(deterministic.paragraphs),
            "tables": len(deterministic.tables),
            "image_count": len(deterministic.images),
            "context_windows": len(deterministic.context_windows),
        }

    def _classify_artifact(
        self, deterministic: Union[DeterministicExcelResult, DeterministicDocxResult]
    ) -> str:
        haystack: List[str] = []
        if isinstance(deterministic, DeterministicExcelResult):
            haystack.extend(s.lower() for s in deterministic.sheets)
            for cell in deterministic.cells[:200]:
                if cell.value is not None and isinstance(cell.value, str):
                    haystack.append(cell.value.lower())
        else:
            for p in deterministic.paragraphs[:50]:
                haystack.append(p.text.lower())
            for t in deterministic.tables[:5]:
                for row in t.rows[:3]:
                    haystack.extend(c.lower() for c in row)
        flat = " ".join(haystack)
        for kind, kws in _ARTIFACT_KEYWORDS.items():
            for kw in kws:
                if kw in flat:
                    return kind
        return "unknown"
