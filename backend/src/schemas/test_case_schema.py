from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class TestCaseSchema(BaseModel):
    """Schema for test case data validation"""
    id: Optional[int] = None
    test_case_id: str = Field(..., min_length=1, max_length=100)
    reference_document: Optional[str] = Field(None, max_length=500)
    associated_requirement_id: Optional[str] = Field(None, max_length=500)
    screen_id: Optional[str] = Field(None, max_length=100)
    feature: Optional[str] = Field(None, max_length=200)
    dr_applicable_screens: Optional[str] = Field(None, max_length=1000)
    dr_id: Optional[str] = Field(None, max_length=1000)
    test_objective: Optional[str] = Field(None, max_length=1000)
    preconditions: Optional[str] = Field(None, max_length=2000)
    procedure: Optional[str] = Field(None, max_length=5000)
    expected_behavior: Optional[str] = Field(None, max_length=2000)
    test_type: Optional[str] = Field(None, max_length=50)
    region: Optional[str] = Field(None, max_length=50)
    brand: Optional[str] = Field(None, max_length=50)
    vehicle_variant: Optional[str] = Field(None, max_length=100)
    vehicle_specification: Optional[str] = Field(None, max_length=200)
    env_dependency: Optional[str] = Field(None, max_length=200)
    requirement_type: Optional[str] = Field(None, max_length=50)
    regulation: Optional[str] = Field(None, max_length=200)
    priority: Optional[str] = Field(None, max_length=10)
    testsuite_type: Optional[str] = Field(None, max_length=50)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TestCaseCreateSchema(BaseModel):
    """Schema for creating a new test case"""
    test_case_id: str = Field(..., min_length=1, max_length=100)
    reference_document: Optional[str] = Field(None, max_length=500)
    associated_requirement_id: Optional[str] = Field(None, max_length=500)
    screen_id: Optional[str] = Field(None, max_length=100)
    feature: Optional[str] = Field(None, max_length=200)
    dr_applicable_screens: Optional[str] = Field(None, max_length=1000)
    dr_id: Optional[str] = Field(None, max_length=1000)
    test_objective: Optional[str] = Field(None, max_length=1000)
    preconditions: Optional[str] = Field(None, max_length=2000)
    procedure: Optional[str] = Field(None, max_length=5000)
    expected_behavior: Optional[str] = Field(None, max_length=2000)
    test_type: Optional[str] = Field(None, max_length=50)
    region: Optional[str] = Field(None, max_length=50)
    brand: Optional[str] = Field(None, max_length=50)
    vehicle_variant: Optional[str] = Field(None, max_length=100)
    vehicle_specification: Optional[str] = Field(None, max_length=200)
    env_dependency: Optional[str] = Field(None, max_length=200)
    requirement_type: Optional[str] = Field(None, max_length=50)
    regulation: Optional[str] = Field(None, max_length=200)
    priority: Optional[str] = Field(None, max_length=10)
    testsuite_type: Optional[str] = Field(None, max_length=50)
