
from datetime import datetime
from zoneinfo import ZoneInfo

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.core.database import get_database
from app.core.dependencies import AdminOrHRUser, CurrentUser


router = APIRouter(prefix="/dashboards", tags=["Dashboards"])

PAKISTAN_TZ = ZoneInfo("Asia/Karachi")


def current_local_date():
    return datetime.now(PAKISTAN_TZ).date().isoformat()


def current_payroll_month():
    return datetime.now(PAKISTAN_TZ).strftime("%Y-%m")


def to_object_id(value):
    if isinstance(value, ObjectId):
        return value

    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)

    return None


@router.get("/admin-summary")
async def get_admin_dashboard(
    current_user: AdminOrHRUser,
    database=Depends(get_database),
):
    """Return company-wide dashboard statistics for Admin and HR."""

    today = current_local_date()
    payroll_month = current_payroll_month()

    total_employees = await database["employees"].count_documents({})
    active_employees = await database["employees"].count_documents(
        {"is_active": True}
    )

    attendance_today = await database["attendance"].count_documents(
        {"attendance_date": today}
    )

    present_today = await database["attendance"].count_documents(
        {
            "attendance_date": today,
            "status": {"$in": ["Present", "Late", "MissingCheckout"]},
        }
    )

    late_today = await database["attendance"].count_documents(
        {"attendance_date": today, "status": "Late"}
    )

    half_day_today = await database["attendance"].count_documents(
        {"attendance_date": today, "status": "HalfDay"}
    )

    missing_checkout_today = await database["attendance"].count_documents(
        {"attendance_date": today, "status": "MissingCheckout"}
    )

    pending_leaves = await database["leave_requests"].count_documents(
        {"status": "Pending"}
    )

    draft_payrolls = await database["payrolls"].count_documents(
        {"payroll_month": payroll_month, "status": "Draft"}
    )

    finalized_payrolls = await database["payrolls"].count_documents(
        {"payroll_month": payroll_month, "status": "Finalized"}
    )

    return {
        "dashboard": "admin",
        "date": today,
        "payroll_month": payroll_month,
        "employees": {
            "total": total_employees,
            "active": active_employees,
        },
        "attendance": {
            "records_today": attendance_today,
            "present_or_late": present_today,
            "late": late_today,
            "half_day": half_day_today,
            "missing_checkout": missing_checkout_today,
        },
        "leave_requests": {
            "pending": pending_leaves,
        },
        "payroll": {
            "draft": draft_payrolls,
            "finalized": finalized_payrolls,
        },
    }


@router.get("/employee-summary")
async def get_employee_dashboard(
    current_user: CurrentUser,
    database=Depends(get_database),
):
    """Return dashboard information for the logged-in employee only."""

    if current_user.get("role") != "Employee":
        raise HTTPException(
            status_code=403,
            detail="This dashboard is available to employees only.",
        )

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

    attendance_today = await database["attendance"].find_one(
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

    attendance_data = None
    if attendance_today:
        attendance_data = {
            "date": attendance_today.get("attendance_date"),
            "status": attendance_today.get("status"),
            "check_in_at": attendance_today.get("check_in_at"),
            "check_out_at": attendance_today.get("check_out_at"),
        }

    payroll_data = None
    if latest_payroll:
        payroll_data = {
            "payroll_month": latest_payroll.get("payroll_month"),
            "gross_salary": latest_payroll.get("gross_salary"),
            "total_deductions": latest_payroll.get("total_deductions"),
            "net_salary": latest_payroll.get("net_salary"),
            "status": latest_payroll.get("status"),
        }

    return {
        "dashboard": "employee",
        "date": today,
        "attendance_today": attendance_data,
        "leave_requests": leave_counts,
        "latest_payroll": payroll_data,
    }
