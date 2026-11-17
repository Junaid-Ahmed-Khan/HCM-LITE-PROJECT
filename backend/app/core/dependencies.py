
from typing import Annotated, Callable

from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.database import get_database
from app.core.security import decode_token


ROLES = ("Admin", "HR", "Employee")
INACTIVE_EMPLOYMENT_STATUSES = {"Resigned", "Terminated"}

bearer_scheme = HTTPBearer(auto_error=False)


def unauthorized(
    detail: str = "Could not authenticate credentials.",
) -> HTTPException:
    """Create a standard 401 response with a Bearer challenge."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> dict:
    """
    Authenticate an access token and reload the user from MongoDB.

    Employee accounts linked to inactive, resigned, or terminated
    employee records are denied access.
    """
    if credentials is None:
        raise unauthorized("Authentication is required.")

    claims = decode_token(
        credentials.credentials,
        expected_type="access",
    )

    if claims is None:
        raise unauthorized("Invalid or expired access token.")

    subject = claims.get("sub")

    if not isinstance(subject, str) or not ObjectId.is_valid(subject):
        raise unauthorized("Invalid token subject.")

    database = get_database()

    user = await database["users"].find_one(
        {"_id": ObjectId(subject)}
    )

    if user is None:
        raise unauthorized("User account was not found.")

    if user.get("is_active") is not True:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive.",
        )

    role = user.get("role")

    if role not in ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account has an invalid role.",
        )

    if role == "Employee":
        employee_id = user.get("employee_id")

        if employee_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No employee record is linked to this account.",
            )

        if isinstance(employee_id, str):
            if not ObjectId.is_valid(employee_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="The linked employee record is invalid.",
                )
            employee_id = ObjectId(employee_id)

        if not isinstance(employee_id, ObjectId):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The linked employee record is invalid.",
            )

        employee = await database["employees"].find_one(
            {"_id": employee_id}
        )

        if employee is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The linked employee record was not found.",
            )

        if employee.get("is_active") is not True:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your employee record is inactive. Access is blocked.",
            )

        if (
            employee.get("employment_status")
            in INACTIVE_EMPLOYMENT_STATUSES
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your employment has ended. Access is blocked.",
            )

        # Normalize the linked ID for downstream scope checks.
        user["employee_id"] = employee_id

    user["id"] = str(user["_id"])
    return user


def require_roles(*allowed_roles: str) -> Callable:
    """Return a dependency permitting only the specified roles."""
    if not allowed_roles:
        raise ValueError("At least one allowed role is required.")

    invalid_roles = set(allowed_roles) - set(ROLES)

    if invalid_roles:
        raise ValueError(
            f"Unknown role(s): {', '.join(sorted(invalid_roles))}"
        )

    async def role_guard(
        current_user: Annotated[
            dict,
            Depends(get_current_user),
        ],
    ) -> dict:
        if current_user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

        return current_user

    return role_guard


def enforce_employee_scope(
    current_user: dict,
    requested_employee_id: str,
) -> None:
    """Prevent an Employee from accessing another employee's records."""
    if current_user.get("role") != "Employee":
        return

    own_employee_id = current_user.get("employee_id")

    if own_employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No employee record is linked to this account.",
        )

    if str(own_employee_id) != str(requested_employee_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only access your own employee records.",
        )


CurrentUser = Annotated[
    dict,
    Depends(get_current_user),
]

AdminUser = Annotated[
    dict,
    Depends(require_roles("Admin")),
]

HRUser = Annotated[
    dict,
    Depends(require_roles("HR")),
]

AdminOrHRUser = Annotated[
    dict,
    Depends(require_roles("Admin", "HR")),
]
