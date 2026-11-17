
from datetime import date, datetime, timezone
from typing import Annotated, Literal

from bson import ObjectId
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    PlainSerializer,
    StringConstraints,
    WithJsonSchema,
    field_validator,
)


# -------------------------------------------------------------------
# Shared types
# -------------------------------------------------------------------

def validate_object_id(value):
    """Accept a BSON ObjectId or a valid 24-character hex string."""
    if isinstance(value, ObjectId):
        return value

    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)

    raise ValueError("Invalid MongoDB ObjectId.")


PyObjectId = Annotated[
    ObjectId,
    BeforeValidator(validate_object_id),
    PlainSerializer(str, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string"}),
]

NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=120),
]


def utc_now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


class DocumentModel(BaseModel):
    """Base model shared by MongoDB documents."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    id: PyObjectId = Field(
        default_factory=ObjectId,
        alias="_id",
    )

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


# -------------------------------------------------------------------
# 1. User
# -------------------------------------------------------------------

class User(DocumentModel):
    """Authentication account and authorization information."""

    email: EmailStr
    password_hash: str = Field(min_length=1, repr=False)

    role: Literal["Admin", "HR", "Employee"]

    is_active: bool = True

    # References the linked Employee document, if applicable.
    employee_id: PyObjectId | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return str(value).lower()


# -------------------------------------------------------------------
# 2. Employee
# -------------------------------------------------------------------


class Employee(DocumentModel):
    """Employment and organizational information."""

    employee_code: NonEmptyString
    first_name: NonEmptyString
    last_name: NonEmptyString
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)

    department_id: PyObjectId
    designation_id: PyObjectId
    manager_id: PyObjectId | None = None

    joining_date: date
    employment_status: Literal[
        "Active",
        "OnLeave",
        "Resigned",
        "Terminated",
    ] = "Active"

    basic_salary: float = Field(gt=0, le=100_000_000)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).lower()

    @field_validator("employee_code")
    @classmethod
    def normalize_employee_code(cls, value: str) -> str:
        return value.strip().upper()

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"



# -------------------------------------------------------------------
# 3. Department
# -------------------------------------------------------------------

class Department(DocumentModel):
    """Company department."""

    name: NonEmptyString
    code: NonEmptyString
    description: str | None = Field(default=None, max_length=1000)

    # Optional employee reference for the department head.
    head_employee_id: PyObjectId | None = None

    is_active: bool = True


# -------------------------------------------------------------------
# 4. Designation
# -------------------------------------------------------------------

class Designation(DocumentModel):
    """Job title or designation within a department."""

    name: NonEmptyString
    code: NonEmptyString

    department_id: PyObjectId

    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = True


# -------------------------------------------------------------------
# 5. Company settings
# -------------------------------------------------------------------

class CompanySettings(DocumentModel):
    """
    Company-wide configuration.

    The setup workflow will create the initial settings document.
    Office coordinates are optional until configured by Admin.
    """

    company_name: NonEmptyString
    company_email: EmailStr | None = None
    company_phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=500)

    # Office location used for GPS geofencing.
    office_latitude: float | None = Field(default=None, ge=-90, le=90)
    office_longitude: float | None = Field(default=None, ge=-180, le=180)
    office_radius_meters: float = Field(default=100, gt=0, le=10000)

    # Attendance policy.
    office_start_time: str = "09:00"
    grace_period_minutes: int = Field(default=15, ge=0, le=180)
    half_day_hours: float = Field(default=5, gt=0, le=24)

    # Saturday = 5 and Sunday = 6 in Python's weekday convention.
    weekend_days: list[int] = Field(default_factory=lambda: [5, 6])

    @field_validator("company_email")
    @classmethod
    def normalize_company_email(cls, value):
        return str(value).lower() if value else value

    @field_validator("office_start_time")
    @classmethod
    def validate_office_start_time(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError(
                "Office start time must use HH:MM in 24-hour format."
            ) from exc
        return value

    @field_validator("weekend_days")
    @classmethod
    def validate_weekend_days(cls, value: list[int]) -> list[int]:
        if any(day < 0 or day > 6 for day in value):
            raise ValueError("Weekend days must be integers from 0 to 6.")
        if len(value) != len(set(value)):
            raise ValueError("Weekend days cannot contain duplicates.")
        return value


# -------------------------------------------------------------------
# 6. Holiday
# -------------------------------------------------------------------

class Holiday(DocumentModel):
    """Company holiday calendar entry."""

    name: NonEmptyString
    holiday_date: date

    description: str | None = Field(default=None, max_length=1000)

    # Optional: restrict the holiday to selected departments.
    department_ids: list[PyObjectId] = Field(default_factory=list)

    is_active: bool = True


# -------------------------------------------------------------------
# 7. Leave type
# -------------------------------------------------------------------

class LeaveType(DocumentModel):
    """
    Configurable leave category.

    quota_days=None means unlimited leave, suitable for Unpaid leave.
    The setup workflow will create the organization's leave types.
    """

    name: NonEmptyString
    code: NonEmptyString

    quota_days: float | None = Field(default=None, ge=0)
    is_paid: bool = True

    # Whether unused leave can carry over to the next leave year.
    allow_carry_forward: bool = False

    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = True
