from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# SAK-032: tighter than the original `^[^@]+@[^@]+\.[^@]+$` which accepted
# garbage like '@a.b' or ' x@y.z'. Still pragmatic (not full RFC 5322) but
# rejects whitespace, empty local-part, and missing TLD. For full validation
# swap to pydantic.EmailStr (requires the `email-validator` extra).
EMAIL_PATTERN = (
    r'^[a-zA-Z0-9._%+\-]+'      # local part: letters/digits/safe specials
    r'@'
    r'[a-zA-Z0-9.\-]+'           # domain labels
    r'\.[a-zA-Z]{2,63}$'         # TLD between 2 and 63 chars
)

# SAK-016: minimum password length raised from 6 to 12 across every schema.
# The audit calibrated this against a corporate baseline; tighten further
# (complexity classes, HIBP check) in the P1 hardening phase.
PASSWORD_MIN_LENGTH = 12
SECRET_KEY_MIN_LENGTH = 12


class UserSchema(BaseModel):
    """Schema for user data validation"""
    id: Optional[int] = None
    username: str = Field(..., min_length=1, max_length=50)
    email: str = Field(..., pattern=EMAIL_PATTERN, max_length=254)
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    role: Optional[str] = Field(default="user", max_length=20)
    password_hash: Optional[str] = None  # Never expose this in responses
    secret_key_hash: Optional[str] = None  # Never expose this in responses
    git_token_encrypted: Optional[str] = None  # Encrypted Git token, never expose
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserCreateSchema(BaseModel):
    """Schema for creating a new user"""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=EMAIL_PATTERN, max_length=254)
    password: str = Field(..., min_length=PASSWORD_MIN_LENGTH, max_length=128)
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    role: Optional[str] = Field(None, max_length=20)
    secret_key: str = Field(..., min_length=SECRET_KEY_MIN_LENGTH, max_length=128)
    git_token: Optional[str] = Field(None, min_length=10, max_length=200)  # Optional Git access token


class UserUpdateSchema(BaseModel):
    """Schema for updating user data"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = Field(None, pattern=EMAIL_PATTERN, max_length=254)
    password: Optional[str] = Field(None, min_length=PASSWORD_MIN_LENGTH, max_length=128)
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    role: Optional[str] = Field(None, max_length=20)


class LoginSchema(BaseModel):
    """Schema for user login.

    Allows short passwords on login (we may still have legacy accounts
    created under the old <12 char policy). Sign-up and reset enforce the
    new minimum so the population converges on the policy over time.
    """
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)
