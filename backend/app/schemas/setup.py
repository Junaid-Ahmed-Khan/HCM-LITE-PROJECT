from datetime import datetime
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


class CompanySettingsUpdate(BaseModel):
    """Fields an Admin may update. All fields are optional."""

    model_config = ConfigDict(str_strip_whitespace=True)

    company_name: str | None = Field(
        default=None, min_length=1, max_length=120
    )
    company_email: EmailStr | None = None
    company_phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=500)

    office_latitude: float | None = Field(
        default=None, ge=-90, le=90
    )
    office_longitude: float | None = Field(
        default=None, ge=-180, le=180
    )
    office_radius_meters: float | None = Field(
        default=None, gt=0, le=10000
    )

    office_start_time: str | None = None
    grace_period_minutes: int | None = Field(
        default=None, ge=0, le=180
    )
    half_day_hours: float | None = Field(
        default=None, gt=0, le=24
    )
    weekend_days: list[int] | None = None

    @field_validator("company_email")
    @classmethod
    def normalize_email(cls, value):
        return value.lower() if value else value

    @field_validator("office_start_time")
    @classmethod
    def validate_start_time(cls, value):
        if value is not None:
            from datetime import datetime

            try:
                datetime.strptime(value, "%H:%M")
            except ValueError as exc:
                raise ValueError(
                    "Office start time must use HH:MM format, such as 09:00."
                ) from exc
        return value

    @field_validator("weekend_days")
    @classmethod
    def validate_weekend_days(cls, value):
        if value is not None:
            if any(day < 0 or day > 6 for day in value):
                raise ValueError(
                    "Weekend days must be integers from 0 to 6."
                )
            if len(value) != len(set(value)):
                raise ValueError("Weekend days cannot contain duplicates.")
        return value


class CompanySettingsResponse(BaseModel):
    id: str
    company_name: str
    company_email: EmailStr | None = None
    company_phone: str | None = None
    address: str | None = None

    office_latitude: float | None = None
    office_longitude: float | None = None
    office_radius_meters: float

    office_start_time: str
    grace_period_minutes: int
    half_day_hours: float
    weekend_days: list[int]

    created_at: datetime
    updated_at: datetime


class SetupMessageResponse(BaseModel):
    message: str