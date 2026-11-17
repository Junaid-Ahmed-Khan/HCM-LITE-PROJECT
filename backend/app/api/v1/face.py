
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.database import get_database
from app.core.dependencies import AdminOrHRUser
from app.core.audit import log_audit_event
from app.services.face_recognition import create_face_embedding


router = APIRouter(prefix="/face", tags=["Face Attendance"])


class FaceEnrollmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_base64: str = Field(min_length=100, max_length=7_000_000)


@router.post(
    "/enroll/{employee_id}",
    status_code=status.HTTP_201_CREATED,
)
async def enroll_employee_face(
    employee_id: str,
    payload: FaceEnrollmentRequest,
    current_user: AdminOrHRUser,
):
    if not ObjectId.is_valid(employee_id):
        raise HTTPException(422, "Invalid employee ID.")

    database = get_database()
    employee = await database["employees"].find_one(
        {"_id": ObjectId(employee_id)}
    )

    if not employee:
        raise HTTPException(404, "Employee not found.")

    if employee.get("employment_status") != "Active":
        raise HTTPException(
            409,
            "Only active employees can be enrolled.",
        )

    try:
        embedding = create_face_embedding(payload.image_base64)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        # Keep internal model errors out of the API response.
        raise HTTPException(
            503,
            "Face processing failed. Check the backend model installation.",
        ) from exc

    now = datetime.now(timezone.utc)
    collection = database["face_enrollments"]

    # One current template per employee. The unique index is also created
    # by ensure_face_indexes below.
    await ensure_face_indexes(database)

    await collection.update_one(
        {"employee_id": ObjectId(employee_id)},
        {
            "$set": {
                "employee_id": ObjectId(employee_id),
                "embedding": embedding,
                "model_name": "Facenet512",
                "enrolled_at": now,
                "enrolled_by": str(current_user.get("_id", "")),
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )

    await log_audit_event(
        database=database,
        actor=current_user,
        action="EMPLOYEE_FACE_ENROLLED",
        target_type="employee",
        target_id=employee_id,
        details={"employee_code": employee.get("employee_code")},
    )

    return {
        "message": "Face enrollment completed.",
        "employee_id": employee_id,
    }


async def ensure_face_indexes(database) -> None:
    await database["face_enrollments"].create_index(
        "employee_id",
        unique=True,
    )

