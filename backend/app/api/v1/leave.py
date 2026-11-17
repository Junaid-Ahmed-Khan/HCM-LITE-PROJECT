
from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from app.core.audit import log_audit_event
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, status
from pymongo.errors import DuplicateKeyError

from app.core.database import get_database
from app.core.dependencies import AdminOrHRUser, CurrentUser
from app.models.leave import LeaveRequest
from app.schemas.leave import (
    LeaveCreateRequest,
    LeaveListResponse,
    LeaveResponse,
    LeaveReviewRequest,
)

router = APIRouter(prefix="/leave", tags=["Leave Management"])

LEAVE_QUOTAS = {
    "Annual": 14,
    "Sick": 8,
    "Casual": 10,
    "Unpaid": None,
}

WEEKEND_DAYS = {5, 6}


async def ensure_leave_indexes(database: Any) -> None:
    """Create indexes used by leave queries."""
    await database["leave_requests"].create_index(
        [("employee_id", 1), ("start_date", 1), ("end_date", 1)],
        name="leave_employee_dates",
    )
    await database["leave_requests"].create_index(
        [("status", 1), ("start_date", 1)],
        name="leave_status_start_date",
    )


def leave_response(document: dict) -> LeaveResponse:
    """Convert a MongoDB leave document into an API response."""
    return LeaveResponse(
        id=str(document["_id"]),
        employee_id=str(document["employee_id"]),
        leave_type=document["leave_type"],
        start_date=document["start_date"].date()
        if isinstance(document["start_date"], datetime)
        else document["start_date"],
        end_date=document["end_date"].date()
        if isinstance(document["end_date"], datetime)
        else document["end_date"],
        total_days=document["total_days"],
        reason=document["reason"],
        status=document["status"],
        reviewed_by=(
            str(document["reviewed_by"])
            if document.get("reviewed_by")
            else None
        ),
        reviewed_at=document.get("reviewed_at"),
        review_note=document.get("review_note"),
        created_at=document.get("created_at"),
        updated_at=document.get("updated_at"),
    )


def mongo_date(value: date) -> datetime:
    """Convert a Python date to a MongoDB-compatible UTC midnight."""
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def date_from_mongo(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value


async def applicable_holidays(
    database: Any,
    employee: dict,
    start_date: date,
    end_date: date,
) -> set[date]:
    """Return active company-wide or employee-department holidays."""
    department_id = employee.get("department_id")

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

    if department_id is not None:
        query["$or"].append({"department_ids": department_id})

    cursor = database["holidays"].find(query)
    documents = await cursor.to_list(length=None)

    return {
        date_from_mongo(document["holiday_date"])
        for document in documents
    }


async def count_working_days(
    database: Any,
    employee: dict,
    start_date: date,
    end_date: date,
) -> int:
    """Count working days, excluding weekends and applicable holidays."""
    holidays = await applicable_holidays(
        database, employee, start_date, end_date
    )

    total = 0
    current_day = start_date

    while current_day <= end_date:
        if (
            current_day.weekday() not in WEEKEND_DAYS
            and current_day not in holidays
        ):
            total += 1

        current_day += timedelta(days=1)

    return total


async def get_employee(
    database: Any,
    employee_id: ObjectId,
) -> dict:
    employee = await database["employees"].find_one(
        {"_id": employee_id}
    )

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee record not found.",
        )

    if employee.get("employment_status") != "Active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only active employees can apply for leave.",
        )

    return employee


def employee_object_id(current_user: dict) -> ObjectId:
    employee_id = current_user.get("employee_id")

    if not employee_id or not ObjectId.is_valid(str(employee_id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not linked to an employee record.",
        )

    return ObjectId(str(employee_id))


async def get_leave_balance(
    database: Any,
    employee_id: ObjectId,
    leave_type: str,
    year: int,
) -> float | None:
    """Return remaining quota; pending requests reserve quota."""
    quota = LEAVE_QUOTAS[leave_type]

    if quota is None:
        return None

    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    cursor = database["leave_requests"].find(
        {
            "employee_id": employee_id,
            "leave_type": leave_type,
            "status": {"$in": ["Pending", "Approved"]},
            "start_date": {
                "$gte": mongo_date(year_start),
                "$lte": mongo_date(year_end),
            },
        }
    )
    requests = await cursor.to_list(length=None)

    used_days = sum(
        float(request.get("total_days", 0))
        for request in requests
    )

    return max(0.0, float(quota) - used_days)


async def reject_overlapping_leave(
    database: Any,
    employee_id: ObjectId,
    start_date: date,
    end_date: date,
) -> None:
    """Prevent overlapping pending or approved requests."""
    cursor = database["leave_requests"].find(
        {
            "employee_id": employee_id,
            "status": {"$in": ["Pending", "Approved"]},
            "start_date": {"$lte": mongo_date(end_date)},
            "end_date": {"$gte": mongo_date(start_date)},
        }
    )

    if await cursor.to_list(length=1):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This leave period overlaps an existing pending "
                "or approved leave request."
            ),
        )


@router.post(
    "",
    response_model=LeaveResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_leave_request(
    payload: LeaveCreateRequest,
    current_user: CurrentUser,
):
    """Submit a leave application for the authenticated employee."""
    if current_user.get("role") != "Employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only employee accounts can apply for leave.",
        )

    if payload.start_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Leave cannot start in the past.",
        )

    database = get_database()
    await ensure_leave_indexes(database)

    employee_id = employee_object_id(current_user)
    employee = await get_employee(database, employee_id)

    total_days = await count_working_days(
        database,
        employee,
        payload.start_date,
        payload.end_date,
    )

    if total_days <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The selected dates contain no working days.",
        )

    await reject_overlapping_leave(
        database,
        employee_id,
        payload.start_date,
        payload.end_date,
    )

    # This version applies the quota to the calendar year of the
    # start date. Cross-year requests are rejected to avoid ambiguity.
    if payload.start_date.year != payload.end_date.year:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A leave request cannot cross calendar years.",
        )

    remaining = await get_leave_balance(
        database,
        employee_id,
        payload.leave_type,
        payload.start_date.year,
    )

    if remaining is not None and total_days > remaining:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Insufficient {payload.leave_type} leave balance. "
                f"Remaining: {remaining:g} working days."
            ),
        )

    now = datetime.now(timezone.utc)

    leave = LeaveRequest(
        employee_id=employee_id,
        leave_type=payload.leave_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        total_days=float(total_days),
        reason=payload.reason.strip(),
        status="Pending",
    )

    document = leave.model_dump(
        by_alias=True,
        mode="python",
        exclude_none=True,
    )
    document["start_date"] = mongo_date(payload.start_date)
    document["end_date"] = mongo_date(payload.end_date)
    document["created_at"] = now
    document["updated_at"] = now

    try:
        result = await database["leave_requests"].insert_one(document)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to create the leave request due to a conflict.",
        ) from exc

    
    saved = await database["leave_requests"].find_one(
        {"_id": result.inserted_id}
    )

    await log_audit_event(
        database=database,
        actor=current_user,
        action="LEAVE_REQUEST_CREATED",
        target_type="leave_request",
        target_id=str(result.inserted_id),
        details={
            "employee_id": str(employee_id),
            "leave_type": payload.leave_type,
            "start_date": payload.start_date.isoformat(),
            "end_date": payload.end_date.isoformat(),
            "total_days": total_days,
        },
    )

    return leave_response(saved)



@router.get(
    "/my",
    response_model=LeaveListResponse,
)
async def my_leave_requests(
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """Employees can see only their own leave applications."""
    if current_user.get("role") != "Employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for employee accounts.",
        )

    database = get_database()
    employee_id = employee_object_id(current_user)
    collection = database["leave_requests"]
    query = {"employee_id": employee_id}

    total = await collection.count_documents(query)
    cursor = (
        collection.find(query)
        .sort("start_date", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    documents = await cursor.to_list(length=page_size)

    return LeaveListResponse(
        items=[leave_response(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch(
    "/{leave_id}/cancel",
    response_model=LeaveResponse,
)
async def cancel_leave_request(
    leave_id: str,
    current_user: CurrentUser,
):
    """Allow an employee to cancel their own pending leave request."""
    if current_user.get("role") != "Employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only employees can cancel leave requests.",
        )

    if not ObjectId.is_valid(leave_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid leave request ID.",
        )

    database = get_database()
    collection = database["leave_requests"]

    employee_id = employee_object_id(current_user)

    # Match both the request ID and employee ID to enforce ownership.
    record = await collection.find_one(
        {
            "_id": ObjectId(leave_id),
            "employee_id": employee_id,
        }
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave request not found.",
        )

    if record.get("status") != "Pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending leave requests can be cancelled.",
        )

    now = datetime.now(timezone.utc)

    result = await collection.update_one(
        {
            "_id": record["_id"],
            "employee_id": employee_id,
            "status": "Pending",
        },
        {
            "$set": {
                "status": "Cancelled",
                "updated_at": now,
            }
        },
    )

    if result.modified_count != 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This leave request could not be cancelled because its status changed.",
        )

    saved = await collection.find_one({"_id": record["_id"]})

    await log_audit_event(
        database=database,
        actor=current_user,
        action="LEAVE_REQUEST_CANCELLED",
        target_type="leave_request",
        target_id=leave_id,
        details={
            "employee_id": str(employee_id),
            "leave_type": record["leave_type"],
            "previous_status": "Pending",
            "new_status": "Cancelled",
        },
    )

    return leave_response(saved)



@router.get(
    "",
    response_model=LeaveListResponse,
)
async def list_leave_requests(
    current_user: AdminOrHRUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    leave_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(Pending|Approved|Rejected|Cancelled)$",
    ),
    employee_id: str | None = None,
):
    """Admin and HR can list leave applications."""
    database = get_database()
    query: dict = {}

    if leave_status:
        query["status"] = leave_status

    if employee_id:
        if not ObjectId.is_valid(employee_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid employee ID.",
            )
        query["employee_id"] = ObjectId(employee_id)

    collection = database["leave_requests"]
    total = await collection.count_documents(query)
    cursor = (
        collection.find(query)
        .sort("start_date", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    documents = await cursor.to_list(length=page_size)

    return LeaveListResponse(
        items=[leave_response(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch(
    "/{leave_id}/review",
    response_model=LeaveResponse,
)
async def review_leave_request(
    leave_id: str,
    payload: LeaveReviewRequest,
    current_user: AdminOrHRUser,
):
    """Admin or HR can approve or reject a pending request."""
    if not ObjectId.is_valid(leave_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid leave request ID.",
        )

    database = get_database()
    collection = database["leave_requests"]

    record = await collection.find_one({"_id": ObjectId(leave_id)})

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave request not found.",
        )

    if record.get("status") != "Pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending leave requests can be reviewed.",
        )

    now = datetime.now(timezone.utc)

    result = await collection.update_one(
        {"_id": record["_id"], "status": "Pending"},
        {
            "$set": {
                "status": payload.status,
                "reviewed_by": ObjectId(str(current_user["_id"])),
                "reviewed_at": now,
                "review_note": (
                    payload.review_note.strip()
                    if payload.review_note
                    else None
                ),
                "updated_at": now,
            }
        },
    )

    if result.modified_count != 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This leave request was already reviewed.",
        )

    saved = await database["leave_requests"].find_one(
    {"_id": ObjectId(leave_id)}
    )

    await log_audit_event(
        database=database,
        actor=current_user,
        action=(
            "LEAVE_REQUEST_APPROVED"
            if payload.status == "Approved"
            else "LEAVE_REQUEST_REJECTED"
        ),
        target_type="leave_request",
        target_id=leave_id,
        details={
            "employee_id": str(record["employee_id"]),
            "leave_type": record["leave_type"],
            "status": payload.status,
            "review_note": payload.review_note,
        },
    )

    return leave_response(saved)
