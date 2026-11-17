
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

from jose import JWTError, jwt
import bcrypt

from app.core.config import settings




TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    if not isinstance(password, str) or not password:
        raise ValueError("Password cannot be empty.")

    password_bytes = password.encode("utf-8")

    if len(password_bytes) > 72:
        raise ValueError(
            "Password must not exceed 72 UTF-8 bytes."
        )

    hashed = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt(),
    )

    return hashed.decode("utf-8")


def verify_password(
    password: str,
    hashed_password: str,
) -> bool:
    if not isinstance(password, str) or not isinstance(
        hashed_password, str
    ):
        return False

    password_bytes = password.encode("utf-8")

    if not password_bytes or len(password_bytes) > 72:
        return False

    try:
        return bcrypt.checkpw(
            password_bytes,
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError, UnicodeError):
        return False


def create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a signed access or refresh JWT."""
    if not subject.strip():
        raise ValueError("Token subject cannot be empty.")

    if token_type == "access":
        default_expiry = timedelta(
            minutes=settings.access_token_expire_minutes
        )
    else:
        default_expiry = timedelta(
            days=settings.refresh_token_expire_days
        )

    now = datetime.now(timezone.utc)
    expiry = now + (
        expires_delta if expires_delta is not None else default_expiry
    )

    claims: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": expiry,
        "jti": str(uuid4()),
    }

    # Reserved claims cannot be overridden by callers.
    if extra_claims:
        reserved = {"sub", "type", "iat", "exp", "jti"}
        if reserved.intersection(extra_claims):
            raise ValueError(
                "Extra claims cannot override reserved JWT claims."
            )
        claims.update(extra_claims)

    secret = settings.secret_key.get_secret_value()
    if not secret:
        raise RuntimeError(
            "SECRET_KEY is not configured. Set it in the backend .env."
        )

    return jwt.encode(
        claims,
        secret,
        algorithm=settings.jwt_algorithm,
    )


def create_access_token(
    subject: str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a short-lived access token."""
    return create_token(
        subject=subject,
        token_type="access",
        extra_claims=extra_claims,
    )


def create_refresh_token(subject: str) -> str:
    """Create a longer-lived refresh token."""
    return create_token(
        subject=subject,
        token_type="refresh",
    )


def decode_token(
    token: str,
    expected_type: TokenType = "access",
) -> dict[str, Any] | None:
    """
    Validate a JWT signature, expiry, and token type.

    Returns the decoded claims if valid; otherwise returns None.
    """
    secret = settings.secret_key.get_secret_value()
    if not secret:
        return None

    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[settings.jwt_algorithm],
            options={
                "require_sub": True,
                "require_exp": True,
                "require_iat": True,
                "require_jti": True,
            },
        )

        if claims.get("type") != expected_type:
            return None

        if not isinstance(claims.get("sub"), str):
            return None

        if not claims["sub"].strip():
            return None

        return claims

    except (JWTError, TypeError, ValueError):
        return None
