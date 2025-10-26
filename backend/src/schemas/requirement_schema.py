"""Schemas for requirements data validation"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class RequirementSchema(BaseModel):
    """Schema for requirement data validation"""
    id: Optional[int] = None
    requirement_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    given: Optional[str] = None  # Given context
    when: Optional[str] = None  # When action
    then: Optional[str] = None  # Then expected result
    priority: Optional[str] = Field(None, max_length=20)  # High, Medium, Low
    status: Optional[str] = Field(None, max_length=20)  # Draft, Active, Completed, Archived
    assignee: Optional[str] = Field(None, max_length=100)
    tags: Optional[str] = None  # Comma-separated tags
    created_by: Optional[str] = Field(None, max_length=100)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RequirementCreateSchema(BaseModel):
    """Schema for creating a new requirement"""
    requirement_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    given: Optional[str] = None
    when: Optional[str] = None
    then: Optional[str] = None
    priority: Optional[str] = Field(None, max_length=20)
    status: Optional[str] = Field('Draft', max_length=20)
    assignee: Optional[str] = Field(None, max_length=100)
    tags: Optional[str] = None


class RequirementUpdateSchema(BaseModel):
    """Schema for updating requirement data"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    given: Optional[str] = None
    when: Optional[str] = None
    then: Optional[str] = None
    priority: Optional[str] = Field(None, max_length=20)
    status: Optional[str] = Field(None, max_length=20)
    assignee: Optional[str] = Field(None, max_length=100)
    tags: Optional[str] = None

