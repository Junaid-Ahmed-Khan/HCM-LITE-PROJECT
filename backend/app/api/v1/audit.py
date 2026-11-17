
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.core.database import get_database
from app.core.dependencies import CurrentUser


router = APIRouter(
    prefix="/audit-logs",
    tags=["Audit Logs"],
)


@router.get("")
async def get_audit_logs(
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: str | None = None,
    target_type: str | None = None,
):
    """
    Retrieve audit logs with pagination.
    Only Admin users are allowed to view audit logs.
    """

    # Enforce Admin-only access.
    if current_user.get("role") != "Admin":
        raise HTTPException(
            status_code=403,
            detail="Only administrators can view audit logs.",
        )

    database = get_database()
    collection = database["audit_logs"]

    # Build optional filters.
    filters: dict[str, Any] = {}

    if action:
        filters["action"] = {
            "$regex": action,
            "$options": "i",
        }

    if target_type:
        filters["target_type"] = target_type

    # Calculate total records matching the filters.
    total = await collection.count_documents(filters)

    # Fetch newest audit events first.
    cursor = (
        collection.find(filters)
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )

    documents = await cursor.to_list(length=page_size)

    # Convert MongoDB documents into JSON-safe dictionaries.
    items = []

    for document in documents:
        created_at = document.get("created_at")

        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()

        actor_id = document.get("actor_id")

        items.append(
            {
                "id": str(document["_id"]),
                "actor_id": (
                    str(actor_id)
                    if actor_id is not None
                    else None
                ),
                "actor_email": document.get("actor_email"),
                "actor_role": document.get("actor_role"),
                "action": document.get("action"),
                "target_type": document.get("target_type"),
                "target_id": document.get("target_id"),
                "details": document.get("details") or {},
                "created_at": created_at,
            }
        )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
