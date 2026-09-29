"""Set a new password for an existing cinema admin.

There is no password-reset endpoint yet, and bcrypt hashes cannot be reversed,
so a forgotten password can only be replaced - by the platform operator, from
the machine that has database access.

Usage:
    python -m scripts.reset_password --email admin@cineplex-bonn.de --password new-secret
"""

import argparse
import asyncio

from sqlmodel import select

from app.core.database import SessionLocal
from app.core.security import MAX_PASSWORD_BYTES, hash_password
from app.models import CinemaAdmin


def valid_password(value: str) -> str:
    """bcrypt refuses anything past 72 bytes instead of truncating it."""
    if len(value.encode()) > MAX_PASSWORD_BYTES:
        raise argparse.ArgumentTypeError(
            f"password must not exceed {MAX_PASSWORD_BYTES} bytes"
        )
    return value


async def reset_password(email: str, password: str) -> None:
    async with SessionLocal() as db:
        result = await db.execute(
            select(CinemaAdmin).where(CinemaAdmin.email == email)
        )
        admin = result.scalar_one_or_none()
        if admin is None:
            raise SystemExit(f"No admin with e-mail '{email}'.")

        admin.password_hash = hash_password(password)
        db.add(admin)
        await db.commit()

        # any token issued before this point stays valid until it expires -
        # the backend has no denylist yet
        print(f"Password updated for '{email}' (id={admin.id})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset a cinema admin's password.")
    parser.add_argument("--email", required=True, help="login e-mail of the admin")
    parser.add_argument(
        "--password", required=True, type=valid_password, help="the new password"
    )
    args = parser.parse_args()

    asyncio.run(reset_password(args.email, args.password))


if __name__ == "__main__":
    main()
