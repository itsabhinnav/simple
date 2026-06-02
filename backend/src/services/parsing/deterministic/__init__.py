"""Deterministic (CPU-only) parsers for .xlsx and .docx documents."""

from src.services.parsing.deterministic.excel_parser import ExcelDeterministicParser
from src.services.parsing.deterministic.docx_parser import DocxDeterministicParser

__all__ = ["ExcelDeterministicParser", "DocxDeterministicParser"]
