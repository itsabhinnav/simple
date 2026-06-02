"""Worker-side container that builds the orchestrator without Flask DI.

Celery workers do not have a Flask app context, so we cannot import the
`src.infrastructure.dependency_injection` module (which pulls Flask). This
lightweight container instantiates the same service classes directly.
"""

from __future__ import annotations

from typing import Optional

import src.implementations.llm  # noqa: F401 - auto-register adapters
from src.infrastructure.configuration_manager import get_config_manager
from src.interfaces.llm_provider import get_vlm_registry
from src.services.parsing.context_assembly import HybridContextAssembler
from src.services.parsing.deterministic.docx_parser import DocxDeterministicParser
from src.services.parsing.deterministic.excel_parser import ExcelDeterministicParser
from src.services.parsing.hybrid_parser import HybridDocumentParser
from src.services.parsing.reconciliation import StrictReconciler
from src.services.parsing.visual.preprocessor import VisualPreprocessor


class WorkerContainer:
    """Tiny stand-alone container for Celery workers."""

    _instance: Optional["WorkerContainer"] = None

    def __init__(self) -> None:
        cm = get_config_manager()
        registry = get_vlm_registry()
        registry.configure_from_config(cm)

        excel_parser = ExcelDeterministicParser()
        docx_parser = DocxDeterministicParser()
        visual = VisualPreprocessor()
        assembler = HybridContextAssembler()
        reconciler = StrictReconciler()

        self.parser = HybridDocumentParser(
            excel_parser=excel_parser,
            docx_parser=docx_parser,
            visual_preprocessor=visual,
            assembler=assembler,
            vlm_registry=registry,
            reconciler=reconciler,
            config=cm,
        )

    @classmethod
    def instance(cls) -> "WorkerContainer":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
