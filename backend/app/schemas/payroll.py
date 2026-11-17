
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PayrollStatus = Literal["Draft", "Finalized"]


class PayrollGenerateRequest(BaseModel):
    """Admin requests payroll generation for a month."""

    model_config = ConfigDict(extra="forbid")

    payroll_month: str = Field(
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="Payroll month in YYYY-MM format",
    )


class PayrollResponse(BaseModel):
    """Payroll details returned by the API."""

    id: str
    employee_id: str
    payroll_month: str

    basic_salary: float
    hra: float
    medical_allowance: float
    gross_salary: float

    working_days: int
    present_days: float
    absent_days: float
    half_days: float
    unpaid_leave_days: float

    absent_deduction: float
    half_day_deduction: float
    unpaid_leave_deduction: float
    total_deductions: float

    net_salary: float
    status: PayrollStatus

    finalized_by: str | None = None
    finalized_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PayrollListResponse(BaseModel):
    items: list[PayrollResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
