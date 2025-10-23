from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class DatabaseQuerySchema(BaseModel):
    """Schema for database query requests"""
    query: str = Field(..., min_length=1)
    environment: Optional[str] = Field("default", max_length=50)


class DatabaseInfoSchema(BaseModel):
    """Schema for database information response"""
    name: str
    size: int
    last_modified: datetime
    tables: List[str]
    row_counts: Dict[str, int]


class ErrorResponseSchema(BaseModel):
    """Schema for error responses"""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None


class SuccessResponseSchema(BaseModel):
    """Schema for success responses"""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None
