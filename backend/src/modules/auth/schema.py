from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, EmailStr

class LoginRequest(BaseModel):
    """Request payload for logging in."""
    email: EmailStr = Field(..., example="admin@sentinellog.ai")
    password: str = Field(..., min_length=8, max_length=128)

class TokenPayload(BaseModel):
    """Schema for decoded JWT token payload claims."""
    sub: str = Field(..., description="User ID (Subject)", example="9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d")
    exp: datetime = Field(..., description="Expiration timestamp")
    type: str = Field(..., description="Token type: access", example="access")

class TokenResponse(BaseModel):
    """Response returned upon successful login or token refresh."""
    access_token: str = Field(..., example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    token_type: str = Field(default="bearer", example="bearer")
    expires_in: int = Field(..., description="Access token expiration in seconds", example=900)

class RefreshTokenInDB(BaseModel):
    """Database record representation of a refresh token."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    token_hash: str
    expires_at: datetime
    revoked: bool
    created_at: datetime