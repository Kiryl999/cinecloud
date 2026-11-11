"""Provision a new tenant (cinema) together with its first admin.

Admins usually open their cinema themselves, in the app right after they
register (POST /api/cinemas/). This is the operator's way to do it for an
account, e.g. one that exists in Keycloak already (see k8s/README.md);
further admins are added with scripts/add_admin.py.

Usage:
    python -m scripts.create_tenant --name "Cineplex Bonn" --slug cineplex-bonn \
        --user-id 4558cd31-9dd7-45f8-93b8-30199851a88a
"""

import argparse
import asyncio

from sqlmodel import select

from app.core.database import SessionLocal
from app.models import Cinema
from scripts.add_admin import keycloak_user_id, link_admin


async def create_tenant(name: str, slug: str, user_id: str) -> None:
    async with SessionLocal() as db:
        existing_cinema = await db.execute(select(Cinema).where(Cinema.slug == slug))
        if existing_cinema.scalar_one_or_none() is not None:
            raise SystemExit(f"A cinema with slug '{slug}' already exists.")

        cinema = Cinema(name=name, slug=slug)
        db.add(cinema)
        await db.flush()  # assigns cinema.id without committing yet

        admin = await link_admin(db, cinema, user_id)
        await db.commit()

        print(f"Created cinema '{name}' (id={cinema.id}, slug={slug})")
        print(f"Account {user_id} manages it (admin id={admin.id})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a cinema and its first admin.")
    parser.add_argument("--name", required=True, help="display name of the cinema")
    parser.add_argument("--slug", required=True, help="url slug, e.g. cineplex-bonn")
    parser.add_argument(
        "--user-id", required=True, type=keycloak_user_id,
        help="ID of the admin's Keycloak account",
    )
    args = parser.parse_args()

    asyncio.run(create_tenant(args.name, args.slug, args.user_id))


if __name__ == "__main__":
    main()
