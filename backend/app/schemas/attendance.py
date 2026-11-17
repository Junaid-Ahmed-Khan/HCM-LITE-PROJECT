
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AttendanceStatus = Literal[
    "Present",
    "Late",
    "HalfDay",
    "MissingCheckout",
    "Absent",
]

AttendanceSource = Literal[
    "web",
    "camera",
    "hr_correction",
]


class CheckInRequest(BaseModel):
    """Optional location details for a check-in request."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["web", "camera"] = "web"

    latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
    )
    longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
    )
    gps_accuracy_m: float | None = Field(
        default=None,
        gt=0,
        le=100,
    )
    # Required by the backend when source="camera".
    face_image_base64: str | None = Field(
        default=None,
        min_length=100,
        max_length=7_000_000,
    )


class CheckOutRequest(BaseModel):
    """No client-supplied timestamp is accepted."""

    model_config = ConfigDict(extra="forbid")


class AttendanceResponse(BaseModel):
    """Public representation of an attendance record."""

    id: str
    employee_id: str
    attendance_date: str
    check_in_at: datetime
    check_out_at: datetime | None = None
    status: AttendanceStatus
    source: AttendanceSource
    check_in_latitude: float | None = None
    check_in_longitude: float | None = None
    gps_accuracy_m: float | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AttendanceListResponse(BaseModel):
    items: list[AttendanceResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
