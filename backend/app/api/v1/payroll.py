
from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from app.core.audit import log_audit_event
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, status
from pymongo.errors import DuplicateKeyError

from app.core.database import get_database
from app.core.dependencies import AdminOrHRUser, CurrentUser
from app.models.payroll import Payroll
from app.schemas.payroll import (
    PayrollGenerateRequest,
    PayrollListResponse,
    PayrollResponse,
)

router = APIRouter(prefix="/payroll", tags=["Payroll"])

WEEKEND_DAYS = {5, 6}


async def ensure_payroll_indexes(database: Any) -> None:
    """Enforce one payroll record per employee per month."""
    await database["payroll"].create_index(
        [("employee_id", 1), ("payroll_month", 1)],
        unique=True,
        name="unique_employee_payroll_month",
    )
    await database["payroll"].create_index(
        [("payroll_month", -1)],
        name="payroll_month_desc",
    )


def payroll_response(document: dict) -> PayrollResponse:
    """Convert a MongoDB document into the payroll response schema."""
    return PayrollResponse(
        id=str(document["_id"]),
        employee_id=str(document["employee_id"]),
        payroll_month=document["payroll_month"],
        basic_salary=document["basic_salary"],
        hra=document["hra"],
        medical_allowance=document["medical_allowance"],
        gross_salary=document["gross_salary"],
        working_days=document["working_days"],
        present_days=document["present_days"],
        absent_days=document["absent_days"],
        half_days=document["half_days"],
        unpaid_leave_days=document["unpaid_leave_days"],
        absent_deduction=document["absent_deduction"],
        half_day_deduction=document["half_day_deduction"],
        unpaid_leave_deduction=document["unpaid_leave_deduction"],
        total_deductions=document["total_deductions"],
        net_salary=document["net_salary"],
        status=document["status"],
        finalized_by=(
            str(document["finalized_by"])
            if document.get("finalized_by")
            else None
        ),
        finalized_at=document.get("finalized_at"),
        created_at=document.get("created_at"),
        updated_at=document.get("updated_at"),
    )


def mongo_date(value: date) -> datetime:
    """Convert a date into UTC midnight for MongoDB date queries."""
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def date_value(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value


def month_bounds(month_text: str) -> tuple[date, date]:
    year, month = map(int, month_text.split("-"))
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


async def get_employee(database: Any, employee_id: ObjectId) -> dict:
    employee = await database["employees"].find_one({"_id": employee_id})

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee record not found.",
        )

    if employee.get("employment_status") != "Active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payroll generation requires an active employee.",
        )

    return employee


async def get_holidays(
    database: Any,
    employee: dict,
    start_date: date,
    end_date: date,
) -> set[date]:
    query = {
        "is_active": True,
        "holiday_date": {
            "$gte": mongo_date(start_date),
            "$lte": mongo_date(end_date),
        },
        "$or": [
            {"department_ids": {"$exists": False}},
            {"department_ids": []},
        ],
    }

    if employee.get("department_id") is not None:
        query["$or"].append(
            {"department_ids": employee["department_id"]}
        )

    documents = await database["holidays"].find(query).to_list(length=None)

    return {
        date_value(document["holiday_date"])
        for document in documents
    }


async def count_month_working_days(
    database: Any,
    employee: dict,
    start_date: date,
    end_date: date,
) -> int:
    holidays = await get_holidays(database, employee, start_date, end_date)
    total = 0
    current = start_date

    while current <= end_date:
        if current.weekday() not in WEEKEND_DAYS and current not in holidays:
            total += 1
        current += timedelta(days=1)

    return total


async def approved_unpaid_leave_days(
    database: Any,
    employee_id: ObjectId,
    start_date: date,
    end_date: date,
    holidays: set[date],
) -> float:
    """Count approved Unpaid leave days overlapping the payroll month."""
    documents = await database["leave_requests"].find(
        {
            "employee_id": employee_id,
            "status": "Approved",
            "leave_type": "Unpaid",
            "start_date": {"$lte": mongo_date(end_date)},
            "end_date": {"$gte": mongo_date(start_date)},
        }
    ).to_list(length=None)

    total = 0

    for document in documents:
        leave_start = max(date_value(document["start_date"]), start_date)
        leave_end = min(date_value(document["end_date"]), end_date)
        current = leave_start

        while current <= leave_end:
            if (
                current.weekday() not in WEEKEND_DAYS
                and current not in holidays
            ):
                total += 1
            current += timedelta(days=1)

    return float(total)


async def generate_employee_payroll(
    database: Any,
    employee: dict,
    payroll_month: str,
) -> dict:
    start_date, end_date = month_bounds(payroll_month)
    employee_id = employee["_id"]

    existing = await database["payroll"].find_one(
        {
            "employee_id": employee_id,
            "payroll_month": payroll_month,
        }
    )

    if existing:
        if existing.get("status") == "Finalized":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Payroll for employee {employee_id} and "
                    f"{payroll_month} is finalized and locked."
                ),
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Payroll for employee {employee_id} and "
                f"{payroll_month} already exists."
            ),
        )

    basic_salary = float(employee.get("basic_salary", 0))

    if basic_salary <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Employee {employee_id} must have a positive basic salary."
            ),
        )

    holidays = await get_holidays(
        database, employee, start_date, end_date
    )
    working_days = await count_month_working_days(
        database, employee, start_date, end_date
    )

    if working_days <= 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No working days exist in this payroll month.",
        )

    attendance_docs = await database["attendance"].find(
        {
            "employee_id": employee_id,
            "attendance_date": {
                "$gte": start_date.isoformat(),
                "$lte": end_date.isoformat(),
            },
        }
    ).to_list(length=None)

    attendance_by_date = {
        document["attendance_date"]: document
        for document in attendance_docs
    }

    present_days = 0.0
    absent_days = 0.0
    half_days = 0.0

    current = start_date
    while current <= end_date:
        if (
            current.weekday() in WEEKEND_DAYS
            or current in holidays
        ):
            current += timedelta(days=1)
            continue

        attendance = attendance_by_date.get(current.isoformat())

        if attendance is None or attendance.get("status") == "Absent":
            absent_days += 1
        elif attendance.get("status") == "HalfDay":
            half_days += 1
            present_days += 0.5
        elif attendance.get("status") in {
            "Present",
            "Late",
            "MissingCheckout",
        }:
            present_days += 1

        current += timedelta(days=1)

    unpaid_days = await approved_unpaid_leave_days(
        database,
        employee_id,
        start_date,
        end_date,
        holidays,
    )

    # Avoid double-charging days already classified as absent.
    unpaid_days = min(unpaid_days, absent_days)

    hra = round(basic_salary * 0.40, 2)
    medical_allowance = round(basic_salary * 0.10, 2)
    gross_salary = round(basic_salary + hra + medical_allowance, 2)
    per_day_gross = gross_salary / working_days

    # Unpaid leave is classified as a separate deduction.
    absent_chargeable = max(0.0, absent_days - unpaid_days)
    absent_deduction = round(per_day_gross * absent_chargeable, 2)
    half_day_deduction = round(per_day_gross * 0.5 * half_days, 2)
    unpaid_leave_deduction = round(per_day_gross * unpaid_days, 2)

    total_deductions = round(
        absent_deduction
        + half_day_deduction
        + unpaid_leave_deduction,
        2,
    )
    net_salary = round(max(0.0, gross_salary - total_deductions), 2)

    now = datetime.now(timezone.utc)

    payroll = Payroll(
        employee_id=employee_id,
        payroll_month=payroll_month,
        basic_salary=round(basic_salary, 2),
        hra=hra,
        medical_allowance=medical_allowance,
        gross_salary=gross_salary,
        working_days=working_days,
        present_days=present_days,
        absent_days=absent_days,
        half_days=half_days,
        unpaid_leave_days=unpaid_days,
        absent_deduction=absent_deduction,
        half_day_deduction=half_day_deduction,
        unpaid_leave_deduction=unpaid_leave_deduction,
        total_deductions=total_deductions,
        net_salary=net_salary,
        status="Draft",
    )

    document = payroll.model_dump(
        by_alias=True,
        mode="python",
        exclude_none=True,
    )
    document["created_at"] = now
    document["updated_at"] = now

    try:
        result = await database["payroll"].insert_one(document)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payroll for this employee and month already exists.",
        ) from exc

    return await database["payroll"].find_one({"_id": result.inserted_id})


@router.post(
    "/generate",
    response_model=PayrollListResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_payroll(
    payload: PayrollGenerateRequest,
    current_user: CurrentUser,
):
    """Generate draft payroll for active employees. Admin only."""
    if current_user.get("role") != "Admin":
        database = get_database()

        await log_audit_event(
            database=database,
            actor=current_user,
            action="PAYROLL_GENERATION_DENIED",
            target_type="payroll",
            details={
                "payroll_month": payload.payroll_month,
                "reason": "Insufficient permissions",
            },
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admin can generate payroll.",
        )

    database = get_database()
    await ensure_payroll_indexes(database)

    employees = await database["employees"].find(
        {"employment_status": "Active"}
    ).to_list(length=None)

    results = []

    
    for employee in employees:
        results.append(
            await generate_employee_payroll(
                database,
                employee,
                payload.payroll_month,
            )
        )

    await log_audit_event(
        database=database,
        actor=current_user,
        action="PAYROLL_GENERATED",
        target_type="payroll",
        details={
            "payroll_month": payload.payroll_month,
            "employees_processed": len(results),
            "payroll_ids": [str(doc["_id"]) for doc in results],
        },
    )


    return PayrollListResponse(
        items=[payroll_response(doc) for doc in results],
        total=len(results),
        page=1,
        page_size=max(1, len(results)),
    )


@router.get(
    "/my",
    response_model=PayrollListResponse,
)
async def my_payroll(
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Employee can see only their own payslips."""
    if current_user.get("role") != "Employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for employee accounts.",
        )

    employee_id = current_user.get("employee_id")

    if not employee_id or not ObjectId.is_valid(str(employee_id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not linked to an employee record.",
        )

    database = get_database()
    collection = database["payroll"]
    query = {"employee_id": ObjectId(str(employee_id))}

    total = await collection.count_documents(query)
    documents = await (
        collection.find(query)
        .sort("payroll_month", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list(length=page_size)
    )

    return PayrollListResponse(
        items=[payroll_response(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "",
    response_model=PayrollListResponse,
)
async def list_payroll(
    current_user: AdminOrHRUser,
    payroll_month: str | None = Query(
        default=None,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
    ),
    employee_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Admin/HR can list payroll records."""
    query: dict = {}

    if payroll_month:
        query["payroll_month"] = payroll_month

    if employee_id:
        if not ObjectId.is_valid(employee_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid employee ID.",
            )
        query["employee_id"] = ObjectId(employee_id)

    database = get_database()
    collection = database["payroll"]
    total = await collection.count_documents(query)

    documents = await (
        collection.find(query)
        .sort("payroll_month", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list(length=page_size)
    )

    return PayrollListResponse(
        items=[payroll_response(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch(
    "/{payroll_id}/finalize",
    response_model=PayrollResponse,
)
async def finalize_payroll(
    payroll_id: str,
    current_user: CurrentUser,
):
    """Only Admin can finalize payroll. Finalized records are locked."""
    if current_user.get("role") != "Admin":
        database = get_database()

        await log_audit_event(
            database=database,
            actor=current_user,
            action="PAYROLL_FINALIZATION_DENIED",
            target_type="payroll",
            target_id=payroll_id,
            details={
                "reason": "Insufficient permissions",
            },
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admin can finalize payroll.",
        )

    if not ObjectId.is_valid(payroll_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid payroll ID.",
        )

    database = get_database()
    collection = database["payroll"]

    result = await collection.update_one(
        {
            "_id": ObjectId(payroll_id),
            "status": "Draft",
        },
        {
            "$set": {
                "status": "Finalized",
                "finalized_by": ObjectId(str(current_user["_id"])),
                "finalized_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    if result.modified_count != 1:
        record = await collection.find_one(
            {"_id": ObjectId(payroll_id)}
        )

        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payroll record not found.",
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payroll is already finalized or cannot be finalized.",
        )

    saved = await collection.find_one({"_id": ObjectId(payroll_id)})

    await log_audit_event(
        database=database,
        actor=current_user,
        action="PAYROLL_FINALIZED",
        target_type="payroll",
        target_id=payroll_id,
        details={
            "employee_id": str(saved["employee_id"]),
            "payroll_month": saved["payroll_month"],
            "net_salary": saved["net_salary"],
            "status": saved["status"],
        },
    )

    return payroll_response(saved)
