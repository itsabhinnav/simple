"""Deterministic .docx parser via python-docx (convenience) + zipfile/lxml (image fidelity)."""

from __future__ import annotations

import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import docx as docx_lib
from docx.document import Document as DocxDocument
from lxml import etree

from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.logging_config import get_logger
from src.services.parsing.models import (
    ContextWindow,
    DeterministicDocxResult,
    DocxParagraph,
    DocxTable,
    ImageAnchor,
)

logger = get_logger(__name__)


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


class DocxDeterministicParser:
    """Deterministic .docx parser following the documented architecture."""

    def __init__(self, tmp_dir: Optional[str] = None, spatial_radius: int = 2) -> None:
        cm = get_config_manager()
        self._tmp_dir = Path(tmp_dir or cm.get_config("parsing.tmp_dir", "data/tmp/parsing"))
        self._spatial_radius = spatial_radius

    def parse(self, path: Path) -> DeterministicDocxResult:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"docx not found: {path}")
        self._tmp_dir.mkdir(parents=True, exist_ok=True)
        warnings: List[str] = []

        paragraphs, tables = self._parse_body_with_docx(path, warnings)

        with zipfile.ZipFile(path, "r") as zf:
            images = self._parse_images(zf, path.stem, warnings)

        context_windows = self._build_context_windows(paragraphs, images, radius=self._spatial_radius)

        return DeterministicDocxResult(
            paragraphs=paragraphs,
            tables=tables,
            images=images,
            context_windows=context_windows,
            warnings=warnings,
        )

    def _parse_body_with_docx(self, path: Path, warnings: List[str]) -> Tuple[List[DocxParagraph], List[DocxTable]]:
        try:
            document: DocxDocument = docx_lib.Document(str(path))
        except Exception as exc:  # noqa: BLE001 - we want to surface but not crash
            warnings.append(f"python-docx open failed: {exc}")
            return [], []

        paragraphs: List[DocxParagraph] = []
        tables: List[DocxTable] = []
        para_index = 0
        table_index = 0

        body = document.element.body
        for child in body.iterchildren():
            tag = _local(child.tag)
            if tag == "p":
                style_name = None
                is_heading = False
                heading_level: Optional[int] = None
                text_parts: List[str] = []
                for el in child.iter():
                    el_tag = _local(el.tag)
                    if el_tag == "pStyle":
                        val = el.get(f"{{{NS['w']}}}val") or ""
                        style_name = val
                        if val.lower().startswith("heading"):
                            is_heading = True
                            try:
                                heading_level = int(val.replace("Heading", "").strip() or "1")
                            except ValueError:
                                heading_level = 1
                    elif el_tag == "t":
                        text_parts.append(el.text or "")
                paragraphs.append(
                    DocxParagraph(
                        index=para_index,
                        text="".join(text_parts),
                        style=style_name,
                        is_heading=is_heading,
                        heading_level=heading_level,
                    )
                )
                para_index += 1
            elif tag == "tbl":
                rows: List[List[str]] = []
                for row_el in child.findall("w:tr", NS):
                    row: List[str] = []
                    for cell_el in row_el.findall("w:tc", NS):
                        cell_text = []
                        for t_el in cell_el.iter():
                            if _local(t_el.tag) == "t":
                                cell_text.append(t_el.text or "")
                        row.append("".join(cell_text))
                    rows.append(row)
                tables.append(
                    DocxTable(index=table_index, paragraph_index=para_index, rows=rows)
                )
                table_index += 1

        return paragraphs, tables

    def _parse_images(self, zf: zipfile.ZipFile, file_stem: str, warnings: List[str]) -> List[ImageAnchor]:
        document_path = "word/document.xml"
        if document_path not in zf.namelist():
            warnings.append("word/document.xml missing")
            return []
        try:
            root = etree.fromstring(zf.read(document_path))
        except etree.XMLSyntaxError as exc:
            warnings.append(f"document.xml parse error: {exc}")
            return []

        rels = self._read_rels(zf, "word/_rels/document.xml.rels")
        anchors: List[ImageAnchor] = []
        body = root.find("w:body", NS)
        if body is None:
            return []
        para_index = -1
        for child in body.iterchildren():
            tag = _local(child.tag)
            if tag == "p":
                para_index += 1
                for blip in child.iter():
                    if _local(blip.tag) != "blip":
                        continue
                    embed = blip.get(f"{{{NS['r']}}}embed")
                    if not embed:
                        continue
                    target = rels.get(embed)
                    if not target:
                        warnings.append(f"para {para_index}: unresolved image rel {embed}")
                        continue
                    media_path = self._resolve_media(target)
                    if media_path not in zf.namelist():
                        warnings.append(f"para {para_index}: media missing {media_path}")
                        continue
                    image_id = f"{file_stem}_p{para_index}_{uuid.uuid4().hex[:8]}"
                    suffix = Path(media_path).suffix or ".bin"
                    binary_target = self._tmp_dir / f"{image_id}{suffix}"
                    try:
                        binary_target.write_bytes(zf.read(media_path))
                    except OSError as exc:
                        warnings.append(f"could not write image {binary_target}: {exc}")
                        continue
                    anchors.append(
                        ImageAnchor(
                            image_id=image_id,
                            binary_storage_path=str(binary_target),
                            paragraph_index=para_index,
                        )
                    )
        return anchors

    def _read_rels(self, zf: zipfile.ZipFile, rel_path: str) -> Dict[str, str]:
        if rel_path not in zf.namelist():
            return {}
        try:
            root = etree.fromstring(zf.read(rel_path))
        except etree.XMLSyntaxError:
            return {}
        out: Dict[str, str] = {}
        for rel in root.findall("pr:Relationship", NS):
            rid = rel.get("Id") or ""
            target = rel.get("Target") or ""
            out[rid] = target
        return out

    def _resolve_media(self, target: str) -> str:
        if target.startswith("/"):
            return target.lstrip("/")
        if target.startswith("word/"):
            return target
        return f"word/{target}"

    def _build_context_windows(
        self,
        paragraphs: List[DocxParagraph],
        images: List[ImageAnchor],
        radius: int,
    ) -> List[ContextWindow]:
        out: List[ContextWindow] = []
        for image in images:
            if image.paragraph_index is None:
                continue
            idx = image.paragraph_index
            lo = max(0, idx - radius)
            hi = min(len(paragraphs) - 1, idx + radius)
            rows: List[List[str]] = []
            placeholder = f"[IMAGE_{image.image_id}_ANCHOR]"
            for p in range(lo, hi + 1):
                if p == idx:
                    rows.append([placeholder])
                elif 0 <= p < len(paragraphs):
                    rows.append([paragraphs[p].text])
            out.append(
                ContextWindow(
                    anchor=f"paragraph:{idx}",
                    image_id=image.image_id,
                    radius=radius,
                    rows=rows,
                    placeholder=placeholder,
                    paragraph_index=idx,
                )
            )
        return out
