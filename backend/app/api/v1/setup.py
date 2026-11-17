from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from app.core.database import get_database
from app.core.dependencies import AdminOrHRUser, AdminUser
from app.models.documents import CompanySettings
from app.schemas.setup import (
    CompanySettingsResponse,
    CompanySettingsUpdate,
    SetupMessageResponse,
)

router = APIRouter(prefix="/setup", tags=["Organization Setup"])


def format_company_settings(document: dict) -> CompanySettingsResponse:
    return CompanySettingsResponse(
        id=str(document["_id"]),
        company_name=document["company_name"],
        company_email=document.get("company_email"),
        company_phone=document.get("company_phone"),
        address=document.get("address"),
        office_latitude=document.get("office_latitude"),
        office_longitude=document.get("office_longitude"),
        office_radius_meters=document["office_radius_meters"],
        office_start_time=document["office_start_time"],
        grace_period_minutes=document["grace_period_minutes"],
        half_day_hours=document["half_day_hours"],
        weekend_days=document["weekend_days"],
        created_at=document["created_at"],
        updated_at=document["updated_at"],
    )


async def get_company_document() -> dict:
    database = get_database()

    document = await database["company_settings"].find_one(
        {"singleton_key": "company"}
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company setup has not been completed.",
        )

    return document


@router.get(
    "/company",
    response_model=CompanySettingsResponse,
)
async def read_company_settings(
    current_user: AdminOrHRUser,
):
    """Admin and HR can view company configuration."""

    document = await get_company_document()
    return format_company_settings(document)


@router.patch(
    "/company",
    response_model=CompanySettingsResponse,
)
async def update_company_settings(
    payload: CompanySettingsUpdate,
    current_user: AdminUser,
):
    """Only Admin can update company configuration."""

    changes = payload.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one setting to update.",
        )

    database = get_database()
    collection = database["company_settings"]

    current = await get_company_document()

    # Validate the merged settings, not just the individual changed fields.
    # This also validates settings that depend on existing values.
    try:
        candidate = CompanySettings.model_validate(
            {**current, **changes}
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # GPS attendance requires both coordinates or neither.
    latitude = candidate.office_latitude
    longitude = candidate.office_longitude

    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Set both office_latitude and office_longitude, "
                "or clear both."
            ),
        )

    now = datetime.now(timezone.utc)

    update_values = {
        field: getattr(candidate, field)
        for field in changes
    }
    update_values["updated_at"] = now

    result = await collection.update_one(
        {
            "_id": current["_id"],
            "singleton_key": "company",
        },
        {"$set": update_values},
    )

    if result.matched_count != 1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company settings could not be found.",
        )

    updated = await collection.find_one(
        {
            "_id": current["_id"],
            "singleton_key": "company",
        }
    )

    return format_company_settings(updated)