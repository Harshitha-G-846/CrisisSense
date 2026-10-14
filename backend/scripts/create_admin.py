#!/usr/bin/env python3
"""
create_admin.py — ResQ-Sense Controlled Administrator Provisioning CLI

Provisions an authorized emergency command administrator account in the ResQ-Sense database.
Passwords are encrypted using salted bcrypt hashing.
Never writes plaintext passwords or modifies existing incident/resource records.

Usage:
    python backend/scripts/create_admin.py --email admin@resqsense.org --password "AdminPass123!" --name "Emergency Commander"
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure backend root is on Python path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from member3.database import SessionLocal, engine, ensure_schema_compatibility
from member3.models import User
from auth import (
    hash_password,
    validate_email_address,
    validate_password_strength,
)


def provision_admin(
    email: str,
    password: str,
    name: str = "Authorized Emergency Commander",
    role: str = "authority",
    target_engine=None,
    db_session=None,
) -> User:
    """Create or update an administrator account with salted bcrypt password hashing."""
    normalized_email = validate_email_address(email)
    validate_password_strength(password)

    actual_engine = target_engine if target_engine is not None else engine
    ensure_schema_compatibility(actual_engine)

    close_session = False
    if db_session is not None:
        db = db_session
    else:
        db = SessionLocal()
        close_session = True

    try:
        user = db.scalars(select(User).where(User.email == normalized_email)).first()

        pw_hash = hash_password(password)

        if user is not None:
            user.full_name = name.strip() or user.full_name
            user.password_hash = pw_hash
            user.role = role
            db.commit()
            db.refresh(user)
            print(f"[*] Updated existing user '{user.email}' to role '{user.role}'. ID: {user.id}")
            return user
        else:
            user = User(
                full_name=name.strip(),
                email=normalized_email,
                password_hash=pw_hash,
                role=role,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"[+] Successfully provisioned new administrator '{user.email}' with role '{user.role}'. ID: {user.id}")
            return user
    finally:
        if close_session:
            db.close()


def main():
    parser = argparse.ArgumentParser(description="Provision ResQ-Sense Administrator Account")
    parser.add_argument("--email", default=os.environ.get("ADMIN_EMAIL"), help="Admin email address")
    parser.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD"), help="Admin password (min 8 chars, letter + digit)")
    parser.add_argument("--name", default=os.environ.get("ADMIN_NAME", "Command Authority"), help="Admin full name")

    args = parser.parse_args()

    email = args.email
    password = args.password
    name = args.name

    if not email:
        email = input("Enter administrator email address: ").strip()
    if not password:
        import getpass
        password = getpass.getpass("Enter administrator password: ").strip()

    try:
        user = provision_admin(email=email, password=password, name=name)
        print(f"[OK] Administrator {user.email} is ready to authenticate.")
    except Exception as exc:
        print(f"[ERROR] Failed to provision administrator: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
