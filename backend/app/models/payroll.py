
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models.documents import DocumentModel, PyObjectId


PayrollStatus = Literal["Draft", "Finalized"]


class Payroll(DocumentModel):
    """Monthly payroll record for one employee."""

    employee_id: PyObjectId

    # Format: YYYY-MM
    payroll_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")

    basic_salary: float = Field(ge=0)
    hra: float = Field(ge=0)
    medical_allowance: float = Field(ge=0)
    gross_salary: float = Field(ge=0)

    working_days: int = Field(ge=0)
    present_days: float = Field(ge=0)
    absent_days: float = Field(ge=0)
    half_days: float = Field(ge=0)
    unpaid_leave_days: float = Field(ge=0)

    absent_deduction: float = Field(ge=0)
    half_day_deduction: float = Field(ge=0)
    unpaid_leave_deduction: float = Field(ge=0)
    total_deductions: float = Field(ge=0)

    net_salary: float = Field(ge=0)

    status: PayrollStatus = "Draft"

    finalized_by: PyObjectId | None = None
    finalized_at: datetime | None = None
