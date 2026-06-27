"""Schemas for requirements data validation.

The Pydantic field names track the logical names the frontend uses (``given``,
``when``, ``then``), but the underlying SQLite columns are ``when_action`` and
``then_result`` because ``when`` / ``then`` are SQL reserved keywords. The
service layer is responsible for the rename when building queries. The
controllers additionally normalise ``when_action``/``then_result`` in the
request body so legacy clients keep working.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class RequirementSchema(BaseModel):
    """Schema for requirement data validation"""
    id: Optional[int] = None
    requirement_id: str = Field(..., min_length=1, max_length=100)
    srs_id: Optional[str] = Field(None, max_length=100)
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    requirement_type: Optional[str] = Field(None, max_length=50)
    given: Optional[str] = None  # Given context
    when: Optional[str] = None  # When action (DB column: when_action)
    then: Optional[str] = None  # Then expected result (DB column: then_result)
    priority: Optional[str] = Field(None, max_length=20)
    tags: Optional[str] = None
    feature: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    brand: Optional[str] = Field(None, max_length=100)
    reference_spec_id: Optional[str] = Field(None, max_length=200)
    reference_spec_version: Optional[str] = Field(None, max_length=50)
    requirement_version: Optional[str] = Field(None, max_length=50)
    verification_method: Optional[str] = Field(None, max_length=50)
    linked_epic_jira_id: Optional[str] = Field(None, max_length=100)
    linked_test_case_ids: Optional[str] = None
    linked_design_ids: Optional[str] = None
    design_ticket_id: Optional[str] = Field(None, max_length=100)
    created_by: Optional[str] = Field(None, max_length=100)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RequirementCreateSchema(BaseModel):
    """Schema for creating a new requirement"""
    requirement_id: str = Field(..., min_length=1, max_length=100)
    srs_id: Optional[str] = Field(None, max_length=100)
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    requirement_type: Optional[str] = Field(None, max_length=50)
    given: Optional[str] = None
    when: Optional[str] = None
    then: Optional[str] = None
    priority: Optional[str] = Field(None, max_length=20)
    tags: Optional[str] = None
    feature: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    brand: Optional[str] = Field(None, max_length=100)
    reference_spec_id: Optional[str] = Field(None, max_length=200)
    reference_spec_version: Optional[str] = Field(None, max_length=50)
    requirement_version: Optional[str] = Field(None, max_length=50)
    verification_method: Optional[str] = Field(None, max_length=50)
    linked_epic_jira_id: Optional[str] = Field(None, max_length=100)
    linked_test_case_ids: Optional[str] = None
    linked_design_ids: Optional[str] = None
    design_ticket_id: Optional[str] = Field(None, max_length=100)


class RequirementUpdateSchema(BaseModel):
    """Schema for updating requirement data.

    ``requirement_type`` is editable here even though the original schema
    omitted it — the requirements table has the column and the detail page
    auto-saves it. Missing it caused silent drops on update.
    """
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    srs_id: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    requirement_type: Optional[str] = Field(None, max_length=50)
    given: Optional[str] = None
    when: Optional[str] = None
    then: Optional[str] = None
    priority: Optional[str] = Field(None, max_length=20)
    tags: Optional[str] = None
    feature: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    brand: Optional[str] = Field(None, max_length=100)
    reference_spec_id: Optional[str] = Field(None, max_length=200)
    reference_spec_version: Optional[str] = Field(None, max_length=50)
    requirement_version: Optional[str] = Field(None, max_length=50)
    verification_method: Optional[str] = Field(None, max_length=50)
    linked_epic_jira_id: Optional[str] = Field(None, max_length=100)
    linked_test_case_ids: Optional[str] = None
    linked_design_ids: Optional[str] = None
    design_ticket_id: Optional[str] = Field(None, max_length=100)


