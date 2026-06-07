"""Deterministic Excel (.xlsx) parser using zipfile + lxml (+ openpyxl for value cache).

Implements the user-provided architecture:
  Phase A — shared strings + sheet XML → CellGrid (with merge propagation and dimension clamping)
  Phase B — drawings/_rels → ImageAnchor records (EMU offsets + bbox estimate + A1 anchor)
  Phase C — build_spatial_proximity_matrix → ContextWindow list around each image
"""

from __future__ import annotations

import io
import re
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from lxml import etree

from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.logging_config import get_logger
from src.services.parsing.models import (
    BoundingBox,
    Cell,
    ContextWindow,
    DeterministicExcelResult,
    ImageAnchor,
    MergedRange,
)

logger = get_logger(__name__)


# SAK-040: shared hardened XML parser. All etree.fromstring calls in this
# module must use this parser to keep XXE/SSRF off even if upstream defaults
# regress.
_SAFE_PARSER = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    load_dtd=False,
    huge_tree=False,
    dtd_validation=False,
)


NS = {
    "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}


REF_RE = re.compile(r"^([A-Z]+)(\d+)$")


def col_letter_to_index(letters: str) -> int:
    """Convert A->1, Z->26, AA->27."""
    value = 0
    for ch in letters:
        value = value * 26 + (ord(ch) - 64)
    return value


def col_index_to_letter(idx: int) -> str:
    """Convert 1->A, 26->Z, 27->AA. idx is 1-indexed."""
    if idx <= 0:
        raise ValueError(f"Column index must be >= 1, got {idx}")
    letters = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def parse_ref(ref: str) -> Tuple[int, int]:
    """Parse "B14" -> (row=14, col=2)."""
    match = REF_RE.match(ref)
    if not match:
        raise ValueError(f"Invalid cell ref: {ref}")
    return int(match.group(2)), col_letter_to_index(match.group(1))


def make_ref(row: int, col: int) -> str:
    return f"{col_index_to_letter(col)}{row}"


def _local(tag: str) -> str:
    """Strip namespace from lxml tag."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


class _SheetData:
    """Internal container for one parsed sheet."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.dimension: Optional[str] = None
        self.max_row: int = 0
        self.max_col: int = 0
        self.cells: Dict[Tuple[int, int], Cell] = {}
        self.merged: List[MergedRange] = []
        self.hidden_rows: List[int] = []
        self.hidden_cols: List[int] = []
        self.drawing_part: Optional[str] = None


class ExcelDeterministicParser:
    """Deterministic .xlsx parser following the documented architecture."""

    def __init__(self, tmp_dir: Optional[str] = None, spatial_radius: Optional[int] = None) -> None:
        cm = get_config_manager()
        self._tmp_dir = Path(tmp_dir or cm.get_config("parsing.tmp_dir", "data/tmp/parsing"))
        self._spatial_radius = int(spatial_radius or cm.get_config("parsing.spatial_radius", 4) or 4)

    # ----------------------------- public API -----------------------------

    def parse(self, path: Path) -> DeterministicExcelResult:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"xlsx not found: {path}")
        warnings: List[str] = []
        self._tmp_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(path, "r") as zf:
            shared_strings = self._read_shared_strings(zf, warnings)
            sheets, sheet_paths = self._read_workbook_sheets(zf, warnings)
            workbook_rels = self._read_rels(zf, "xl/_rels/workbook.xml.rels")

            sheet_data: List[_SheetData] = []
            for name, rel_id in sheets:
                target = workbook_rels.get(rel_id)
                if not target:
                    warnings.append(f"sheet {name}: missing rel target")
                    continue
                sheet_xml_path = self._normalize_xl(target)
                data = self._parse_sheet(zf, name, sheet_xml_path, shared_strings, warnings)
                sheet_data.append(data)

            images = self._parse_drawings(zf, sheet_data, path.stem, warnings)

        cell_list: List[Cell] = []
        merged_ranges: List[MergedRange] = []
        hidden: Dict[str, Dict[str, List[int]]] = {}
        dimensions: Dict[str, str] = {}
        for sd in sheet_data:
            cell_list.extend(sd.cells.values())
            merged_ranges.extend(sd.merged)
            hidden[sd.name] = {"rows": sorted(sd.hidden_rows), "cols": sorted(sd.hidden_cols)}
            if sd.dimension:
                dimensions[sd.name] = sd.dimension

        context_windows = self.build_spatial_proximity_matrix(sheet_data, images, radius=self._spatial_radius)

        return DeterministicExcelResult(
            sheets=[sd.name for sd in sheet_data],
            cells=cell_list,
            merged_ranges=merged_ranges,
            hidden=hidden,
            images=images,
            context_windows=context_windows,
            warnings=warnings,
            dimensions=dimensions,
        )

    # ----------------------------- phase A -----------------------------

    def _read_shared_strings(self, zf: zipfile.ZipFile, warnings: List[str]) -> List[str]:
        if "xl/sharedStrings.xml" not in zf.namelist():
            return []
        try:
            data = zf.read("xl/sharedStrings.xml")
            root = etree.fromstring(data, _SAFE_PARSER)
        except etree.XMLSyntaxError as exc:
            warnings.append(f"sharedStrings parse error: {exc}")
            return []
        strings: List[str] = []
        for si in root.findall("s:si", NS):
            parts = [(t.text or "") for t in si.iter() if _local(t.tag) == "t"]
            strings.append("".join(parts))
        return strings

    def _read_workbook_sheets(self, zf: zipfile.ZipFile, warnings: List[str]) -> Tuple[List[Tuple[str, str]], List[str]]:
        try:
            root = etree.fromstring(zf.read("xl/workbook.xml"), _SAFE_PARSER)
        except (KeyError, etree.XMLSyntaxError) as exc:
            warnings.append(f"workbook.xml unreadable: {exc}")
            return [], []
        sheets: List[Tuple[str, str]] = []
        sheet_paths: List[str] = []
        for sh in root.findall(".//s:sheets/s:sheet", NS):
            name = sh.get("name") or "Sheet"
            rid = sh.get(f"{{{NS['r']}}}id") or ""
            sheets.append((name, rid))
            sheet_paths.append(name)
        return sheets, sheet_paths

    def _read_rels(self, zf: zipfile.ZipFile, rel_path: str) -> Dict[str, str]:
        if rel_path not in zf.namelist():
            return {}
        try:
            root = etree.fromstring(zf.read(rel_path), _SAFE_PARSER)
        except etree.XMLSyntaxError:
            return {}
        out: Dict[str, str] = {}
        for rel in root.findall("pr:Relationship", NS):
            rid = rel.get("Id") or ""
            target = rel.get("Target") or ""
            out[rid] = target
        return out

    def _normalize_xl(self, target: str) -> str:
        """Resolve a workbook rel Target into a full zip path under xl/."""
        if target.startswith("/"):
            return target.lstrip("/")
        if target.startswith("xl/"):
            return target
        return f"xl/{target}"

    def _parse_sheet(
        self,
        zf: zipfile.ZipFile,
        name: str,
        sheet_path: str,
        shared_strings: List[str],
        warnings: List[str],
    ) -> _SheetData:
        data = _SheetData(name)
        if sheet_path not in zf.namelist():
            warnings.append(f"sheet xml missing: {sheet_path}")
            return data
        try:
            root = etree.fromstring(zf.read(sheet_path), _SAFE_PARSER)
        except etree.XMLSyntaxError as exc:
            warnings.append(f"sheet {name} parse error: {exc}")
            return data

        dim = root.find("s:dimension", NS)
        if dim is not None and dim.get("ref"):
            data.dimension = dim.get("ref")
            clamp_max_row, clamp_max_col = self._dimension_bounds(data.dimension)
        else:
            clamp_max_row, clamp_max_col = (0, 0)
            warnings.append(f"sheet {name}: no <dimension>, falling back to row scan")

        for col_el in root.findall(".//s:cols/s:col", NS):
            if col_el.get("hidden") == "1":
                try:
                    cmin = int(col_el.get("min") or "0")
                    cmax = int(col_el.get("max") or cmin)
                    data.hidden_cols.extend(range(cmin, cmax + 1))
                except ValueError:
                    continue

        sheet_view = root.find(".//s:sheetData", NS)
        if sheet_view is not None:
            for row_el in sheet_view.findall("s:row", NS):
                try:
                    row_num = int(row_el.get("r") or "0")
                except ValueError:
                    continue
                if not row_num:
                    continue
                if row_el.get("hidden") == "1":
                    data.hidden_rows.append(row_num)
                if clamp_max_row and row_num > clamp_max_row + 256:
                    warnings.append(f"sheet {name}: row {row_num} beyond dimension {data.dimension}; stopping")
                    break
                if row_num > data.max_row:
                    data.max_row = row_num
                for cell_el in row_el.findall("s:c", NS):
                    ref = cell_el.get("r")
                    if not ref:
                        continue
                    try:
                        r, c = parse_ref(ref)
                    except ValueError:
                        continue
                    if c > data.max_col:
                        data.max_col = c
                    cell = self._build_cell(name, ref, r, c, cell_el, shared_strings)
                    data.cells[(r, c)] = cell

        for mc in root.findall(".//s:mergeCells/s:mergeCell", NS):
            ref = mc.get("ref")
            if not ref or ":" not in ref:
                continue
            try:
                start, end = ref.split(":", 1)
                sr, sc = parse_ref(start)
                er, ec = parse_ref(end)
            except ValueError:
                continue
            data.merged.append(
                MergedRange(sheet=name, ref=ref, start_row=sr, start_col=sc, end_row=er, end_col=ec)
            )

        self._propagate_merges(data)

        rel_path = sheet_path.replace("xl/worksheets/", "xl/worksheets/_rels/") + ".rels"
        rels = self._read_rels(zf, rel_path)
        for rid, target in rels.items():
            if "drawing" in target.lower():
                resolved = target.replace("../", "xl/") if target.startswith("..") else self._normalize_xl(target)
                data.drawing_part = resolved
                break

        return data

    def _dimension_bounds(self, dim_ref: str) -> Tuple[int, int]:
        try:
            if ":" in dim_ref:
                start, end = dim_ref.split(":", 1)
                er, ec = parse_ref(end)
                return er, ec
            r, c = parse_ref(dim_ref)
            return r, c
        except ValueError:
            return 0, 0

    def _build_cell(
        self,
        sheet: str,
        ref: str,
        row: int,
        col: int,
        cell_el: etree._Element,
        shared_strings: List[str],
    ) -> Cell:
        cell_type = cell_el.get("t") or "n"
        v_el = cell_el.find("s:v", NS)
        f_el = cell_el.find("s:f", NS)
        is_el = cell_el.find("s:is", NS)

        raw_value: Any = None
        raw_text: Optional[str] = None
        if cell_type == "s" and v_el is not None and (v_el.text or "").strip():
            try:
                idx = int(v_el.text)
                if 0 <= idx < len(shared_strings):
                    raw_value = shared_strings[idx]
                    raw_text = raw_value
            except ValueError:
                raw_value = v_el.text
                raw_text = v_el.text
        elif cell_type in ("str", "inlineStr") and is_el is not None:
            raw_value = "".join((t.text or "") for t in is_el.iter() if _local(t.tag) == "t")
            raw_text = raw_value
        elif cell_type == "str" and v_el is not None:
            raw_value = v_el.text
            raw_text = v_el.text
        elif cell_type == "b" and v_el is not None:
            raw_value = bool(int(v_el.text or "0"))
            raw_text = str(raw_value)
        elif v_el is not None and (v_el.text or "").strip():
            try:
                raw_value = float(v_el.text)
                if raw_value.is_integer():
                    raw_value = int(raw_value)
                raw_text = str(raw_value)
            except ValueError:
                raw_value = v_el.text
                raw_text = v_el.text

        formula = f_el.text if f_el is not None else None
        needs_evaluation = formula is not None and (v_el is None or not (v_el.text or "").strip())

        return Cell(
            sheet=sheet,
            row=row,
            col=col,
            ref=ref,
            value=raw_value,
            raw_text=raw_text,
            data_type=cell_type,
            needs_evaluation=needs_evaluation,
            formula=formula,
        )

    def _propagate_merges(self, data: _SheetData) -> None:
        for merged in data.merged:
            origin_key = (merged.start_row, merged.start_col)
            origin_cell = data.cells.get(origin_key)
            if origin_cell is None:
                continue
            origin_cell.is_merged_origin = True
            for r in range(merged.start_row, merged.end_row + 1):
                for c in range(merged.start_col, merged.end_col + 1):
                    if (r, c) == origin_key:
                        continue
                    ref = make_ref(r, c)
                    existing = data.cells.get((r, c))
                    if existing is None or existing.value in (None, ""):
                        data.cells[(r, c)] = Cell(
                            sheet=data.name,
                            row=r,
                            col=c,
                            ref=ref,
                            value=origin_cell.value,
                            raw_text=origin_cell.raw_text,
                            data_type=origin_cell.data_type,
                            inherited_from=origin_cell.ref,
                        )

    # ----------------------------- phase B -----------------------------

    def _parse_drawings(
        self,
        zf: zipfile.ZipFile,
        sheets: List[_SheetData],
        file_stem: str,
        warnings: List[str],
    ) -> List[ImageAnchor]:
        out: List[ImageAnchor] = []
        for sd in sheets:
            if not sd.drawing_part:
                continue
            drawing_xml_path = sd.drawing_part
            if drawing_xml_path not in zf.namelist():
                warnings.append(f"drawing missing for sheet {sd.name}: {drawing_xml_path}")
                continue
            try:
                root = etree.fromstring(zf.read(drawing_xml_path), _SAFE_PARSER)
            except etree.XMLSyntaxError as exc:
                warnings.append(f"drawing parse error for {sd.name}: {exc}")
                continue

            drawing_rel_path = drawing_xml_path.replace("xl/drawings/", "xl/drawings/_rels/") + ".rels"
            drawing_rels = self._read_rels(zf, drawing_rel_path)

            for anchor_el in root.iter():
                local = _local(anchor_el.tag)
                if local not in ("twoCellAnchor", "oneCellAnchor"):
                    continue
                anchor = self._build_image_anchor(zf, sd, anchor_el, drawing_rels, file_stem, warnings)
                if anchor:
                    out.append(anchor)
        return out

    def _build_image_anchor(
        self,
        zf: zipfile.ZipFile,
        sheet: _SheetData,
        anchor_el: etree._Element,
        drawing_rels: Dict[str, str],
        file_stem: str,
        warnings: List[str],
    ) -> Optional[ImageAnchor]:
        from_el = anchor_el.find("xdr:from", NS)
        to_el = anchor_el.find("xdr:to", NS)
        if from_el is None:
            return None

        from_row = self._int_text(from_el, "xdr:row")
        from_col = self._int_text(from_el, "xdr:col")
        from_row_off = self._int_text(from_el, "xdr:rowOff")
        from_col_off = self._int_text(from_el, "xdr:colOff")

        if to_el is not None:
            to_row = self._int_text(to_el, "xdr:row")
            to_col = self._int_text(to_el, "xdr:col")
            to_row_off = self._int_text(to_el, "xdr:rowOff")
            to_col_off = self._int_text(to_el, "xdr:colOff")
        else:
            to_row = from_row
            to_col = from_col
            to_row_off = from_row_off
            to_col_off = from_col_off

        anchor_cell = make_ref(from_row + 1, from_col + 1)
        bbox = BoundingBox(
            start_row=from_row + 1,
            start_col=from_col + 1,
            end_row=to_row + 1,
            end_col=to_col + 1,
        )

        blip = None
        for el in anchor_el.iter():
            if _local(el.tag) == "blip":
                blip = el
                break
        if blip is None:
            return None
        embed_id = blip.get(f"{{{NS['r']}}}embed")
        target = drawing_rels.get(embed_id or "")
        if not target:
            warnings.append(f"sheet {sheet.name}: image rel {embed_id} unresolved")
            return None

        media_path = target.replace("../", "xl/") if target.startswith("..") else self._normalize_xl(target)
        if media_path not in zf.namelist():
            warnings.append(f"sheet {sheet.name}: media missing {media_path}")
            return None

        image_id = f"{file_stem}_{sheet.name}_{uuid.uuid4().hex[:8]}"
        suffix = Path(media_path).suffix or ".bin"
        binary_target = self._tmp_dir / f"{image_id}{suffix}"
        try:
            binary_target.write_bytes(zf.read(media_path))
        except OSError as exc:
            warnings.append(f"could not write image binary {binary_target}: {exc}")
            return None

        return ImageAnchor(
            image_id=image_id,
            binary_storage_path=str(binary_target),
            sheet=sheet.name,
            anchor_cell=anchor_cell,
            bounding_box_estimate=bbox,
            emu_offsets={
                "from_col_off": from_col_off,
                "from_row_off": from_row_off,
                "to_col_off": to_col_off,
                "to_row_off": to_row_off,
            },
        )

    def _int_text(self, parent: etree._Element, xpath: str) -> int:
        el = parent.find(xpath, NS)
        if el is None or el.text is None:
            return 0
        try:
            return int(el.text)
        except ValueError:
            return 0

    # ----------------------------- phase C -----------------------------

    def build_spatial_proximity_matrix(
        self,
        sheets: List[_SheetData],
        images: List[ImageAnchor],
        radius: int = 4,
    ) -> List[ContextWindow]:
        windows: List[ContextWindow] = []
        by_sheet: Dict[str, _SheetData] = {sd.name: sd for sd in sheets}
        for image in images:
            if not image.sheet or image.sheet not in by_sheet:
                continue
            sheet = by_sheet[image.sheet]
            bbox = image.bounding_box_estimate
            if not bbox:
                continue
            r_lo = max(1, bbox.start_row - radius)
            r_hi = bbox.end_row + radius
            c_lo = max(1, bbox.start_col - radius)
            c_hi = bbox.end_col + radius
            placeholder = f"[IMAGE_{image.image_id}_ANCHOR]"
            rows: List[List[str]] = []
            for r in range(r_lo, r_hi + 1):
                row: List[str] = []
                for c in range(c_lo, c_hi + 1):
                    if bbox.start_row <= r <= bbox.end_row and bbox.start_col <= c <= bbox.end_col:
                        row.append(placeholder)
                        continue
                    cell = sheet.cells.get((r, c))
                    if cell is None or cell.value is None:
                        row.append("")
                    else:
                        row.append(str(cell.value))
                rows.append(row)
            windows.append(
                ContextWindow(
                    sheet=image.sheet,
                    anchor=image.anchor_cell or "",
                    image_id=image.image_id,
                    radius=radius,
                    rows=rows,
                    placeholder=placeholder,
                )
            )
        return windows

    # --------------------------- formula stub ---------------------------

    def evaluate_formulas(self, workbook_path: Path) -> bool:  # noqa: ARG002 - intentional stub
        """Stub: returns False until an evaluator (pycel/LibreOffice) is wired in."""
        return False
