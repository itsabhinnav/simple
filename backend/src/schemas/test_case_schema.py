"""Pydantic schemas for the test_cases entity.

The data model now distinguishes between **single-value** dropdown columns
(``test_type``, ``priority``, ``regulation``, ...) and **multi-value**
columns (``feature``, ``region``, ``brand``, ``vehicle_variant``,
``vehicle_mode``, ``env_dependency``, ``testsuite_type``,
``reference_document``, ``associated_requirement_id``, ``screen_id``).

Multi-value fields accept either::
    - a JSON-style list  : ["FOTA", "Radio"]
    - a CSV string       : "FOTA, Radio"
    - a single string    : "FOTA"
    - None / empty       : []

Pydantic normalises any of those shapes to ``List[str]`` so the repository
and API contract are predictable. The repository serialises them to JSON
strings before persisting.

Dropdown option lists themselves live in ``config.yaml`` under
``test_case_dropdowns`` (not in this file) so testers can extend pickers
without code changes.
"""

from datetime import datetime
from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


# Field names that this module treats as multi-value lists. Kept in sync
# with `test_case_dropdowns.multi_value_fields` in config.yaml.
MULTI_VALUE_FIELDS = (
    "reference_document",
    "associated_requirement_id",
    "screen_id",
    "feature",
    "region",
    "brand",
    "vehicle_variant",
    "vehicle_mode",
    "env_dependency",
    "testsuite_type",
)


def _coerce_to_list(value: Any) -> Optional[List[str]]:
    """Normalise an incoming multi-value field to ``List[str]``.

    Accepts list, tuple, comma-separated string, single scalar, or None.
    Empty / whitespace-only entries are dropped. Returns ``None`` for
    nullish input so downstream code can distinguish "not set" from
    "explicitly empty".
    """
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        out = [str(v).strip() for v in value if v is not None and str(v).strip() != ""]
        return out
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return []
        # JSON-encoded list (e.g. saved by an earlier write).
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                import json
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return [str(v).strip() for v in parsed if v is not None and str(v).strip() != ""]
            except Exception:
                pass
        return [part.strip() for part in stripped.split(",") if part.strip()]
    return [str(value).strip()]


MultiValue = Optional[Union[List[str], str]]


class _TestCaseFieldsMixin(BaseModel):
    """Field definitions shared by TestCaseSchema and TestCaseCreateSchema.

    Multi-value fields are typed ``List[str]`` after validation; the
    ``before`` validator coerces strings/CSVs into lists.
    """

    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=10000)
    vehicle_model: Optional[str] = Field(None, max_length=200)
    severity: Optional[str] = Field(None, max_length=50)

    # --- multi-value text columns ---
    reference_document: MultiValue = None
    associated_requirement_id: MultiValue = None
    screen_id: MultiValue = None
    feature: MultiValue = None
    region: MultiValue = None
    brand: MultiValue = None
    vehicle_variant: MultiValue = None
    vehicle_mode: MultiValue = None
    env_dependency: MultiValue = None
    testsuite_type: MultiValue = None

    # --- single-value columns ---
    dr_applicable_screens: Optional[str] = Field(None, max_length=1000)
    dr_id: Optional[str] = Field(None, max_length=200)
    test_objective: Optional[str] = Field(None, max_length=2000)
    preconditions: Optional[str] = Field(None, max_length=5000)
    procedure: Optional[str] = Field(None, max_length=10000)
    expected_behavior: Optional[str] = Field(None, max_length=5000)
    test_type: Optional[str] = Field(None, max_length=50)
    vehicle_specification: Optional[str] = Field(None, max_length=200)
    requirement_type: Optional[str] = Field(None, max_length=50)
    regulation: Optional[str] = Field(None, max_length=10)  # "Yes"/"No"
    priority: Optional[str] = Field(None, max_length=10)

    @field_validator(*MULTI_VALUE_FIELDS, mode="before")
    @classmethod
    def _normalise_multi_value(cls, value: Any) -> Any:
        return _coerce_to_list(value)


class TestCaseSchema(_TestCaseFieldsMixin):
    """Full test-case representation (DB row → response payload)."""

    id: Optional[int] = None
    test_case_id: str = Field(..., min_length=1, max_length=100)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TestCaseCreateSchema(_TestCaseFieldsMixin):
    """Payload accepted by ``POST /api/test-cases``."""

    test_case_id: str = Field(..., min_length=1, max_length=100)
