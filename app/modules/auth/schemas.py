from pydantic import BaseModel, EmailStr

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenData(BaseModel):
    email: EmailStr | None = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str