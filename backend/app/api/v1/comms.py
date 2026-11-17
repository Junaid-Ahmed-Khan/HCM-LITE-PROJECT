
from datetime import datetime, timezone
from typing import Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.core.database import get_database
from app.core.dependencies import CurrentUser


router = APIRouter(prefix="/comms", tags=["Communications"])


class AnnouncementCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=150)
    message: str = Field(min_length=3, max_length=5000)
    audience: Literal["All", "HR", "Employees"] = "All"


class AnnouncementResponse(BaseModel):
    id: str
    title: str
    message: str
    audience: str
    created_by: str
    created_at: datetime
    is_archived: bool


def require_roles(current_user: dict, *roles: str) -> None:
    if current_user.get("role") not in roles:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to perform this action.",
        )


def serialize_announcement(document: dict) -> dict:
    return {
        "id": str(document["_id"]),
        "title": document["title"],
        "message": document["message"],
        "audience": document["audience"],
        "created_by": str(document["created_by"]),
        "created_at": document["created_at"],
        "is_archived": document["is_archived"],
    }


@router.post(
    "/announcements",
    response_model=AnnouncementResponse,
    status_code=201,
)
async def create_announcement(
    request: AnnouncementCreateRequest,
    current_user: CurrentUser,
    database=Depends(get_database),
):
    require_roles(current_user, "Admin", "HR")

    creator_id = current_user.get("_id")
    if not isinstance(creator_id, ObjectId):
        try:
            creator_id = ObjectId(str(creator_id))
        except Exception:
            raise HTTPException(
                status_code=401,
                detail="Invalid authenticated user.",
            )

    announcement = {
        "title": request.title.strip(),
        "message": request.message.strip(),
        "audience": request.audience,
        "created_by": creator_id,
        "created_at": datetime.now(timezone.utc),
        "is_archived": False,
    }

    if len(announcement["title"]) < 3 or len(announcement["message"]) < 3:
        raise HTTPException(
            status_code=422,
            detail="Title and message must contain at least 3 non-space characters.",
        )

    result = await database["announcements"].insert_one(announcement)
    announcement["_id"] = result.inserted_id

    return serialize_announcement(announcement)


@router.get("/announcements", response_model=list[AnnouncementResponse])
async def list_announcements(
    current_user: CurrentUser,
    include_archived: bool = Query(default=False),
    database=Depends(get_database),
):
    role = current_user.get("role")

    if role not in ("Admin", "HR", "Employee"):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to view announcements.",
        )

    query = {}

    if role == "Employee":
        query["is_archived"] = False
        query["audience"] = {"$in": ["All", "Employees"]}
    else:
        if not include_archived:
            query["is_archived"] = False

    cursor = database["announcements"].find(query).sort("created_at", -1)

    announcements = []
    async for document in cursor:
        announcements.append(serialize_announcement(document))

    return announcements


@router.patch(
    "/announcements/{announcement_id}/archive",
    response_model=AnnouncementResponse,
)
async def archive_announcement(
    announcement_id: str,
    current_user: CurrentUser,
    database=Depends(get_database),
):
    require_roles(current_user, "Admin")

    if not ObjectId.is_valid(announcement_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid announcement ID.",
        )

    announcement = await database["announcements"].find_one(
        {"_id": ObjectId(announcement_id)}
    )

    if announcement is None:
        raise HTTPException(
            status_code=404,
            detail="Announcement not found.",
        )

    if announcement.get("is_archived", False):
        raise HTTPException(
            status_code=409,
            detail="Announcement is already archived.",
        )

    await database["announcements"].update_one(
        {"_id": announcement["_id"]},
        {
            "$set": {
                "is_archived": True,
                "archived_at": datetime.now(timezone.utc),
                "archived_by": current_user.get("_id"),
            }
        },
    )

    announcement["is_archived"] = True
    return serialize_announcement(announcement)
