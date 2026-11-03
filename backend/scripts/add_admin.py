"""Let a Keycloak account manage an existing cinema.

Accounts are created in Keycloak (see k8s/README.md); the application only
records which account manages which cinema. A cinema may have several admins,
an account manages exactly one cinema.

Usage:
    python -m scripts.add_admin --slug cineplex-bonn \
        --user-id 4558cd31-9dd7-45f8-93b8-30199851a88a
"""

import argparse
import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.database import SessionLocal
from app.models import Cinema, CinemaAdmin


def keycloak_user_id(value: str) -> str:
    """Keycloak's user ids are UUIDs.

    Checking the format catches a pasted username or e-mail address, which
    would otherwise be stored as a link that no token ever matches.
    """
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise argparse.ArgumentTypeError(
            "expected the ID shown in Keycloak's user details, "
            "e.g. 4558cd31-9dd7-45f8-93b8-30199851a88a"
        ) from None


async def link_admin(db: AsyncSession, cinema: Cinema, user_id: str) -> CinemaAdmin:
    """Stage the admin row in `db`; committing is up to the caller."""
    existing = await db.execute(
        select(CinemaAdmin).where(CinemaAdmin.subject == user_id)
    )
    if existing.scalar_one_or_none() is not None:
        raise SystemExit(f"Account {user_id} already manages a cinema.")

    admin = CinemaAdmin(cinema_id=cinema.id, subject=user_id)
    db.add(admin)
    return admin


async def add_admin(slug: str, user_id: str) -> None:
    async with SessionLocal() as db:
        result = await db.execute(select(Cinema).where(Cinema.slug == slug))
        cinema = result.scalar_one_or_none()
        if cinema is None:
            raise SystemExit(f"No cinema with slug '{slug}'.")

        admin = await link_admin(db, cinema, user_id)
        await db.commit()

        print(f"Account {user_id} now manages '{cinema.name}' (admin id={admin.id})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Link a Keycloak account to a cinema.")
    parser.add_argument("--slug", required=True, help="url slug of the cinema")
    parser.add_argument(
        "--user-id", required=True, type=keycloak_user_id,
        help="ID of the Keycloak account",
    )
    args = parser.parse_args()

    asyncio.run(add_admin(args.slug, args.user_id))


if __name__ == "__main__":
    main()
