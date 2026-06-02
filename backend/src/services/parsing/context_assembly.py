"""Hybrid context assembly: marry deterministic text + visual page snapshots."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

from pydantic import BaseModel, ConfigDict, Field

from src.infrastructure.logging_config import get_logger
from src.services.parsing.models import (
    ContextWindow,
    DeterministicDocxResult,
    DeterministicExcelResult,
    ImageAnchor,
    MergedRange,
)
from src.services.parsing.visual.preprocessor import PageSnapshot

logger = get_logger(__name__)


class AssembledContext(BaseModel):
    """A single prompt-ready chunk passed to the VLM."""

    model_config = ConfigDict(extra="ignore")

    image: Optional[ImageAnchor] = None
    snapshot: Optional[PageSnapshot] = None
    window: Optional[ContextWindow] = None
    layout_tags: Dict[str, Any] = Field(default_factory=dict)
    prompt: str = ""


class HybridContextAssembler:
    """Combine deterministic windows + page snapshots into VLM prompts."""

    DEFAULT_PROMPT_HEADER = (
        "You are inspecting a document page. Use the deterministic text grid below "
        "as ground truth — do NOT contradict it. Add semantic labels, image descriptions, "
        "and any structure the grid is missing. Respond with concise JSON."
    )

    def assemble(
        self,
        deterministic: Union[DeterministicExcelResult, DeterministicDocxResult],
        snapshots: Sequence[PageSnapshot],
    ) -> List[AssembledContext]:
        if isinstance(deterministic, DeterministicExcelResult):
            return self._assemble_excel(deterministic, snapshots)
        if isinstance(deterministic, DeterministicDocxResult):
            return self._assemble_docx(deterministic, snapshots)
        return []

    def _snapshot_for_sheet(self, snapshots: Sequence[PageSnapshot], sheet: Optional[str], idx: int) -> Optional[PageSnapshot]:
        if not snapshots:
            return None
        for snap in snapshots:
            if sheet and snap.sheet_name == sheet:
                return snap
        if 0 <= idx < len(snapshots):
            return snapshots[idx]
        return snapshots[0]

    def _assemble_excel(
        self,
        deterministic: DeterministicExcelResult,
        snapshots: Sequence[PageSnapshot],
    ) -> List[AssembledContext]:
        out: List[AssembledContext] = []
        windows_by_image = {w.image_id: w for w in deterministic.context_windows if w.image_id}
        for idx, image in enumerate(deterministic.images):
            window = windows_by_image.get(image.image_id)
            snap = self._snapshot_for_sheet(snapshots, image.sheet, idx)
            tags = self._excel_layout_tags(deterministic, image, window)
            prompt = self._render_prompt(window, tags)
            out.append(
                AssembledContext(image=image, snapshot=snap, window=window, layout_tags=tags, prompt=prompt)
            )
        if not out and deterministic.cells:
            out.append(
                AssembledContext(
                    layout_tags={"summary": "no_images"},
                    prompt=self._render_prompt(None, {"summary": "no_images"}),
                )
            )
        return out

    def _excel_layout_tags(
        self,
        deterministic: DeterministicExcelResult,
        image: ImageAnchor,
        window: Optional[ContextWindow],
    ) -> Dict[str, Any]:
        bbox = image.bounding_box_estimate
        merged_in_window: List[str] = []
        hidden_in_window: Dict[str, List[int]] = {"rows": [], "cols": []}
        if bbox:
            for m in deterministic.merged_ranges:
                if m.sheet != image.sheet:
                    continue
                if self._ranges_overlap(m, bbox):
                    merged_in_window.append(m.ref)
            sheet_hidden = deterministic.hidden.get(image.sheet or "", {})
            for r in sheet_hidden.get("rows", []):
                if bbox.start_row - 4 <= r <= bbox.end_row + 4:
                    hidden_in_window["rows"].append(r)
            for c in sheet_hidden.get("cols", []):
                if bbox.start_col - 4 <= c <= bbox.end_col + 4:
                    hidden_in_window["cols"].append(c)
        return {
            "merged_ranges_in_window": merged_in_window,
            "hidden_in_window": hidden_in_window,
            "image_anchors_in_window": [image.image_id],
            "sheet": image.sheet,
        }

    def _ranges_overlap(self, merged: MergedRange, bbox) -> bool:
        return not (
            merged.end_row < bbox.start_row
            or merged.start_row > bbox.end_row
            or merged.end_col < bbox.start_col
            or merged.start_col > bbox.end_col
        )

    def _assemble_docx(
        self,
        deterministic: DeterministicDocxResult,
        snapshots: Sequence[PageSnapshot],
    ) -> List[AssembledContext]:
        out: List[AssembledContext] = []
        windows_by_image = {w.image_id: w for w in deterministic.context_windows if w.image_id}
        for idx, image in enumerate(deterministic.images):
            window = windows_by_image.get(image.image_id)
            snap = snapshots[idx] if idx < len(snapshots) else (snapshots[0] if snapshots else None)
            tags = {
                "image_anchors_in_window": [image.image_id],
                "paragraph_index": image.paragraph_index,
            }
            prompt = self._render_prompt(window, tags)
            out.append(
                AssembledContext(image=image, snapshot=snap, window=window, layout_tags=tags, prompt=prompt)
            )
        if not out and (deterministic.paragraphs or deterministic.tables):
            sample_rows = []
            for table in deterministic.tables[:1]:
                sample_rows.extend(table.rows[:2])
            heading_texts = [p.text for p in deterministic.paragraphs if p.is_heading][:3]
            tags = {"summary": "no_images", "headings": heading_texts}
            window = None
            if sample_rows:
                window = ContextWindow(anchor="overview", radius=0, rows=sample_rows)
            out.append(AssembledContext(window=window, layout_tags=tags, prompt=self._render_prompt(window, tags)))
        return out

    def _render_prompt(self, window: Optional[ContextWindow], tags: Dict[str, Any]) -> str:
        lines: List[str] = [self.DEFAULT_PROMPT_HEADER, ""]
        lines.append(f"Layout tags: {tags}")
        if window and window.rows:
            lines.append("Localized grid:")
            for row in window.rows:
                lines.append("\t".join(row))
        return "\n".join(lines)
