from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class UserSchema(BaseModel):
    """Schema for user data validation"""
    id: Optional[int] = None
    username: str = Field(..., min_length=1, max_length=50)
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    role: Optional[str] = Field(None, max_length=20)
    password_hash: Optional[str] = None  # Never expose this in responses
    secret_key_hash: Optional[str] = None  # Never expose this in responses
    git_token_encrypted: Optional[str] = None  # Encrypted Git token, never expose
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserCreateSchema(BaseModel):
    """Schema for creating a new user"""
    username: str = Field(..., min_length=1, max_length=50)
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=6, max_length=100)
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    role: Optional[str] = Field(None, max_length=20)
    secret_key: str = Field(..., min_length=3, max_length=50)
    git_token: Optional[str] = Field(None, min_length=10, max_length=200)  # Optional Git access token


class UserUpdateSchema(BaseModel):
    """Schema for updating user data"""
    username: Optional[str] = Field(None, min_length=1, max_length=50)
    email: Optional[str] = Field(None, pattern=r'^[^@]+@[^@]+\.[^@]+$')
    password: Optional[str] = Field(None, min_length=6, max_length=100)
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    role: Optional[str] = Field(None, max_length=20)


class LoginSchema(BaseModel):
    """Schema for user login"""
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)  # Allow shorter passwords for login (signup still requires 6+)
