"""End-to-end smoke for the orchestrator without any VLM provider being available."""

from __future__ import annotations

import pytest

from src.interfaces.llm_provider import VLMProviderError, VLMRegistry
from src.services.parsing.context_assembly import HybridContextAssembler
from src.services.parsing.deterministic.docx_parser import DocxDeterministicParser
from src.services.parsing.deterministic.excel_parser import ExcelDeterministicParser
from src.services.parsing.hybrid_parser import HybridDocumentParser
from src.services.parsing.models import ParseOptions
from src.services.parsing.reconciliation import StrictReconciler
from src.services.parsing.visual.preprocessor import VisualPreprocessor


class _UnavailableRegistry(VLMRegistry):
    def __init__(self) -> None:
        super().__init__()
        self.register("none", lambda: self._raise_unavailable())
        self.set_default("none")

    def _raise_unavailable(self):
        raise VLMProviderError("none", "no provider available")


def _build_parser(tmp_path) -> HybridDocumentParser:
    return HybridDocumentParser(
        excel_parser=ExcelDeterministicParser(tmp_dir=str(tmp_path / "out")),
        docx_parser=DocxDeterministicParser(tmp_dir=str(tmp_path / "out")),
        visual_preprocessor=VisualPreprocessor(tmp_dir=str(tmp_path / "vp")),
        assembler=HybridContextAssembler(),
        vlm_registry=_UnavailableRegistry(),
        reconciler=StrictReconciler(),
    )


def test_xlsx_end_to_end_no_vlm(tmp_path, xlsx_fixture):
    parser = _build_parser(tmp_path)
    result = parser.parse(str(xlsx_fixture), ParseOptions(provider="none"))
    assert result.file_type == "xlsx"
    assert result.vlm.get("skipped") is True
    assert "Spec" in result.deterministic.get("sheets", [])
    assert result.deterministic.get("image_count") == 1
    assert isinstance(result.structured_payload.get("sheets"), dict)


def test_docx_end_to_end_no_vlm(tmp_path, docx_fixture):
    parser = _build_parser(tmp_path)
    result = parser.parse(str(docx_fixture), ParseOptions(provider="none"))
    assert result.file_type == "docx"
    assert result.vlm.get("skipped") is True
    assert result.deterministic.get("paragraphs", 0) >= 3
    assert result.deterministic.get("tables") == 1


def test_unsupported_extension_returns_warning(tmp_path):
    parser = _build_parser(tmp_path)
    fake = tmp_path / "thing.pdf"
    fake.write_bytes(b"%PDF-1.4")
    result = parser.parse(str(fake))
    assert result.file_type == "unknown"
    assert any("unsupported file extension" in w for w in result.warnings)
