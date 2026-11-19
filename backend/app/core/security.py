"""Password hashing (Argon2id) and JWT access tokens.

Kept in `core` because both are cross-cutting primitives: modules must never
implement their own hashing or token handling.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any, Final

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings
from app.core.errors import ApiError

PASSWORD_MIN_LENGTH: Final[int] = 10
PASSWORD_MAX_LENGTH: Final[int] = 128
TOKEN_TYPE: Final[str] = "access"

# Small deny-list of the most common passwords. A production system would use a
# larger corpus (e.g. HIBP); this covers the obvious cases without a dependency.
_COMMON_PASSWORDS: Final[frozenset[str]] = frozenset(
    {
        "password",
        "password1",
        "password123",
        "passw0rd",
        "qwerty123",
        "1234567890",
        "12345678910",
        "admin12345",
        "letmein123",
        "welcome123",
        "iloveyou1",
        "changeme123",
        "education1",
        "student123",
        "teacher123",
    }
)


@lru_cache
def _password_hasher() -> PasswordHasher:
    """Argon2id hasher with RFC 9106 low-memory recommended parameters."""
    return PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)


def normalize_email(email: str) -> str:
    """Normalise an email: trim surrounding whitespace and lowercase it."""
    return email.strip().lower()


def validate_password_strength(password: str, *, email: str | None = None) -> list[str]:
    """Return a list of human-readable problems with the password (empty = valid)."""
    problems: list[str] = []

    if len(password) < PASSWORD_MIN_LENGTH:
        problems.append(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.")
    if len(password) > PASSWORD_MAX_LENGTH:
        problems.append(f"Password must be at most {PASSWORD_MAX_LENGTH} characters long.")
    if password != password.strip():
        problems.append("Password must not start or end with whitespace.")
    if not any(ch.isalpha() for ch in password):
        problems.append("Password must contain at least one letter.")
    if not any(ch.isdigit() for ch in password):
        problems.append("Password must contain at least one digit.")
    if password.lower() in _COMMON_PASSWORDS:
        problems.append("Password is too common.")
    if email is not None and password.lower() == normalize_email(email):
        problems.append("Password must not be the same as the email address.")

    return problems


def hash_password(password: str) -> str:
    """Hash a password with Argon2id. The plaintext is never stored."""
    return _password_hasher().hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time password check; any hashing error is treated as a mismatch."""
    try:
        return _password_hasher().verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    """True when the stored hash uses outdated parameters."""
    try:
        return _password_hasher().check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    """Create a signed access token.

    Returns:
        tuple of (token, lifetime in seconds)
    """
    settings = get_settings()
    lifetime = timedelta(minutes=settings.access_token_expire_minutes)
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": TOKEN_TYPE,
        "iss": settings.jwt_issuer,
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str) -> dict[str, Any]:
    """Validate signature, issuer, expiry and token type.

    Raises:
        ApiError: 401 with a stable code when the token is unusable.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise ApiError(
            401,
            "token_expired",
            "Access token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise ApiError(
            401,
            "invalid_token",
            "Access token is invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("type") != TOKEN_TYPE:
        raise ApiError(
            401,
            "invalid_token",
            "Access token is invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload
