"""Tests for the deterministic DOCX parser."""

from __future__ import annotations

from src.services.parsing.deterministic.docx_parser import DocxDeterministicParser


def test_paragraph_extraction(tmp_path, docx_fixture):
    parser = DocxDeterministicParser(tmp_dir=str(tmp_path / "out"))
    result = parser.parse(docx_fixture)
    texts = [p.text for p in result.paragraphs]
    assert "Test Cases" in texts
    assert any("Intro paragraph" in t for t in texts)
    assert any("Paragraph after the image" in t for t in texts)
    headings = [p for p in result.paragraphs if p.is_heading]
    assert headings, "expected at least one heading"


def test_table_extraction(tmp_path, docx_fixture):
    parser = DocxDeterministicParser(tmp_dir=str(tmp_path / "out"))
    result = parser.parse(docx_fixture)
    assert len(result.tables) == 1
    table = result.tables[0]
    assert table.rows[0] == ["ID", "Description"]
    assert table.rows[1] == ["TC-001", "Validate price field"]


def test_image_anchor_capture(tmp_path, docx_fixture):
    parser = DocxDeterministicParser(tmp_dir=str(tmp_path / "out"))
    result = parser.parse(docx_fixture)
    assert len(result.images) == 1
    image = result.images[0]
    assert image.paragraph_index is not None
    assert image.paragraph_index >= 0
    assert image.binary_storage_path
    assert image.binary_storage_path.endswith((".png", ".jpg", ".jpeg", ".gif", ".bin"))


def test_context_window_built(tmp_path, docx_fixture):
    parser = DocxDeterministicParser(tmp_dir=str(tmp_path / "out"))
    result = parser.parse(docx_fixture)
    assert len(result.context_windows) == 1
    window = result.context_windows[0]
    assert window.paragraph_index is not None
    assert any("[IMAGE_" in cell for row in window.rows for cell in row)
