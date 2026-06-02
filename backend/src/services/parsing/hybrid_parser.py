"""Orchestrator for the hybrid document parsing engine."""

from __future__ import annotations

import concurrent.futures
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.logging_config import get_logger
from src.interfaces.llm_provider import VLMProviderError, VLMRegistry
from src.services.parsing.context_assembly import AssembledContext, HybridContextAssembler
from src.services.parsing.deterministic.docx_parser import DocxDeterministicParser
from src.services.parsing.deterministic.excel_parser import ExcelDeterministicParser
from src.services.parsing.models import (
    DeterministicDocxResult,
    DeterministicExcelResult,
    HybridParseResult,
    ParseOptions,
)
from src.services.parsing.reconciliation import StrictReconciler
from src.services.parsing.visual.preprocessor import PageSnapshot, VisualPreprocessor

logger = get_logger(__name__)


_DETERMINISTIC_RESULT = Union[DeterministicExcelResult, DeterministicDocxResult]


class HybridDocumentParser:
    """Run the full deterministic → visual → assembler → VLM → reconciliation pipeline."""

    def __init__(
        self,
        excel_parser: ExcelDeterministicParser,
        docx_parser: DocxDeterministicParser,
        visual_preprocessor: VisualPreprocessor,
        assembler: HybridContextAssembler,
        vlm_registry: VLMRegistry,
        reconciler: StrictReconciler,
        config: Optional[Any] = None,
    ) -> None:
        self.excel_parser = excel_parser
        self.docx_parser = docx_parser
        self.visual_preprocessor = visual_preprocessor
        self.assembler = assembler
        self.vlm_registry = vlm_registry
        self.reconciler = reconciler
        self.config = config or get_config_manager()

    def parse(self, file_path: str, options: Optional[ParseOptions] = None) -> HybridParseResult:
        options = options or ParseOptions()
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"input file missing: {file_path}")

        file_type = self._detect_type(path)
        warnings: List[str] = []
        if file_type == "unknown":
            warnings.append(f"unsupported file extension: {path.suffix}")
            return HybridParseResult(file_type="unknown", warnings=warnings)

        deterministic = self._run_deterministic_and_visual(file_type, path, options, warnings)
        det_result = deterministic["deterministic"]
        snapshots: List[PageSnapshot] = deterministic["snapshots"]

        contexts = self.assembler.assemble(det_result, snapshots)

        vlm_outputs: List[Dict[str, Any]] = []
        if options.enable_vlm:
            vlm_outputs = self._run_vlm(contexts, options, warnings)
        else:
            warnings.append("vlm disabled by options")

        result = self.reconciler.reconcile(det_result, vlm_outputs, warnings=warnings)
        return result

    def _detect_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".xlsx":
            return "xlsx"
        if suffix == ".docx":
            return "docx"
        return "unknown"

    def _run_deterministic_and_visual(
        self,
        file_type: str,
        path: Path,
        options: ParseOptions,
        warnings: List[str],
    ) -> Dict[str, Any]:
        det_runner = self._select_deterministic(file_type)

        if not options.enable_visual:
            snapshots: List[PageSnapshot] = []
            det_result = det_runner(path)
            return {"deterministic": det_result, "snapshots": snapshots}

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            det_future = pool.submit(det_runner, path)
            visual_future = pool.submit(self._safe_snapshot, path)

            try:
                det_result = det_future.result()
            except Exception as exc:  # noqa: BLE001 - bubbled into warnings
                logger.error(f"deterministic parser failed: {exc}", exc_info=True)
                raise
            try:
                snapshots = visual_future.result()
            except Exception as exc:  # noqa: BLE001 - visual is optional
                warnings.append(f"visual preprocessor failed: {exc}")
                snapshots = []
        return {"deterministic": det_result, "snapshots": snapshots}

    def _safe_snapshot(self, path: Path) -> List[PageSnapshot]:
        try:
            return self.visual_preprocessor.snapshot(path)
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            logger.warning(f"snapshot raised: {exc}")
            return []

    def _select_deterministic(self, file_type: str):
        if file_type == "xlsx":
            return self.excel_parser.parse
        return self.docx_parser.parse

    def _run_vlm(
        self,
        contexts: List[AssembledContext],
        options: ParseOptions,
        warnings: List[str],
    ) -> List[Dict[str, Any]]:
        provider_name = options.provider or self.vlm_registry.get_default_name()
        if not provider_name:
            warnings.append("no default VLM provider configured")
            return [{"provider": None, "model": None, "skipped": True, "error": "no default provider"}]
        try:
            provider = self.vlm_registry.get(provider_name)
        except VLMProviderError as exc:
            warnings.append(f"provider unavailable: {exc.message}")
            return [
                {
                    "provider": provider_name,
                    "model": exc.model,
                    "skipped": True,
                    "error": exc.message,
                }
            ]

        outputs: List[Dict[str, Any]] = []
        for ctx in contexts:
            if not ctx.snapshot:
                outputs.append(
                    {
                        "provider": provider_name,
                        "model": getattr(provider, "_model", "default"),
                        "skipped": True,
                        "error": "no snapshot available",
                    }
                )
                continue
            try:
                parsed = provider.extract_structured(
                    ctx.snapshot.image_path,
                    ctx.prompt,
                    options.schema_hint or {"cells": "ref->value", "labels": "list", "image_descriptions": "list"},
                )
                outputs.append(
                    {
                        "provider": provider_name,
                        "model": getattr(provider, "_model", "default"),
                        "skipped": False,
                        "parsed": parsed,
                        "raw_text": str(parsed),
                    }
                )
            except VLMProviderError as exc:
                logger.warning(f"VLM call failed: {exc.message}")
                outputs.append(
                    {
                        "provider": provider_name,
                        "model": exc.model,
                        "skipped": True,
                        "error": exc.message,
                    }
                )
        return outputs
