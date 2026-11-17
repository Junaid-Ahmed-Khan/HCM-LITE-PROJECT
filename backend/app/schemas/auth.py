
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


class RegisterAdminRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    company_name: str = Field(min_length=1, max_length=120)
    company_email: EmailStr | None = None
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("email", "company_email")
    @classmethod
    def normalize_email(cls, value):
        return str(value).lower() if value else value

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 UTF-8 bytes.")
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=1, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return str(value).lower()


class HRAccountCreateRequest(BaseModel):
    """Create login credentials for an HR user."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    email: EmailStr
    initial_password: str = Field(min_length=8, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return str(value).lower()

    @field_validator("initial_password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 UTF-8 bytes.")
        return value


class EmployeeAccountCreateRequest(BaseModel):
    """Create login credentials for an existing employee."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    employee_id: str = Field(min_length=24, max_length=24)
    initial_password: str = Field(min_length=8, max_length=72)

    @field_validator("employee_id")
    @classmethod
    def validate_employee_id(cls, value: str) -> str:
        from bson import ObjectId

        if not ObjectId.is_valid(value):
            raise ValueError("Invalid employee ID.")
        return value

    @field_validator("initial_password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 UTF-8 bytes.")
        return value


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("current_password", "new_password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 UTF-8 bytes.")
        return value


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    role: Literal["Admin", "HR", "Employee"]
    is_active: bool
    employee_id: str | None = None


class AuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserPublic


class MessageResponse(BaseModel):
    message: str
