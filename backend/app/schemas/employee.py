
from typing import Literal
from datetime import date

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


EmploymentStatus = Literal[
    "Active", "OnLeave", "Resigned", "Terminated"
]


class EmployeeCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    employee_code: str = Field(min_length=1, max_length=120)
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)

    department_id: str
    designation_id: str
    manager_id: str | None = None

    joining_date: date
    employment_status: EmploymentStatus = "Active"
    basic_salary: float = Field(gt=0, le=100_000_000)

    @field_validator("employee_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower()


class EmployeeUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    first_name: str | None = Field(default=None, min_length=1, max_length=120)
    last_name: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)

    department_id: str | None = None
    designation_id: str | None = None
    manager_id: str | None = None

    joining_date: date | None = None
    employment_status: EmploymentStatus | None = None
    basic_salary: float | None = Field(
        default=None, gt=0, le=100_000_000
    )

    # Admin/HR can activate or deactivate an employee.
    is_active: bool | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(
        cls, value: EmailStr | None
    ) -> str | None:
        return str(value).lower() if value else value


class EmployeeResponse(BaseModel):
    id: str
    employee_code: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None = None
    department_id: str
    designation_id: str
    manager_id: str | None = None
    joining_date: date
    employment_status: EmploymentStatus
    is_active: bool = True
    basic_salary: float
    created_at: str | None = None
    updated_at: str | None = None


class EmployeeListResponse(BaseModel):
    items: list[EmployeeResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
