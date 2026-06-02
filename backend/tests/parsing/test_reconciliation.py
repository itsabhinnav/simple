"""Tests for the strict reconciler — deterministic always wins on cell values."""

from __future__ import annotations

from src.services.parsing.models import Cell, DeterministicExcelResult, ImageAnchor
from src.services.parsing.reconciliation import StrictReconciler


def _build_fake_det() -> DeterministicExcelResult:
    return DeterministicExcelResult(
        sheets=["Specs"],
        cells=[
            Cell(sheet="Specs", row=1, col=1, ref="A1", value="Product"),
            Cell(sheet="Specs", row=1, col=2, ref="B1", value="Price"),
            Cell(sheet="Specs", row=14, col=2, ref="B14", value="Price: $10,450"),
        ],
        images=[
            ImageAnchor(
                image_id="img1",
                binary_storage_path="/tmp/img1.png",
                sheet="Specs",
                anchor_cell="C14",
            )
        ],
    )


def test_deterministic_wins_on_cell_value():
    det = _build_fake_det()
    vlm_output = {
        "provider": "fake",
        "model": "fake-model",
        "skipped": False,
        "raw_text": "Saw cell B14 with Price: $10,460 in product table",
        "parsed": {
            "cells": {"B14": "Price: $10,460"},
            "semantic_context": "Product X",
            "labels": ["product_pricing"],
            "image_descriptions": ["pie chart"],
        },
    }
    result = StrictReconciler().reconcile(det, [vlm_output])

    sheet_payload = result.structured_payload["sheets"]["Specs"]
    cell_values = {c["ref"]: c["value"] for c in sheet_payload["cells"]}
    assert cell_values["B14"] == "Price: $10,450"


def test_semantic_context_from_vlm_preserved():
    det = _build_fake_det()
    vlm_output = {
        "provider": "fake",
        "model": "fake-model",
        "skipped": False,
        "raw_text": "Price: $10,460",
        "parsed": {
            "cells": {"B14": "Price: $10,460"},
            "semantic_context": "Product X",
            "labels": ["product_pricing"],
            "image_descriptions": ["pie chart"],
        },
    }
    result = StrictReconciler().reconcile(det, [vlm_output])
    overlays = result.structured_payload["semantics"]
    assert overlays, "expected semantic overlays preserved"
    assert overlays[0]["semantic_context"] == "Product X"
    assert "product_pricing" in overlays[0]["labels"]
    assert "pie chart" in overlays[0]["image_descriptions"]


def test_conflict_logged_when_vlm_disagrees():
    det = _build_fake_det()
    vlm_output = {
        "provider": "fake",
        "model": "fake-model",
        "skipped": False,
        "raw_text": "Saw cell B14 with Price: $10,460",
        "parsed": {"cells": {"B14": "Price: $10,460"}},
    }
    result = StrictReconciler().reconcile(det, [vlm_output])
    coords = [c.coordinate for c in result.conflicts]
    assert "B14" in coords
    conflict = next(c for c in result.conflicts if c.coordinate == "B14")
    assert conflict.resolution == "deterministic_wins"
    assert conflict.deterministic_value == "Price: $10,450"


def test_artifact_classification_requirements():
    det = DeterministicExcelResult(
        sheets=["Requirements"],
        cells=[
            Cell(sheet="Requirements", row=1, col=1, ref="A1", value="Requirement ID"),
            Cell(sheet="Requirements", row=1, col=2, ref="B1", value="Given"),
            Cell(sheet="Requirements", row=1, col=3, ref="C1", value="When"),
            Cell(sheet="Requirements", row=1, col=4, ref="D1", value="Then"),
        ],
    )
    result = StrictReconciler().reconcile(det, [])
    assert result.artifact_kind == "requirements"
