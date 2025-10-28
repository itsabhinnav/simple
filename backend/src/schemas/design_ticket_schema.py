"""Schemas for design tickets data validation"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class DesignTicketSchema(BaseModel):
    """Schema for design ticket data validation"""
    id: Optional[int] = None
    design_ticket_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    design_type: Optional[str] = Field(None, max_length=100)  # Sequence Diagram, Use Case, State Flow, etc.
    diagram_type: Optional[str] = Field(None, max_length=100)  # More specific type
    image_url: Optional[str] = Field(None, max_length=1000)  # Path to uploaded image
    priority: Optional[str] = Field(None, max_length=20)  # High, Medium, Low
    status: Optional[str] = Field(None, max_length=20)  # Draft, Review, Approved, Archived
    requirement_id: Optional[str] = Field(None, max_length=500)  # Linked requirement ID
    assignee: Optional[str] = Field(None, max_length=100)
    tags: Optional[str] = None  # Comma-separated tags
    created_by: Optional[str] = Field(None, max_length=100)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DesignTicketCreateSchema(BaseModel):
    """Schema for creating a new design ticket"""
    design_ticket_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    design_type: Optional[str] = Field(None, max_length=100)
    diagram_type: Optional[str] = Field(None, max_length=100)
    image_url: Optional[str] = Field(None, max_length=1000)
    priority: Optional[str] = Field(None, max_length=20)
    status: Optional[str] = Field('Draft', max_length=20)
    requirement_id: Optional[str] = Field(None, max_length=500)
    assignee: Optional[str] = Field(None, max_length=100)
    tags: Optional[str] = None


class DesignTicketUpdateSchema(BaseModel):
    """Schema for updating design ticket data"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    design_type: Optional[str] = Field(None, max_length=100)
    diagram_type: Optional[str] = Field(None, max_length=100)
    image_url: Optional[str] = Field(None, max_length=1000)
    priority: Optional[str] = Field(None, max_length=20)
    status: Optional[str] = Field(None, max_length=20)
    requirement_id: Optional[str] = Field(None, max_length=500)
    assignee: Optional[str] = Field(None, max_length=100)
    tags: Optional[str] = None

