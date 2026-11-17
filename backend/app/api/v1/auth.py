
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.audit import log_audit_event
from app.core.config import settings
from app.core.database import get_database
from app.core.dependencies import (
    AdminOrHRUser,
    AdminUser,
    CurrentUser,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.documents import CompanySettings, User
from app.schemas.auth import (
    AuthTokenResponse,
    ChangePasswordRequest,
    EmployeeAccountCreateRequest,
    HRAccountCreateRequest,
    LoginRequest,
    MessageResponse,
    RefreshTokenRequest,
    RegisterAdminRequest,
    UserPublic,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def public_user(user: dict) -> UserPublic:
    employee_id = user.get("employee_id")

    return UserPublic(
        id=str(user["_id"]),
        email=user["email"],
        role=user["role"],
        is_active=user.get("is_active") is True,
        employee_id=str(employee_id) if employee_id else None,
    )


async def ensure_employee_can_access(database, user: dict) -> None:
    """Block login and token refresh for inactive or former employees."""

    if user.get("role") != "Employee":
        return

    employee_id = user.get("employee_id")

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
            detail="No employee record is linked to this account.",
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

    if employee.get("employment_status") in {"Resigned", "Terminated"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your employment has ended. Access is blocked.",
        )
    # Require successful face enrollment before creating an employee account.
    face_enrollment = await database["face_enrollments"].find_one(
        {"employee_id": employee_id},
        {"_id": 1},
    )

    if face_enrollment is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
            "Face enrollment is required before creating "
            "the employee login account."
            ),
        )


async def ensure_auth_indexes(database) -> None:
    """Create indexes enforcing authentication and initial setup rules."""

    users = database["users"]
    sessions = database["refresh_sessions"]
    company_settings = database["company_settings"]

    await users.create_index(
        [("email", 1)],
        unique=True,
        name="unique_user_email",
    )

    await users.create_index(
        [("employee_id", 1)],
        unique=True,
        partialFilterExpression={
            "employee_id": {"$type": "objectId"}
        },
        name="unique_user_employee_link",
    )

    await users.create_index(
        [("is_initial_admin", 1)],
        unique=True,
        partialFilterExpression={"is_initial_admin": True},
        name="unique_initial_admin",
    )

    await sessions.create_index(
        [("jti", 1)],
        unique=True,
        name="unique_refresh_jti",
    )

    await sessions.create_index(
        [("expires_at", 1)],
        expireAfterSeconds=0,
        name="refresh_session_expiry",
    )

    await company_settings.create_index(
        [("singleton_key", 1)],
        unique=True,
        name="unique_company_settings",
    )


async def issue_tokens(database, user: dict) -> AuthTokenResponse:
    """Issue an access token and persist its refresh-token session."""

    user_id = str(user["_id"])

    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    claims = decode_token(
        refresh_token,
        expected_type="refresh",
    )

    if claims is None:
        raise RuntimeError(
            "Could not validate the newly created refresh token."
        )

    now = datetime.now(timezone.utc)

    await database["refresh_sessions"].insert_one(
        {
            "jti": claims["jti"],
            "user_id": user["_id"],
            "created_at": now,
            "expires_at": datetime.fromtimestamp(
                claims["exp"],
                tz=timezone.utc,
            ),
            "revoked_at": None,
        }
    )

    return AuthTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=public_user(user),
    )


@router.post(
    "/register-admin",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_initial_admin(payload: RegisterAdminRequest):
    """Create the initial Admin account and company settings."""

    database = get_database()
    await ensure_auth_indexes(database)

    users = database["users"]
    company_collection = database["company_settings"]
    admin_id = None

    if await users.find_one({"role": "Admin"}, {"_id": 1}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An Admin already exists. Initial registration is closed.",
        )

    if await company_collection.find_one(
        {"singleton_key": "company"},
        {"_id": 1},
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Company setup has already been completed.",
        )

    try:
        admin = User(
            email=payload.email,
            password_hash=hash_password(payload.password),
            role="Admin",
            is_active=True,
            employee_id=None,
        )

        admin_document = admin.model_dump(
            by_alias=True,
            mode="python",
            exclude_none=True,
        )
        admin_document["is_initial_admin"] = True

        result = await users.insert_one(admin_document)
        admin_id = result.inserted_id
        admin_document["_id"] = admin_id

        company = CompanySettings(
            company_name=payload.company_name,
            company_email=payload.company_email,
        )

        company_document = company.model_dump(
            by_alias=True,
            mode="python",
            exclude_none=True,
        )
        company_document["singleton_key"] = "company"

        token_response = await issue_tokens(
            database,
            admin_document,
        )

        await company_collection.insert_one(company_document)

        return token_response

    except DuplicateKeyError as exc:
        if admin_id is not None:
            await database["refresh_sessions"].delete_many(
                {"user_id": admin_id}
            )
            await users.delete_one(
                {
                    "_id": admin_id,
                    "is_initial_admin": True,
                }
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Initial setup has already started or completed. "
                "Please check whether an Admin account exists."
            ),
        ) from exc

    except Exception:
        if admin_id is not None:
            await database["refresh_sessions"].delete_many(
                {"user_id": admin_id}
            )
            await users.delete_one(
                {
                    "_id": admin_id,
                    "is_initial_admin": True,
                }
            )
        raise


@router.post("/login", response_model=AuthTokenResponse)
async def login(payload: LoginRequest):
    database = get_database()
    await ensure_auth_indexes(database)

    email = str(payload.email).lower()

    user = await database["users"].find_one(
        {"email": email}
    )

    if not user or not verify_password(
        payload.password,
        user.get("password_hash", ""),
    ):
        await log_audit_event(
            database=database,
            actor={
                "email": email,
                "role": "Unknown",
            },
            action="USER_LOGIN_FAILED",
            target_type="user",
            details={
                "email": email,
                "reason": "Invalid email or password",
            },
        )
        raise unauthorized()

    if user.get("is_active") is not True:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive. Contact an administrator.",
        )

    if user.get("role") not in ("Admin", "HR", "Employee"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has an invalid role.",
        )

    await ensure_employee_can_access(database, user)

    token_response = await issue_tokens(database, user)

    await log_audit_event(
        database=database,
        actor=user,
        action="USER_LOGIN",
        target_type="user",
        target_id=str(user["_id"]),
        details={
            "email": user["email"],
            "role": user["role"],
        },
    )

    return token_response


@router.post(
    "/create-hr-account",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_hr_account(
    payload: HRAccountCreateRequest,
    current_user: AdminUser,
):
    """Create an HR account. Admin access is required."""

    database = get_database()
    await ensure_auth_indexes(database)

    users = database["users"]
    email = str(payload.email).lower()

    if await users.find_one(
        {"email": email},
        {"_id": 1},
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    hr_user = User(
        email=email,
        password_hash=hash_password(payload.initial_password),
        role="HR",
        is_active=True,
        employee_id=None,
    )

    document = hr_user.model_dump(
        by_alias=True,
        mode="python",
        exclude_none=True,
    )

    try:
        result = await users.insert_one(document)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from exc

    document["_id"] = result.inserted_id

    await log_audit_event(
        database=database,
        actor=current_user,
        action="HR_ACCOUNT_CREATED",
        target_type="user",
        target_id=str(result.inserted_id),
        details={
            "email": email,
            "role": "HR",
        },
    )

    return public_user(document)


@router.post(
    "/create-employee-account",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_employee_account(
    payload: EmployeeAccountCreateRequest,
    current_user: AdminOrHRUser,
):
    """Create login credentials for an existing active employee."""

    database = get_database()
    await ensure_auth_indexes(database)

    employee_id = ObjectId(payload.employee_id)

    employee = await database["employees"].find_one(
        {"_id": employee_id}
    )

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found.",
        )

    if employee.get("employment_status") != "Active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only active employees can receive login accounts.",
        )
    
    face_enrollment = await database["face_enrollments"].find_one(
        {"employee_id": employee_id},
        {"_id": 1},
    )

    if not face_enrollment:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Enroll this employee's face before creating a login account.",
        )


    email = str(employee["email"]).lower()

    existing_user = await database["users"].find_one(
        {
            "$or": [
                {"email": email},
                {"employee_id": employee_id},
            ]
        }
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A user account already uses this email "
                "or is already linked to this employee."
            ),
        )

    user = User(
        email=email,
        password_hash=hash_password(payload.initial_password),
        role="Employee",
        is_active=True,
        employee_id=employee_id,
    )

    document = user.model_dump(
        by_alias=True,
        mode="python",
        exclude_none=True,
    )

    try:
        result = await database["users"].insert_one(document)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "An account already exists for this employee or email."
            ),
        ) from exc

    await log_audit_event(
        database=database,
        actor=current_user,
        action="EMPLOYEE_ACCOUNT_CREATED",
        target_type="user",
        target_id=str(result.inserted_id),
        details={
            "email": email,
            "role": "Employee",
            "employee_id": str(employee_id),
        },
    )

    return MessageResponse(
        message="Employee login account created successfully."
    )


@router.post("/refresh", response_model=AuthTokenResponse)
async def refresh_access_token(payload: RefreshTokenRequest):
    database = get_database()
    await ensure_auth_indexes(database)

    claims = decode_token(
        payload.refresh_token,
        expected_type="refresh",
    )

    if claims is None:
        raise unauthorized()

    subject = claims.get("sub")
    jti = claims.get("jti")

    if (
        not isinstance(subject, str)
        or not ObjectId.is_valid(subject)
        or not isinstance(jti, str)
    ):
        raise unauthorized()

    now = datetime.now(timezone.utc)

    old_session = await database["refresh_sessions"].find_one_and_update(
        {
            "jti": jti,
            "user_id": ObjectId(subject),
            "revoked_at": None,
            "expires_at": {"$gt": now},
        },
        {"$set": {"revoked_at": now}},
        return_document=ReturnDocument.BEFORE,
    )

    if old_session is None:
        raise unauthorized()

    user = await database["users"].find_one(
        {"_id": ObjectId(subject)}
    )

    if not user or user.get("is_active") is not True:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive or no longer exists.",
        )

    if user.get("role") not in ("Admin", "HR", "Employee"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has an invalid role.",
        )

    await ensure_employee_can_access(database, user)

    return await issue_tokens(database, user)


@router.post(
    "/change-password",
    response_model=MessageResponse,
)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUser,
):
    if not verify_password(
        payload.current_password,
        current_user.get("password_hash", ""),
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    if verify_password(
        payload.new_password,
        current_user.get("password_hash", ""),
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password.",
        )

    database = get_database()
    user_id = current_user["_id"]
    now = datetime.now(timezone.utc)

    await database["users"].update_one(
        {"_id": user_id},
        {
            "$set": {
                "password_hash": hash_password(payload.new_password),
                "updated_at": now,
            }
        },
    )

    await database["refresh_sessions"].update_many(
        {
            "user_id": user_id,
            "revoked_at": None,
        },
        {"$set": {"revoked_at": now}},
    )

    await log_audit_event(
        database=database,
        actor=current_user,
        action="USER_PASSWORD_CHANGED",
        target_type="user",
        target_id=str(user_id),
        details={
            "email": current_user["email"],
            "role": current_user["role"],
            "refresh_sessions_revoked": True,
        },
    )

    return MessageResponse(
        message=(
            "Password changed successfully. "
            "Please sign in again on other devices."
        )
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    payload: RefreshTokenRequest,
    current_user: CurrentUser,
):
    database = get_database()
    await ensure_auth_indexes(database)

    claims = decode_token(
        payload.refresh_token,
        expected_type="refresh",
    )

    if claims is None:
        raise unauthorized()

    subject = claims.get("sub")
    jti = claims.get("jti")

    if (
        not isinstance(subject, str)
        or not ObjectId.is_valid(subject)
        or not isinstance(jti, str)
    ):
        raise unauthorized()

    if subject != str(current_user["_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot revoke another user's session.",
        )

    now = datetime.now(timezone.utc)

    await database["refresh_sessions"].update_one(
        {
            "jti": jti,
            "user_id": ObjectId(subject),
            "revoked_at": None,
        },
        {"$set": {"revoked_at": now}},
    )

    await log_audit_event(
        database=database,
        actor=current_user,
        action="USER_LOGOUT",
        target_type="user",
        target_id=str(current_user["_id"]),
        details={
            "email": current_user["email"],
            "role": current_user["role"],
        },
    )

    return MessageResponse(
        message="Logged out successfully."
    )
