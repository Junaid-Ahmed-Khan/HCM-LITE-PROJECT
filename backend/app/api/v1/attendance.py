
from datetime import date, datetime, time, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Any
from zoneinfo import ZoneInfo

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query, status
from pymongo.errors import DuplicateKeyError

from app.core.audit import log_audit_event
from app.core.database import get_database
from app.core.dependencies import AdminOrHRUser, CurrentUser
from app.models.attendance import Attendance
from app.schemas.attendance import (
    AttendanceListResponse,
    AttendanceResponse,
    CheckInRequest,
    CheckOutRequest,
)
from app.services.face_recognition import verify_face


router = APIRouter(prefix="/attendance", tags=["Attendance"])

BUSINESS_TIMEZONE = ZoneInfo("Asia/Karachi")

OFFICE_START_DEFAULT = time(9, 0)
GRACE_PERIOD_DEFAULT = 15
HALF_DAY_HOURS_DEFAULT = 5.0
MAX_GPS_ACCURACY_METRES = 100.0


async def ensure_attendance_indexes(database: Any) -> None:
    """Create indexes needed to prevent duplicate daily attendance."""
    await database["attendance"].create_index(
        [("employee_id", 1), ("attendance_date", 1)],
        unique=True,
        name="unique_employee_attendance_per_day",
    )

    await database["attendance"].create_index(
        [("attendance_date", -1)],
        name="attendance_date_desc",
    )


def attendance_response(document: dict) -> AttendanceResponse:
    """Convert a MongoDB attendance document into the API response."""
    return AttendanceResponse(
        id=str(document["_id"]),
        employee_id=str(document["employee_id"]),
        attendance_date=document["attendance_date"],
        check_in_at=document["check_in_at"],
        check_out_at=document.get("check_out_at"),
        status=document["status"],
        source=document["source"],
        check_in_latitude=document.get("check_in_latitude"),
        check_in_longitude=document.get("check_in_longitude"),
        gps_accuracy_m=document.get("gps_accuracy_m"),
        notes=document.get("notes"),
        created_at=document.get("created_at"),
        updated_at=document.get("updated_at"),
    )


def get_employee_object_id(current_user: dict) -> ObjectId:
    """Require the authenticated account to be linked to an employee."""
    employee_id = current_user.get("employee_id")

    if not employee_id or not ObjectId.is_valid(str(employee_id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not linked to an employee record.",
        )

    return ObjectId(str(employee_id))


def parse_office_start(value: Any) -> time:
    """Support office_start_time stored as a time or HH:MM string."""
    if isinstance(value, time):
        return value.replace(tzinfo=None)

    if isinstance(value, str):
        try:
            return time.fromisoformat(value.strip()).replace(tzinfo=None)
        except ValueError:
            pass

    return OFFICE_START_DEFAULT


def setting_value(
    settings: dict | None,
    names: tuple[str, ...],
    default: Any = None,
) -> Any:
    """Read a setting while supporting common field-name variants."""
    if not settings:
        return default

    for name in names:
        if settings.get(name) is not None:
            return settings[name]

    return default


def haversine_distance_m(
    latitude1: float,
    longitude1: float,
    latitude2: float,
    longitude2: float,
) -> float:
    """Calculate the distance between two GPS coordinates in metres."""
    earth_radius_m = 6_371_000.0

    lat1 = radians(latitude1)
    lat2 = radians(latitude2)
    delta_lat = radians(latitude2 - latitude1)
    delta_lon = radians(longitude2 - longitude1)

    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    )
    a = min(1.0, max(0.0, a))

    return 2 * earth_radius_m * asin(sqrt(a))


async def get_company_settings(database: Any) -> dict:
    """Read the existing company settings document."""
    settings = await database["company_settings"].find_one({})

    if not settings:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company settings must be configured before attendance.",
        )

    return settings


async def check_company_holiday(
    database: Any,
    employee: dict,
    attendance_date: str,
) -> bool:
    """
    Return True if an active company or department holiday applies.

    Assumes holiday_date is stored as an ISO date string:
    YYYY-MM-DD.
    """
    query = {
        "holiday_date": attendance_date,
        "is_active": True,
        "$or": [
            {"department_ids": {"$exists": False}},
            {"department_ids": []},
            {"department_ids": employee.get("department_id")},
        ],
    }

    holiday = await database["holidays"].find_one(query)
    return holiday is not None


async def require_active_employee(
    database: Any,
    employee_id: ObjectId,
) -> dict:
    """Require an existing, active employee record."""
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
            detail="Only active employees can record attendance.",
        )

    return employee


async def validate_camera_location(
    database: Any,
    payload: CheckInRequest,
) -> None:
    """Validate GPS accuracy and distance for camera check-ins."""
    if (
        payload.latitude is None
        or payload.longitude is None
        or payload.gps_accuracy_m is None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Camera check-in requires latitude, longitude, "
                "and GPS accuracy."
            ),
        )

    if payload.gps_accuracy_m > MAX_GPS_ACCURACY_METRES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="GPS accuracy must be 100 metres or better.",
        )

    settings = await get_company_settings(database)

    office_latitude = setting_value(
        settings,
        ("office_latitude", "office_location_latitude"),
    )
    office_longitude = setting_value(
        settings,
        ("office_longitude", "office_location_longitude"),
    )
    office_radius = setting_value(
        settings,
        (
            "office_radius_meters",
            "office_radius_m",
            "office_radius_metres",
            "office_radius",
        ),
    )

    if (
        office_latitude is None
        or office_longitude is None
        or office_radius is None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Configure the office GPS coordinates and attendance "
                "radius before enabling camera check-in."
            ),
        )

    distance = haversine_distance_m(
        payload.latitude,
        payload.longitude,
        float(office_latitude),
        float(office_longitude),
    )

    if distance > float(office_radius):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are outside the permitted office attendance area.",
        )


def determine_check_in_status(
    local_now: datetime,
    settings: dict,
) -> str:
    """Determine whether check-in is Present or Late."""
    office_start = parse_office_start(
        setting_value(
            settings,
            ("office_start_time",),
            OFFICE_START_DEFAULT,
        )
    )

    grace_minutes = int(
        setting_value(
            settings,
            ("grace_period_minutes",),
            GRACE_PERIOD_DEFAULT,
        )
    )

    deadline = datetime.combine(
        local_now.date(),
        office_start,
    ) + timedelta(minutes=grace_minutes)

    if local_now.replace(tzinfo=None) > deadline:
        return "Late"

    return "Present"


@router.post(
    "/check-in",
    response_model=AttendanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def check_in(
    payload: CheckInRequest,
    current_user: CurrentUser,
):
    """Record one attendance check-in per employee per working day."""
    if current_user.get("role") != "Employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only employee accounts can check in.",
        )

    database = get_database()
    await ensure_attendance_indexes(database)

    employee_id = get_employee_object_id(current_user)
    employee = await require_active_employee(database, employee_id)

    now_utc = datetime.now(timezone.utc)
    local_now = now_utc.astimezone(BUSINESS_TIMEZONE)
    attendance_date = local_now.date().isoformat()

    # Saturday = 5, Sunday = 6.
    if local_now.weekday() in (5, 6):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Attendance check-in is unavailable on weekends.",
        )

    if await check_company_holiday(
        database,
        employee,
        attendance_date,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Attendance check-in is unavailable on company holidays.",
        )

    settings = await get_company_settings(database)

    if payload.source == "camera":
        await validate_camera_location(database, payload)

    existing = await database["attendance"].find_one(
        {
            "employee_id": employee_id,
            "attendance_date": attendance_date,
        }
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attendance has already been recorded for today.",
        )

    record = Attendance(
        employee_id=employee_id,
        attendance_date=attendance_date,
        check_in_at=now_utc,
        status=determine_check_in_status(local_now, settings),
        source=payload.source,
        check_in_latitude=payload.latitude,
        check_in_longitude=payload.longitude,
        gps_accuracy_m=payload.gps_accuracy_m,
    )

    document = record.model_dump(
        by_alias=True,
        mode="python",
        exclude_none=True,
    )

    if payload.source == "camera":
        if not payload.face_image_base64:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A face image is required for camera check-in.",
            )

        enrollment = await database["face_enrollments"].find_one(
            {"employee_id": employee_id}
        )

        if not enrollment or not enrollment.get("embedding"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your face has not been enrolled. Contact HR.",
            )

        try:
            matched, _distance = verify_face(
                payload.face_image_base64,
                enrollment["embedding"],
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Face verification is temporarily unavailable.",
            ) from exc

        if not matched:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Face verification failed. Attendance was not recorded.",
            )

    # Never save the submitted face image in the attendance document.
    try:
        result = await database["attendance"].insert_one(document)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attendance has already been recorded for today.",
        ) from exc

    saved = await database["attendance"].find_one(
        {"_id": result.inserted_id}
    )

    if not saved:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Attendance was recorded but could not be retrieved.",
        )

    await log_audit_event(
        database=database,
        actor=current_user,
        action="ATTENDANCE_CHECK_IN",
        target_type="attendance",
        target_id=str(result.inserted_id),
        details={
            "employee_id": str(employee_id),
            "attendance_date": attendance_date,
            "status": saved["status"],
            "source": saved["source"],
        },
    )

    return attendance_response(saved)


@router.post(
    "/check-out",
    response_model=AttendanceResponse,
)
async def check_out(
    payload: CheckOutRequest,
    current_user: CurrentUser,
):
    """Record checkout and update the final attendance status."""
    if current_user.get("role") != "Employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only employee accounts can check out.",
        )

    database = get_database()
    employee_id = get_employee_object_id(current_user)

    now_utc = datetime.now(timezone.utc)
    local_now = now_utc.astimezone(BUSINESS_TIMEZONE)
    attendance_date = local_now.date().isoformat()

    record = await database["attendance"].find_one(
        {
            "employee_id": employee_id,
            "attendance_date": attendance_date,
        }
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No check-in record exists for today.",
        )

    if record.get("check_out_at") is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already checked out today.",
        )

    check_in_at = record["check_in_at"]

    # MongoDB may return a naive datetime depending on client configuration.
    if check_in_at.tzinfo is None:
        check_in_at = check_in_at.replace(tzinfo=timezone.utc)

    elapsed_seconds = (now_utc - check_in_at).total_seconds()

    if elapsed_seconds < 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Checkout time cannot be earlier than check-in time.",
        )

    settings = await get_company_settings(database)

    half_day_hours = float(
        setting_value(
            settings,
            ("half_day_hours",),
            HALF_DAY_HOURS_DEFAULT,
        )
    )

    worked_hours = elapsed_seconds / 3600
    new_status = record.get("status", "Present")

    if worked_hours < half_day_hours:
        new_status = "HalfDay"

    update_result = await database["attendance"].update_one(
        {
            "_id": record["_id"],
            "check_out_at": None,
        },
        {
            "$set": {
                "check_out_at": now_utc,
                "status": new_status,
                "updated_at": now_utc,
            }
        },
    )

    if update_result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Checkout was already recorded or the attendance record changed.",
        )

    updated = await database["attendance"].find_one(
        {"_id": record["_id"]}
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Checkout was recorded but the record could not be retrieved.",
        )

    await log_audit_event(
        database=database,
        actor=current_user,
        action="ATTENDANCE_CHECK_OUT",
        target_type="attendance",
        target_id=str(record["_id"]),
        details={
            "employee_id": str(employee_id),
            "attendance_date": attendance_date,
            "status": updated["status"],
            "worked_hours": round(worked_hours, 2),
        },
    )

    return attendance_response(updated)


@router.get(
    "/my",
    response_model=AttendanceListResponse,
)
async def get_my_attendance(
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    start_date: date | None = None,
    end_date: date | None = None,
):
    """Employees can retrieve only their own attendance records."""
    if current_user.get("role") != "Employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for employee accounts.",
        )

    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date must not be later than end_date.",
        )

    database = get_database()
    employee_id = get_employee_object_id(current_user)

    query: dict = {"employee_id": employee_id}

    if start_date or end_date:
        query["attendance_date"] = {}

        if start_date:
            query["attendance_date"]["$gte"] = start_date.isoformat()

        if end_date:
            query["attendance_date"]["$lte"] = end_date.isoformat()

    collection = database["attendance"]
    total = await collection.count_documents(query)

    cursor = (
        collection.find(query)
        .sort("attendance_date", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )

    documents = await cursor.to_list(length=page_size)

    return AttendanceListResponse(
        items=[attendance_response(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "",
    response_model=AttendanceListResponse,
)
async def list_attendance(
    current_user: AdminOrHRUser,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    start_date: date | None = None,
    end_date: date | None = None,
    employee_id: str | None = None,
):
    """Admin/HR can review attendance with optional filters."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date must not be later than end_date.",
        )

    query: dict = {}

    if start_date or end_date:
        query["attendance_date"] = {}

        if start_date:
            query["attendance_date"]["$gte"] = start_date.isoformat()

        if end_date:
            query["attendance_date"]["$lte"] = end_date.isoformat()

    if employee_id:
        if not ObjectId.is_valid(employee_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid employee ID.",
            )

        query["employee_id"] = ObjectId(employee_id)

    database = get_database()
    collection = database["attendance"]
    total = await collection.count_documents(query)

    cursor = (
        collection.find(query)
        .sort("attendance_date", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )

    documents = await cursor.to_list(length=page_size)

    return AttendanceListResponse(
        items=[attendance_response(doc) for doc in documents],
        total=total,
        page=page,
        page_size=page_size,
    )
