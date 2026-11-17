
from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.models.documents import DocumentModel, PyObjectId


LeaveStatus = Literal[
    "Pending",
    "Approved",
    "Rejected",
    "Cancelled",
]

LeaveRequestType = Literal[
    "Annual",
    "Sick",
    "Casual",
    "Unpaid",
]


class LeaveRequest(DocumentModel):
    """Leave application submitted by an employee."""

    employee_id: PyObjectId

    leave_type: LeaveRequestType

    start_date: date
    end_date: date

    # Calculated by the backend, excluding weekends and holidays.
    total_days: float = Field(gt=0)

    reason: str = Field(min_length=3, max_length=1000)

    status: LeaveStatus = "Pending"

    reviewed_by: PyObjectId | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = Field(default=None, max_length=1000)
