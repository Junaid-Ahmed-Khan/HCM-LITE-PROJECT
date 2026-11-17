
from datetime import datetime
from zoneinfo import ZoneInfo

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.database import get_database
from app.core.dependencies import CurrentUser
from app.services.ai_assistant import answer_hr_question


router = APIRouter(prefix="/ai", tags=["AI Assistant"])

PAKISTAN_TZ = ZoneInfo("Asia/Karachi")


class AIQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


def current_local_date() -> str:
    return datetime.now(PAKISTAN_TZ).date().isoformat()


def current_payroll_month() -> str:
    return datetime.now(PAKISTAN_TZ).strftime("%Y-%m")


def to_object_id(value):
    if isinstance(value, ObjectId):
        return value

    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)

    return None


async def get_admin_hr_context(database: object) -> dict:
    """Build a limited company-wide summary for Admin and HR."""

    today = current_local_date()
    payroll_month = current_payroll_month()

    return {
        "date": today,
        "payroll_month": payroll_month,
        "employees": {
            "total": await database["employees"].count_documents({}),
            "active": await database["employees"].count_documents(
                {"is_active": True}
            ),
        },
        "attendance_today": {
            "records": await database["attendance"].count_documents(
                {"attendance_date": today}
            ),
            "present_or_late": await database["attendance"].count_documents(
                {
                    "attendance_date": today,
                    "status": {
                        "$in": ["Present", "Late", "MissingCheckout"]
                    },
                }
            ),
            "late": await database["attendance"].count_documents(
                {"attendance_date": today, "status": "Late"}
            ),
            "half_day": await database["attendance"].count_documents(
                {"attendance_date": today, "status": "HalfDay"}
            ),
            "missing_checkout": await database["attendance"].count_documents(
                {"attendance_date": today, "status": "MissingCheckout"}
            ),
        },
        "leave_requests": {
            "pending": await database["leave_requests"].count_documents(
                {"status": "Pending"}
            ),
        },
        "payroll": {
            "draft": await database["payrolls"].count_documents(
                {"payroll_month": payroll_month, "status": "Draft"}
            ),
            "finalized": await database["payrolls"].count_documents(
                {"payroll_month": payroll_month, "status": "Finalized"}
            ),
        },
    }


async def get_employee_context(
    database: object,
    current_user: dict,
) -> dict:
    """Build context using only the logged-in employee's records."""

    employee_id = to_object_id(current_user.get("employee_id"))

    if employee_id is None:
        raise HTTPException(
            status_code=404,
            detail="No employee record is linked to this account.",
        )

    employee = await database["employees"].find_one(
        {"_id": employee_id}
    )

    if employee is None:
        raise HTTPException(
            status_code=404,
            detail="Employee record not found.",
        )

    today = current_local_date()

    attendance = await database["attendance"].find_one(
        {
            "employee_id": employee_id,
            "attendance_date": today,
        }
    )

    leave_counts = {}
    for status in ["Pending", "Approved", "Rejected", "Cancelled"]:
        leave_counts[status.lower()] = (
            await database["leave_requests"].count_documents(
                {
                    "employee_id": employee_id,
                    "status": status,
                }
            )
        )

    latest_payroll = await database["payrolls"].find_one(
        {"employee_id": employee_id},
        sort=[("payroll_month", -1)],
    )

    return {
        "date": today,
        "attendance_today": (
            {
                "status": attendance.get("status"),
                "check_in_at": attendance.get("check_in_at"),
                "check_out_at": attendance.get("check_out_at"),
            }
            if attendance
            else None
        ),
        "leave_requests": leave_counts,
        "latest_payroll": (
            {
                "payroll_month": latest_payroll.get("payroll_month"),
                "status": latest_payroll.get("status"),
                "gross_salary": latest_payroll.get("gross_salary"),
                "total_deductions": latest_payroll.get(
                    "total_deductions"
                ),
                "net_salary": latest_payroll.get("net_salary"),
            }
            if latest_payroll
            else None
        ),
    }


@router.post("/ask")
async def ask_ai_assistant(
    request: AIQuestionRequest,
    current_user: CurrentUser,
    database=Depends(get_database),
):
    """Answer an HR question using data authorized for the current user."""

    role = current_user.get("role")

    if role not in {"Admin", "HR", "Employee"}:
        raise HTTPException(
            status_code=403,
            detail="Your role cannot use the AI assistant.",
        )

    question = request.question.strip()
    if not question:
        raise HTTPException(
            status_code=422,
            detail="Question cannot be empty.",
        )

    if role in {"Admin", "HR"}:
        context = await get_admin_hr_context(database)
    else:
        context = await get_employee_context(database, current_user)

    try:
        answer = await answer_hr_question(
            question=question,
            role=role,
            authorized_context=context,
        )
    except Exception:
        # Avoid exposing provider errors, API keys, or internal details.
        raise HTTPException(
            status_code=502,
            detail="The AI service could not generate an answer. Please try again.",
        )

    return {
        "answer": answer,
        "role": role,
        "date": current_local_date(),
    }
