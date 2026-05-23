from dataclasses import dataclass
from pathlib import Path
import re
import tempfile
from typing import Any, Dict, List, Optional

from openpyxl import load_workbook

from src.infrastructure.dependency_injection import get_hybrid_database_service
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


TARGET_ALIASES = {
    "spec": "specifications",
    "specs": "specifications",
    "specification": "specifications",
    "specifications": "specifications",
    "requirement": "requirements",
    "requirements": "requirements",
    "req": "requirements",
    "reqs": "requirements",
    "test": "test_cases",
    "tests": "test_cases",
    "testcase": "test_cases",
    "testcases": "test_cases",
    "test_case": "test_cases",
    "test_cases": "test_cases",
    "design": "design_tickets",
    "designs": "design_tickets",
    "design_ticket": "design_tickets",
    "design_tickets": "design_tickets",
    "ticket": "design_tickets",
    "tickets": "design_tickets",
}


HEADER_ALIASES = {
    "id": None,
    "specification_id": "spec_id",
    "spec id": "spec_id",
    "requirement id": "requirement_id",
    "req id": "requirement_id",
    "test case id": "test_case_id",
    "testcase id": "test_case_id",
    "design ticket id": "design_ticket_id",
    "design id": "design_ticket_id",
    "when": "when_action",
    "then": "then_result",
    "expected result": "then_result",
    "linked requirement": "linked_requirement_id",
    "linked requirement id": "linked_requirement_id",
    "associated requirement": "associated_requirement_id",
    "associated requirement id": "associated_requirement_id",
    "image": "image_url",
    "file": "file_url",
}


TARGET_CONFIG = {
    "specifications": {
        "table": "specifications",
        "id_field": "spec_id",
        "prefix": "SPEC",
        "required": ["spec_id", "title"],
        "defaults": {"status": "Draft"},
        "fields": ["spec_id", "title", "description", "category", "version", "status", "file_url", "created_by"],
        "ddl": """
            CREATE TABLE IF NOT EXISTS specifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spec_id TEXT UNIQUE,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT,
                version TEXT,
                status TEXT,
                file_url TEXT,
                created_by TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """,
    },
    "requirements": {
        "table": "requirements",
        "id_field": "requirement_id",
        "prefix": "REQ",
        "required": ["requirement_id", "title"],
        "defaults": {"priority": "P2", "status": "Draft"},
        "fields": [
            "requirement_id", "title", "description", "requirement_type", "given",
            "when_action", "then_result", "priority", "status", "assignee", "tags", "created_by",
        ],
        "ddl": None,
    },
    "test_cases": {
        "table": "test_cases",
        "id_field": "test_case_id",
        "prefix": "TC",
        "required": ["test_case_id"],
        "defaults": {"priority": "P2", "test_type": "Positive"},
        "fields": [
            "test_case_id", "reference_document", "associated_requirement_id", "screen_id",
            "feature", "dr_applicable_screens", "dr_id", "test_objective", "preconditions",
            "procedure", "expected_behavior", "test_type", "region", "brand", "vehicle_variant",
            "vehicle_specification", "env_dependency", "requirement_type", "regulation",
            "priority", "testsuite_type", "created_by",
        ],
        "ddl": None,
    },
    "design_tickets": {
        "table": "design_tickets",
        "id_field": "design_ticket_id",
        "prefix": "DT",
        "required": ["design_ticket_id", "title"],
        "defaults": {"priority": "P2", "status": "Draft"},
        "fields": [
            "design_ticket_id", "title", "description", "design_type", "diagram_type",
            "image_url", "priority", "status", "linked_requirement_id", "assignee", "tags", "created_by",
        ],
        "ddl": """
            CREATE TABLE IF NOT EXISTS design_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                design_ticket_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                design_type TEXT,
                diagram_type TEXT,
                image_url TEXT,
                priority TEXT,
                status TEXT DEFAULT 'Draft',
                linked_requirement_id TEXT,
                assignee TEXT,
                tags TEXT,
                created_by TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """,
    },
}


@dataclass
class ImportRowResult:
    row: int
    status: str
    id: Optional[str] = None
    error: Optional[str] = None


class BulkImportService:
    def __init__(self):
        self.database_service = get_hybrid_database_service()

    def import_files(self, files, target: str, created_by: str = "system") -> Dict[str, Any]:
        normalized_target = self._normalize_target(target)
        if normalized_target is None and target != "auto":
            raise ValueError("Unsupported import type")

        summaries = []
        totals = {"created": 0, "skipped": 0, "failed": 0}

        for file_storage in files:
            filename = file_storage.filename or ""
            suffix = Path(filename).suffix.lower()
            if suffix not in {".xlsx", ".xlsm"}:
                summaries.append({
                    "file": filename,
                    "created": 0,
                    "skipped": 0,
                    "failed": 1,
                    "sheets": [],
                    "errors": [{"row": None, "error": "Only .xlsx and .xlsm files are supported"}],
                })
                totals["failed"] += 1
                continue

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                file_storage.save(tmp.name)
                temp_path = tmp.name

            try:
                summary = self._import_workbook(temp_path, filename, normalized_target, created_by)
                summaries.append(summary)
                for key in totals:
                    totals[key] += summary[key]
            finally:
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except Exception:
                    pass

        return {"files": summaries, "totals": totals}

    def _import_workbook(self, path: str, filename: str, target: Optional[str], created_by: str) -> Dict[str, Any]:
        workbook = load_workbook(path, read_only=True, data_only=True)
        file_summary = {"file": filename, "created": 0, "skipped": 0, "failed": 0, "sheets": [], "errors": []}

        for sheet in workbook.worksheets:
            sheet_target = target or self._infer_target(sheet.title, filename)
            if not sheet_target:
                continue

            sheet_summary = self._import_sheet(sheet, sheet_target, created_by)
            file_summary["sheets"].append(sheet_summary)
            file_summary["created"] += sheet_summary["created"]
            file_summary["skipped"] += sheet_summary["skipped"]
            file_summary["failed"] += sheet_summary["failed"]
            file_summary["errors"].extend([
                {"sheet": sheet.title, **error} for error in sheet_summary["errors"][:20]
            ])

        if not file_summary["sheets"]:
            file_summary["failed"] += 1
            file_summary["errors"].append({"row": None, "error": "No matching sheets found for the selected import type"})

        return file_summary

    def _import_sheet(self, sheet, target: str, created_by: str) -> Dict[str, Any]:
        config = TARGET_CONFIG[target]
        self._ensure_table(config)

        rows = sheet.iter_rows(values_only=True)
        header_row = next(rows, None)
        headers = self._normalize_headers(header_row or [])
        summary = {"sheet": sheet.title, "target": target, "created": 0, "skipped": 0, "failed": 0, "errors": []}

        if not any(headers):
            summary["failed"] += 1
            summary["errors"].append({"row": 1, "error": "Header row is empty"})
            return summary

        for row_number, row_values in enumerate(rows, start=2):
            if self._is_blank_row(row_values):
                continue
            row_data = self._row_to_dict(headers, row_values)
            result = self._import_row(config, row_data, row_number, created_by)
            summary[result.status] += 1
            if result.error:
                summary["errors"].append({"row": result.row, "id": result.id, "error": result.error})

        return summary

    def _import_row(self, config: Dict[str, Any], row_data: Dict[str, Any], row_number: int, created_by: str) -> ImportRowResult:
        try:
            payload = self._prepare_payload(config, row_data, row_number, created_by)
            missing = [field for field in config["required"] if not payload.get(field)]
            if missing:
                return ImportRowResult(row=row_number, status="failed", error=f"Missing required fields: {', '.join(missing)}")

            table = config["table"]
            id_field = config["id_field"]
            record_id = payload[id_field]
            existing = self.database_service.execute_query(
                f"SELECT id FROM {table} WHERE {id_field} = ?",
                "default",
                params=(record_id,),
            )
            if existing.get("data"):
                return ImportRowResult(row=row_number, status="skipped", id=record_id, error="Duplicate ID skipped")

            fields = [field for field in config["fields"] if payload.get(field) is not None]
            placeholders = ", ".join(["?" for _ in fields])
            columns = ", ".join(fields)
            values = tuple(payload[field] for field in fields)
            result = self.database_service.execute_query(
                f"INSERT INTO {table} ({columns}, created_at, updated_at) VALUES ({placeholders}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                "default",
                params=values,
            )
            if not result.get("success"):
                return ImportRowResult(row=row_number, status="failed", id=record_id, error=result.get("error", "Insert failed"))

            return ImportRowResult(row=row_number, status="created", id=record_id)
        except Exception as exc:
            logger.exception("Bulk import row failed")
            return ImportRowResult(row=row_number, status="failed", error=str(exc))

    def _prepare_payload(self, config: Dict[str, Any], row_data: Dict[str, Any], row_number: int, created_by: str) -> Dict[str, Any]:
        payload = {field: row_data.get(field) for field in config["fields"]}
        payload.update({key: value for key, value in config["defaults"].items() if not payload.get(key)})
        payload["created_by"] = row_data.get("created_by") or created_by

        id_field = config["id_field"]
        if not payload.get(id_field):
            payload[id_field] = self._generated_id(config["prefix"], row_number)

        if "title" in config["required"] and not payload.get("title"):
            payload["title"] = payload.get("description") or payload.get(id_field)

        return payload

    def _ensure_table(self, config: Dict[str, Any]) -> None:
        ddl = config.get("ddl")
        if ddl:
            self.database_service.execute_query(ddl, "default")

    def _normalize_target(self, target: str) -> Optional[str]:
        key = self._normalize_header(target or "")
        return TARGET_ALIASES.get(key)

    def _infer_target(self, sheet_name: str, filename: str) -> Optional[str]:
        for value in (sheet_name, Path(filename).stem):
            normalized = self._normalize_header(value)
            for alias, target in TARGET_ALIASES.items():
                if alias in normalized:
                    return target
        return None

    def _normalize_headers(self, headers: List[Any]) -> List[Optional[str]]:
        return [self._normalize_header_cell(header) for header in headers]

    def _normalize_header_cell(self, header: Any) -> Optional[str]:
        if header is None:
            return None
        raw = str(header).strip()
        if not raw:
            return None
        lowered = raw.lower().strip()
        if lowered in HEADER_ALIASES:
            return HEADER_ALIASES[lowered]
        return self._normalize_header(raw)

    def _normalize_header(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")

    def _row_to_dict(self, headers: List[Optional[str]], row_values: List[Any]) -> Dict[str, Any]:
        row = {}
        for header, value in zip(headers, row_values):
            if not header:
                continue
            clean_value = self._clean_cell(value)
            if clean_value is not None:
                row[header] = clean_value
        return row

    def _clean_cell(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return str(value).strip()

    def _is_blank_row(self, row_values: List[Any]) -> bool:
        return all(self._clean_cell(value) is None for value in row_values)

    def _generated_id(self, prefix: str, row_number: int) -> str:
        import time
        return f"{prefix}_{int(time.time())}_{row_number}"
