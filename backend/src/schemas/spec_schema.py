"""Schemas for specification entities"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SpecSchema(BaseModel):
    id: Optional[int] = None
    spec_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=500)
    project: Optional[str] = Field(None, max_length=200)
    tags: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    version: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = Field(None, max_length=50)
    file_url: Optional[str] = Field(None, max_length=1000)
    file_name: Optional[str] = Field(None, max_length=500)
    source_url: Optional[str] = Field(None, max_length=2000)
    created_by: Optional[str] = Field(None, max_length=100)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SpecCreateSchema(BaseModel):
    spec_id: str
    title: str
    project: Optional[str] = None
    tags: Optional[str] = None
    category: Optional[str] = None
    version: Optional[str] = None
    status: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    source_url: Optional[str] = None


class SpecUpdateSchema(BaseModel):
    title: Optional[str] = None
    project: Optional[str] = None
    tags: Optional[str] = None
    category: Optional[str] = None
    version: Optional[str] = None
    status: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    source_url: Optional[str] = None
