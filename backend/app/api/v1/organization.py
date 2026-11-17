
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from pymongo.errors import DuplicateKeyError

from app.core.audit import log_audit_event
from app.core.database import get_database
from app.core.dependencies import AdminUser, CurrentUser
from app.models.documents import Department, Designation, utc_now


department_router = APIRouter(
    prefix="/departments",
    tags=["Departments"],
)

designation_router = APIRouter(
    prefix="/designations",
    tags=["Designations"],
)


# ============================================================
# DEPARTMENT SCHEMAS
# ============================================================

class DepartmentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


class DepartmentUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=120)
    code: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


class DepartmentStatusUpdate(BaseModel):
    is_active: bool


class DepartmentResponse(BaseModel):
    id: str
    name: str
    code: str
    description: str | None = None
    head_employee_id: str | None = None
    is_active: bool


class DepartmentListResponse(BaseModel):
    items: list[DepartmentResponse]
    total: int
    page: int
    page_size: int


# ============================================================
# DESIGNATION SCHEMAS
# ============================================================

class DesignationCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=120)
    department_id: str
    description: str | None = Field(default=None, max_length=1000)


class DesignationUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=120)
    code: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


class DesignationResponse(BaseModel):
    id: str
    name: str
    code: str
    department_id: str
    description: str | None = None
    is_active: bool


class DesignationListResponse(BaseModel):
    items: list[DesignationResponse]
    total: int
    page: int
    page_size: int


# ============================================================
# RESPONSE HELPERS
# ============================================================

def department_response(document: dict) -> DepartmentResponse:
    head_id = document.get("head_employee_id")

    return DepartmentResponse(
        id=str(document["_id"]),
        name=document["name"],
        code=document["code"],
        description=document.get("description"),
        head_employee_id=str(head_id) if head_id else None,
        is_active=document.get("is_active", True),
    )


def designation_response(document: dict) -> DesignationResponse:
    return DesignationResponse(
        id=str(document["_id"]),
        name=document["name"],
        code=document["code"],
        department_id=str(document["department_id"]),
        description=document.get("description"),
        is_active=document.get("is_active", True),
    )


# ============================================================
# DATABASE INDEXES
# ============================================================

async def ensure_organization_indexes(database) -> None:
    await database["departments"].create_index(
        "code",
        unique=True,
    )

    await database["designations"].create_index(
        [("department_id", 1), ("code", 1)],
        unique=True,
    )


# ============================================================
# DEPARTMENTS
# ============================================================

@department_router.post(
    "",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_department(
    payload: DepartmentCreate,
    current_user: AdminUser,
):
    # ADMIN ONLY
    database = get_database()
    await ensure_organization_indexes(database)

    data = payload.model_dump()
    data["name"] = data["name"].strip()
    data["code"] = data["code"].strip().upper()

    department = Department(**data)

    document = department.model_dump(
        by_alias=True,
        mode="python",
    )

    document["created_at"] = utc_now()
    document["updated_at"] = document["created_at"]

    try:
        result = await database["departments"].insert_one(document)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A department with this code already exists.",
        ) from exc

    document["_id"] = result.inserted_id

    await log_audit_event(
        database=database,
        actor=current_user,
        action="DEPARTMENT_CREATED",
        target_type="department",
        target_id=str(result.inserted_id),
        details={
            "name": document["name"],
            "code": document["code"],
        },
    )

    return department_response(document)


@department_router.get(
    "",
    response_model=DepartmentListResponse,
)
async def list_departments(
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    include_inactive: bool = False,
):
    # All authenticated roles can view departments.
    database = get_database()

    query = {} if include_inactive else {"is_active": True}

    collection = database["departments"]
    total = await collection.count_documents(query)

    cursor = (
        collection.find(query)
        .sort("name", 1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )

    documents = await cursor.to_list(length=page_size)

    return DepartmentListResponse(
        items=[department_response(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@department_router.patch(
    "/{department_id}/status",
    response_model=DepartmentResponse,
)
async def update_department_status(
    department_id: str,
    payload: DepartmentStatusUpdate,
    current_user: AdminUser,
):
    # ADMIN ONLY
    if not ObjectId.is_valid(department_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid department ID.",
        )

    database = get_database()
    collection = database["departments"]
    object_id = ObjectId(department_id)

    department = await collection.find_one({"_id": object_id})

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found.",
        )

    old_status = department.get("is_active", True)
    new_status = payload.is_active

    if old_status == new_status:
        return department_response(department)

    await collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "is_active": new_status,
                "updated_at": utc_now(),
            }
        },
    )

    updated = await collection.find_one({"_id": object_id})

    await log_audit_event(
        database=database,
        actor=current_user,
        action="DEPARTMENT_STATUS_CHANGED",
        target_type="department",
        target_id=department_id,
        details={
            "department_name": updated["name"],
            "department_code": updated["code"],
            "old_status": old_status,
            "new_status": new_status,
        },
    )

    return department_response(updated)


@department_router.patch(
    "/{department_id}",
    response_model=DepartmentResponse,
)
async def update_department(
    department_id: str,
    payload: DepartmentUpdate,
    current_user: AdminUser,
):
    # ADMIN ONLY
    if not ObjectId.is_valid(department_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid department ID.",
        )

    database = get_database()
    collection = database["departments"]
    object_id = ObjectId(department_id)

    existing = await collection.find_one({"_id": object_id})

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found.",
        )

    changes = payload.model_dump(exclude_unset=True)

    if not changes:
        return department_response(existing)

    for field in ("name", "code"):
        if field in changes and changes[field] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Department {field} cannot be null.",
            )

    if "name" in changes:
        changes["name"] = changes["name"].strip()

    if "code" in changes:
        changes["code"] = changes["code"].strip().upper()

    for field in ("name", "code"):
        if field in changes and not changes[field]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Department {field} cannot be blank.",
            )

    actual_changes = {
        field: value
        for field, value in changes.items()
        if existing.get(field) != value
    }

    if not actual_changes:
        return department_response(existing)

    updated_fields = list(actual_changes.keys())
    actual_changes["updated_at"] = utc_now()

    try:
        await collection.update_one(
            {"_id": object_id},
            {"$set": actual_changes},
        )
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A department with this code already exists.",
        ) from exc

    updated = await collection.find_one({"_id": object_id})

    await log_audit_event(
        database=database,
        actor=current_user,
        action="DEPARTMENT_UPDATED",
        target_type="department",
        target_id=department_id,
        details={
            "updated_fields": updated_fields,
        },
    )

    return department_response(updated)


# ============================================================
# DESIGNATIONS
# ============================================================

@designation_router.post(
    "",
    response_model=DesignationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_designation(
    payload: DesignationCreate,
    current_user: AdminUser,
):
    # ADMIN ONLY
    if not ObjectId.is_valid(payload.department_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="department_id must be a valid MongoDB ID.",
        )

    database = get_database()
    await ensure_organization_indexes(database)

    department = await database["departments"].find_one(
        {
            "_id": ObjectId(payload.department_id),
            "is_active": True,
        }
    )

    if not department:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Department does not exist or is inactive.",
        )

    data = payload.model_dump()
    data["name"] = data["name"].strip()
    data["code"] = data["code"].strip().upper()
    data["department_id"] = ObjectId(data["department_id"])

    designation = Designation(**data)

    document = designation.model_dump(
        by_alias=True,
        mode="python",
    )

    document["created_at"] = utc_now()
    document["updated_at"] = document["created_at"]

    try:
        result = await database["designations"].insert_one(document)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This designation code already exists in the department.",
        ) from exc

    document["_id"] = result.inserted_id

    await log_audit_event(
        database=database,
        actor=current_user,
        action="DESIGNATION_CREATED",
        target_type="designation",
        target_id=str(result.inserted_id),
        details={
            "name": document["name"],
            "code": document["code"],
            "department_id": str(document["department_id"]),
        },
    )

    return designation_response(document)


@designation_router.get(
    "",
    response_model=DesignationListResponse,
)
async def list_designations(
    current_user: CurrentUser,
    department_id: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    include_inactive: bool = False,
):
    # All authenticated roles can view designations.
    database = get_database()

    query = {} if include_inactive else {"is_active": True}

    if department_id:
        if not ObjectId.is_valid(department_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="department_id must be a valid MongoDB ID.",
            )

        query["department_id"] = ObjectId(department_id)

    collection = database["designations"]
    total = await collection.count_documents(query)

    cursor = (
        collection.find(query)
        .sort("name", 1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )

    documents = await cursor.to_list(length=page_size)

    return DesignationListResponse(
        items=[designation_response(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@designation_router.patch(
    "/{designation_id}/status",
    response_model=DesignationResponse,
)
async def update_designation_status(
    designation_id: str,
    payload: DepartmentStatusUpdate,
    current_user: AdminUser,
):
    # ADMIN ONLY
    if not ObjectId.is_valid(designation_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid designation ID.",
        )

    database = get_database()
    collection = database["designations"]
    object_id = ObjectId(designation_id)

    designation = await collection.find_one({"_id": object_id})

    if not designation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Designation not found.",
        )

    old_status = designation.get("is_active", True)
    new_status = payload.is_active

    if old_status == new_status:
        return designation_response(designation)

    await collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "is_active": new_status,
                "updated_at": utc_now(),
            }
        },
    )

    updated = await collection.find_one({"_id": object_id})

    await log_audit_event(
        database=database,
        actor=current_user,
        action="DESIGNATION_STATUS_CHANGED",
        target_type="designation",
        target_id=designation_id,
        details={
            "designation_name": updated["name"],
            "designation_code": updated["code"],
            "old_status": old_status,
            "new_status": new_status,
        },
    )

    return designation_response(updated)


@designation_router.patch(
    "/{designation_id}",
    response_model=DesignationResponse,
)
async def update_designation(
    designation_id: str,
    payload: DesignationUpdate,
    current_user: AdminUser,
):
    # ADMIN ONLY
    if not ObjectId.is_valid(designation_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid designation ID.",
        )

    database = get_database()
    collection = database["designations"]
    object_id = ObjectId(designation_id)

    existing = await collection.find_one({"_id": object_id})

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Designation not found.",
        )

    changes = payload.model_dump(exclude_unset=True)

    if not changes:
        return designation_response(existing)

    for field in ("name", "code"):
        if field in changes:
            value = changes[field]

            if value is None or not value.strip():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Designation {field} cannot be blank.",
                )

    if "name" in changes:
        changes["name"] = changes["name"].strip()

    if "code" in changes:
        changes["code"] = changes["code"].strip().upper()

    actual_changes = {
        field: value
        for field, value in changes.items()
        if existing.get(field) != value
    }

    if not actual_changes:
        return designation_response(existing)

    updated_fields = list(actual_changes.keys())
    actual_changes["updated_at"] = utc_now()

    try:
        await collection.update_one(
            {"_id": object_id},
            {"$set": actual_changes},
        )
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This designation code already exists in the department.",
        ) from exc

    updated = await collection.find_one({"_id": object_id})

    await log_audit_event(
        database=database,
        actor=current_user,
        action="DESIGNATION_UPDATED",
        target_type="designation",
        target_id=designation_id,
        details={
            "updated_fields": updated_fields,
        },
    )

    return designation_response(updated)
