
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models.documents import DocumentModel, PyObjectId


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


class Attendance(DocumentModel):
    """Attendance record for one employee on one calendar day."""

    employee_id: PyObjectId

    # ISO date string (YYYY-MM-DD) avoids BSON date-encoding issues.
    attendance_date: str = Field(
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )

    check_in_at: datetime
    check_out_at: datetime | None = None

    status: AttendanceStatus = "Present"
    source: AttendanceSource = "web"

    check_in_latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
    )
    check_in_longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
    )
    gps_accuracy_m: float | None = Field(
        default=None,
        gt=0,
        le=100,
    )

    notes: str | None = Field(
        default=None,
        max_length=1000,
    )
