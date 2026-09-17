from pydantic import BaseModel, EmailStr, Field


class Register_Organization(BaseModel):
    organization_name: str = Field(min_length=2, max_length=255)
    organization_email: EmailStr
    organization_phone: str = Field(min_length=10, max_length=15)
    organization_hashed_password: str = Field(min_length=8, max_length=255)
    is_active:bool | None=None
    is_verified:bool | None=None

class Login_Organization(BaseModel):
    organization_email: EmailStr
    organization_hashed_password: str 

class Change_Organization_Password(BaseModel):
    old_password:str
    new_password:str
    confirm_new_password:str

class Get_Organization_Profile(BaseModel):
    organization_name: str 
    organization_email: EmailStr
    organization_phone: str
    is_active:bool | None=None
    is_verified:bool | None=None

class  Update_Organization(BaseModel):
    organization_name: str 
    organization_email: EmailStr
    organization_phone: str

class Delete_Organization(BaseModel):
    organization_email: EmailStr

class Create_Admin(BaseModel):
    admin_name: str
    admin_email: EmailStr
    admin_phone: str
    admin_password: str
