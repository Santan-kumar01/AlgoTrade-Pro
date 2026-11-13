from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    """Validate user registration input."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Validate user login input."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """Return JWT access token information."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public user information returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
