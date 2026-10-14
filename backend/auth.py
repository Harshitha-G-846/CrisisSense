"""
auth.py - Citizen Authentication, Password Security & JWT Management
Handles salted bcrypt password hashing, input validation, JWT token issuance,
and role-based authorization for ResQ-Sense.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from member3.database import get_db
from member3.models import User

# Configuration loaded from environment variables
JWT_SECRET = os.environ.get(
    "JWT_SECRET",
    "resq-sense-dev-secret-key-must-be-at-least-32-bytes-long-for-jwt-hs256-security-2026",
)
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
)  # 24 hours default

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
)


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password with a unique cryptographic salt using bcrypt."""
    if not plain_password:
        raise ValueError("Password cannot be empty.")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored salted bcrypt hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def validate_email_address(email: str) -> str:
    """Validate and normalize an email address."""
    if not email or not isinstance(email, str):
        raise ValueError("Email address is required.")
    normalized = email.strip().lower()
    if len(normalized) > 254 or not EMAIL_REGEX.match(normalized):
        raise ValueError("Invalid email address format.")
    return normalized


def normalize_email(email: str) -> str:
    """Normalize email address by stripping whitespace and lowercasing."""
    return validate_email_address(email)



def validate_password_strength(password: str) -> None:
    """Enforce reasonable password complexity requirements."""
    if not password or not isinstance(password, str):
        raise ValueError("Password is required.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if not any(c.isalpha() for c in password):
        raise ValueError("Password must contain at least one letter.")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one number.")


def create_access_token(
    user_id: str,
    email: str,
    role: str = "citizen",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token for a citizen or authority user."""
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "iat": now,
        "exp": expire,
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.InvalidTokenError, Exception):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user_optional(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Extract and authenticate the user from the Authorization header if present.

    Returns None if no Authorization header is provided.
    Raises 401 if an invalid or expired token is provided.
    """
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected 'Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account associated with this token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Require an authenticated user. Raises 401 if unauthenticated."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = get_current_user_optional(authorization=authorization, db=db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_authority(user: Optional[User]) -> User:
    """Ensure that authority-only operations require authenticated administrator credentials."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: Administrator credentials required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.role not in ("authority", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Authority operations require administrator privileges.",
        )
    return user


def get_current_authority_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency requiring an authenticated administrator user."""
    user = get_current_user(authorization=authorization, db=db)
    return require_authority(user)


def get_current_citizen_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency requiring an authenticated citizen user."""
    user = get_current_user(authorization=authorization, db=db)
    if user.role != "citizen":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Citizen dashboard is only accessible to citizen accounts.",
        )
    return user
