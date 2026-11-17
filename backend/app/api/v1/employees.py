
from datetime import date, datetime, time
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.errors import DuplicateKeyError

from app.core.database import get_database
from app.core.dependencies import (
    AdminOrHRUser,
    CurrentUser,
    enforce_employee_scope,
)
from app.core.audit import log_audit_event
from app.models.documents import Employee, utc_now
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeListResponse,
    EmployeeResponse,
    EmployeeUpdate,
)


router = APIRouter(prefix="/employees", tags=["Employees"])


def employee_response(document: dict) -> EmployeeResponse:
    """Convert a MongoDB employee document into a safe API response."""
    return EmployeeResponse(
        id=str(document["_id"]),
        employee_code=document["employee_code"],
        first_name=document["first_name"],
        last_name=document["last_name"],
        email=str(document["email"]),
        phone=document.get("phone"),
        department_id=str(document["department_id"]),
        designation_id=str(document["designation_id"]),
        manager_id=(
            str(document["manager_id"])
            if document.get("manager_id")
            else None
        ),
        joining_date=document["joining_date"],
        employment_status=document["employment_status"],
        is_active=document.get("is_active", True),
        basic_salary=document["basic_salary"],
        created_at=(
            document["created_at"].isoformat()
            if document.get("created_at")
            else None
        ),
        updated_at=(
            document["updated_at"].isoformat()
            if document.get("updated_at")
            else None
        ),
    )


async def ensure_employee_indexes(database) -> None:
    await database["employees"].create_index(
        "employee_code", unique=True
    )
    await database["employees"].create_index(
        "email", unique=True
    )


async def validate_references(database, payload: dict) -> None:
    """Verify referenced department, designation, and manager records."""
    department_id = payload.get("department_id")
    designation_id = payload.get("designation_id")
    manager_id = payload.get("manager_id")

    if department_id is not None:
        department = await database["departments"].find_one(
            {"_id": ObjectId(department_id), "is_active": True}
        )
        if not department:
            raise HTTPException(
                status_code=422,
                detail="Department does not exist or is inactive.",
            )

    if designation_id is not None:
        designation = await database["designations"].find_one(
            {"_id": ObjectId(designation_id), "is_active": True}
        )
        if not designation:
            raise HTTPException(
                status_code=422,
                detail="Designation does not exist or is inactive.",
            )

        if department_id is not None:
            if designation["department_id"] != ObjectId(department_id):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Designation does not belong to the "
                        "selected department."
                    ),
                )

    if manager_id is not None:
        manager = await database["employees"].find_one(
            {
                "_id": ObjectId(manager_id),
                "employment_status": "Active",
            }
        )
        if not manager:
            raise HTTPException(
                status_code=422,
                detail="Manager does not exist or is not active.",
            )


@router.post(
    "",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_employee(
    payload: EmployeeCreate,
    current_user: AdminOrHRUser,
):
    database = get_database()
    await ensure_employee_indexes(database)

    data = payload.model_dump()

    for field in ("department_id", "designation_id", "manager_id"):
        value = data.get(field)
        if value is not None:
            if not ObjectId.is_valid(value):
                raise HTTPException(
                    status_code=422,
                    detail=f"{field} must be a valid MongoDB ID.",
                )
            data[field] = ObjectId(value)

    await validate_references(database, data)

    employee = Employee(**data)
    document = employee.model_dump(by_alias=True, mode="python")

    # New employee records are active by default.
    document["is_active"] = True

    document["created_at"] = utc_now()
    document["updated_at"] = document["created_at"]

    try:
        if isinstance(document.get("joining_date"), date):
            document["joining_date"] = datetime.combine(
                document["joining_date"],
                time.min,
            )

        result = await database["employees"].insert_one(document)
        print("AUDIT LOG: attempting to insert EMPLOYEE_CREATED")
        print("AUDIT DATABASE:", database.name)
        created_employee = await database["employees"].find_one(
        {"_id": result.inserted_id}
    )

        await log_audit_event(
        database=database,
        actor=current_user,
        action="EMPLOYEE_CREATED",
        target_type="employee",
        target_id=str(result.inserted_id),
        details={
            "employee_code": created_employee.get("employee_code"),
        },
    )

    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail="Employee code or email already exists.",
        )

    document["_id"] = result.inserted_id
    return employee_response(document)


@router.get("", response_model=EmployeeListResponse)
async def list_employees(
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    employment_status: str | None = None,
):
    database = get_database()
    query: dict = {}

    if current_user["role"] == "Employee":
        employee_id = current_user.get("employee_id")
        if not employee_id:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Your account is not linked to an employee record."
                ),
            )
        query["_id"] = employee_id

    if employment_status:
        allowed = {"Active", "OnLeave", "Resigned", "Terminated"}
        if employment_status not in allowed:
            raise HTTPException(
                status_code=422,
                detail="Invalid employment status.",
            )
        query["employment_status"] = employment_status

    collection = database["employees"]
    total = await collection.count_documents(query)

    cursor = (
        collection.find(query)
        .sort("employee_code", 1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    documents = await cursor.to_list(length=page_size)

    return EmployeeListResponse(
        items=[employee_response(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: str,
    current_user: CurrentUser,
):
    if not ObjectId.is_valid(employee_id):
        raise HTTPException(
            status_code=422,
            detail="Invalid employee ID.",
        )

    enforce_employee_scope(current_user, employee_id)

    database = get_database()
    document = await database["employees"].find_one(
        {"_id": ObjectId(employee_id)}
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Employee not found.",
        )

    return employee_response(document)


@router.patch("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: str,
    payload: EmployeeUpdate,
    current_user: AdminOrHRUser,
):
    if not ObjectId.is_valid(employee_id):
        raise HTTPException(
            status_code=422,
            detail="Invalid employee ID.",
        )

    database = get_database()
    collection = database["employees"]

    existing = await collection.find_one(
        {"_id": ObjectId(employee_id)}
    )
    if not existing:
        raise HTTPException(
            status_code=404,
            detail="Employee not found.",
        )

    changes = payload.model_dump(exclude_unset=True)
    old_employment_status = existing.get("employment_status")
    if "employment_status" in changes:
        changes["is_active"] = changes["employment_status"] in {
            "Active",
        "OnLeave",
        }

    if not changes:
        return employee_response(existing)

    for field in ("department_id", "designation_id", "manager_id"):
        value = changes.get(field)
        if value is not None:
            if not ObjectId.is_valid(value):
                raise HTTPException(
                    status_code=422,
                    detail=f"{field} must be a valid MongoDB ID.",
                )
            changes[field] = ObjectId(value)

    merged = {
        "department_id": changes.get(
            "department_id", existing["department_id"]
        ),
        "designation_id": changes.get(
            "designation_id", existing["designation_id"]
        ),
        "manager_id": changes.get(
            "manager_id", existing.get("manager_id")
        ),
    }

    await validate_references(database, merged)

    changes["updated_at"] = utc_now()

    try:
        if isinstance(changes.get("joining_date"), date):
            changes["joining_date"] = datetime.combine(
                changes["joining_date"],
                time.min,
            )

        await collection.update_one(
            {"_id": ObjectId(employee_id)},
            {"$set": changes},
        )

    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail="An employee with this email already exists.",
        )

    
    updated = await collection.find_one(
        {"_id": ObjectId(employee_id)}
    )

    # Record an event only if the employment status actually changed.
    new_employment_status = updated.get("employment_status")

    if old_employment_status != new_employment_status:
        await log_audit_event(
        database=database,
        actor=current_user,
        action="EMPLOYEE_STATUS_CHANGED",
        target_type="employee",
        target_id=employee_id,
        details={
            "employee_code": updated.get("employee_code"),
            "old_status": old_employment_status,
            "new_status": new_employment_status,
            },
        )

    # Keep the existing general employee update event.
    await log_audit_event(
    database=database,
    actor=current_user,
    action="EMPLOYEE_UPDATED",
    target_type="employee",
    target_id=employee_id,
    details={
        "updated_fields": list(
            payload.model_dump(exclude_unset=True).keys()
            ),
        },
    )

    return employee_response(updated)


