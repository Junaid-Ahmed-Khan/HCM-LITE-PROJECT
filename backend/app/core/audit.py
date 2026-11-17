
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId


async def log_audit_event(
    database,
    actor: dict,
    action: str,
    target_type: str,
    target_id: str | None = None,
    details: dict[str, Any] | None = None,
):
    """Store an audit event in MongoDB."""

    actor_id = actor.get("_id")

    if isinstance(actor_id, ObjectId):
        actor_id = str(actor_id)

    safe_details = details or {}

    await database["audit_logs"].insert_one(
        {
            "actor_id": actor_id,
            "actor_email": actor.get("email"),
            "actor_role": actor.get("role"),
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "details": safe_details,
            "created_at": datetime.now(timezone.utc),
        }
    )
