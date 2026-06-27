"""Pydantic schemas for the test_cases entity.

The data model now distinguishes between **single-value** dropdown columns
(``test_type``, ``priority``, ``regulation``, ...) and **multi-value**
columns (``feature``, ``region``, ``brand``, ``vehicle_variant``,
``vehicle_specification``, ``env_dependency``, ``testsuite_type``,
``reference_document``, ``associated_requirement_id``, ``screen_id``).

Schema notes (June 2026):
    * ``vehicle_mode`` was removed; ``vehicle_specification`` now carries
      the engine / powertrain class (Common, ICE, HEV, PHEV, EV) and is
      multi-value. Any inbound payload still using ``vehicle_mode`` is
      automatically migrated into ``vehicle_specification`` by the create
      / update validators below.
    * ``description`` was removed; the test narrative lives solely in
      ``test_objective``. Inbound payloads carrying a ``description``
      (older clients, legacy bulk imports) have it folded into
      ``test_objective`` if the latter is empty.

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

from pydantic import BaseModel, Field, field_validator, model_validator


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
    "vehicle_specification",
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
    vehicle_specification: MultiValue = None
    env_dependency: MultiValue = None
    testsuite_type: MultiValue = None

    # --- single-value columns ---
    dr_applicable_screens: Optional[str] = Field(None, max_length=1000)
    dr_id: Optional[str] = Field(None, max_length=200)
    test_objective: Optional[str] = Field(None, max_length=10000)
    preconditions: Optional[str] = Field(None, max_length=5000)
    procedure: Optional[str] = Field(None, max_length=10000)
    expected_behavior: Optional[str] = Field(None, max_length=5000)
    test_type: Optional[str] = Field(None, max_length=50)
    requirement_type: Optional[str] = Field(None, max_length=50)
    regulation: Optional[str] = Field(None, max_length=10)  # "Yes"/"No"
    priority: Optional[str] = Field(None, max_length=10)
    reference_spec_id: Optional[str] = Field(None, max_length=200)
    reference_spec_version: Optional[str] = Field(None, max_length=50)

    @field_validator(*MULTI_VALUE_FIELDS, mode="before")
    @classmethod
    def _normalise_multi_value(cls, value: Any) -> Any:
        return _coerce_to_list(value)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_aliases(cls, data: Any) -> Any:
        """Absorb retired field names from older clients / imports.

        * ``vehicle_mode`` payloads are funnelled into ``vehicle_specification``
          (and dropped). If both arrive, the explicit ``vehicle_specification``
          wins; otherwise the legacy value is reused.
        * ``description`` is folded into ``test_objective`` whenever the latter
          is empty, then dropped, so legacy CSV / API callers don't lose data
          on round-trip.
        """
        if not isinstance(data, dict):
            return data

        legacy_mode = data.pop("vehicle_mode", None)
        if legacy_mode is not None and not data.get("vehicle_specification"):
            data["vehicle_specification"] = legacy_mode

        legacy_description = data.pop("description", None)
        if legacy_description is not None and not data.get("test_objective"):
            data["test_objective"] = legacy_description

        return data


class TestCaseSchema(_TestCaseFieldsMixin):
    """Full test-case representation (DB row → response payload)."""

    id: Optional[int] = None
    test_case_id: str = Field(..., min_length=1, max_length=100)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TestCaseCreateSchema(_TestCaseFieldsMixin):
    """Payload accepted by ``POST /api/test-cases``."""

    test_case_id: str = Field(..., min_length=1, max_length=100)
