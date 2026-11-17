
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


LeaveType = Literal["Annual", "Sick", "Casual", "Unpaid"]

LeaveStatus = Literal[
    "Pending",
    "Approved",
    "Rejected",
    "Cancelled",
]


class LeaveCreateRequest(BaseModel):
    """Fields an employee is allowed to submit."""

    model_config = ConfigDict(extra="forbid")

    leave_type: LeaveType
    start_date: date
    end_date: date
    reason: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date.")

        return self


class LeaveReviewRequest(BaseModel):
    """Fields Admin or HR can submit when reviewing leave."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["Approved", "Rejected"]
    review_note: str | None = Field(default=None, max_length=1000)


class LeaveResponse(BaseModel):
    """Leave request returned by the API."""

    id: str
    employee_id: str
    leave_type: LeaveType
    start_date: date
    end_date: date
    total_days: float
    reason: str
    status: LeaveStatus
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LeaveListResponse(BaseModel):
    items: list[LeaveResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
