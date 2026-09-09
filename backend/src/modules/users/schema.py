from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class UserBase(BaseModel):
    """Base shared attributes for User."""
    username: str = Field(..., min_length=3, max_length=50, example="admin_sec")
    email: EmailStr = Field(..., example="admin@sentinellog.ai")

class UserCreate(UserBase):
    """Schema for registering or creating a new User."""
    username: Optional[str] = Field(default=None, min_length=3, max_length=50, example="admin_sec2")
    email: Optional[EmailStr] = Field(default=None, example="new_admin@sentinellog.ai")
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)

class UserUpdate(BaseModel):
    """Schema for updating User properties."""
    username: Optional[str] = Field(default=None, min_length=3, max_length=50, example="admin_sec2")
    email: Optional[EmailStr] = Field(default=None, example="new_admin@sentinellog.ai")
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    is_active: Optional[bool] = Field(default=None)

class UserResponse(UserBase):
    """Schema for returning public User data (excludes password)."""
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., example="9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d")
    is_active: bool = Field(default=True, example=True)
    created_at: datetime

class ChangePassword(BaseModel):
    """Schema for changing a user's password."""
    current_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_new_password: str = Field(..., min_length=8, max_length=128)

class UserInDB(UserResponse):
    """Internal schema including password hash for authentication workflows."""
    hashed_password: str
