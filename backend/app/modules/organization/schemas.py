from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, model_validator

class RegisterOrganization(BaseModel):
    organization_name: str = Field(min_length=2,max_length=255)
    organization_email: EmailStr
    organization_phone: str = Field(min_length=10,max_length=15)
    password: str = Field(min_length=8,max_length=128)
    
class LoginOrganization(BaseModel):
    organization_email: EmailStr
    password: str = Field(min_length=1,max_length=128)

class ChangeOrganizationPassword(BaseModel):
    old_password: str = Field(min_length=1,max_length=128)
    new_password: str = Field(min_length=8,max_length=128)
    confirm_new_password: str = Field(min_length=8,max_length=128)

    @model_validator(mode="after")
    def validate_passwords(self):
        if self.new_password != self.confirm_new_password:
            raise ValueError("New passwords do not match")

        return self

class OrganizationProfile(BaseModel):
    unique_id: UUID
    organization_name: str
    organization_email: EmailStr
    organization_phone: str
    is_active: bool
    is_verified: bool

class UpdateOrganization(BaseModel):
    organization_name: str | None = Field(default=None,min_length=2,max_length=255)
    organization_email: EmailStr | None = None
    organization_phone: str | None = Field(default=None,min_length=10,max_length=15)


class CreateAdmin(BaseModel):
    admin_name: str = Field(min_length=3,max_length=255)
    admin_email: EmailStr
    admin_phone: str = Field(min_length=10,max_length=15)
    admin_employee_id: str = Field(min_length=1,max_length=100)
    password: str = Field(min_length=8,max_length=128)

class AdminResponse(BaseModel):
    unique_id: UUID
    admin_name: str
    admin_email: EmailStr
    admin_phone: str
    admin_employee_id: str
    is_active: bool
    is_verified: bool