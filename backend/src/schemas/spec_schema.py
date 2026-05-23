"""Schemas for specification entities"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SpecSchema(BaseModel):
    id: Optional[int] = None
    spec_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)  # BRD, PRD, SRS, etc.
    version: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = Field(None, max_length=50)  # Draft/Approved
    file_url: Optional[str] = Field(None, max_length=1000)
    created_by: Optional[str] = Field(None, max_length=100)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SpecCreateSchema(BaseModel):
    spec_id: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    version: Optional[str] = None
    status: Optional[str] = None
    file_url: Optional[str] = None


class SpecUpdateSchema(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    version: Optional[str] = None
    status: Optional[str] = None
    file_url: Optional[str] = None



