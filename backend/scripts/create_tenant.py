"""Provision a new tenant (cinema) together with its first admin account.

Tenants are created by the platform operator, not through a public API,
so this lives as an operations script rather than an endpoint.

Usage:
    python -m scripts.create_tenant --name "Cineplex Bonn" --slug cineplex-bonn \
        --email admin@cineplex-bonn.de --password secret123
"""

import argparse
import asyncio

from sqlmodel import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Cinema, CinemaAdmin


async def create_tenant(name: str, slug: str, email: str, password: str) -> None:
    async with SessionLocal() as db:
        existing_cinema = await db.execute(select(Cinema).where(Cinema.slug == slug))
        if existing_cinema.scalar_one_or_none() is not None:
            raise SystemExit(f"A cinema with slug '{slug}' already exists.")

        existing_admin = await db.execute(
            select(CinemaAdmin).where(CinemaAdmin.email == email)
        )
        if existing_admin.scalar_one_or_none() is not None:
            raise SystemExit(f"An admin with e-mail '{email}' already exists.")

        cinema = Cinema(name=name, slug=slug)
        db.add(cinema)
        await db.flush()  # assigns cinema.id without committing yet

        admin = CinemaAdmin(
            cinema_id=cinema.id,
            email=email,
            password_hash=hash_password(password),
        )
        db.add(admin)
        await db.commit()

        print(f"Created cinema '{name}' (id={cinema.id}, slug={slug})")
        print(f"Created admin '{email}' (id={admin.id})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a cinema and its first admin.")
    parser.add_argument("--name", required=True, help="display name of the cinema")
    parser.add_argument("--slug", required=True, help="url slug, e.g. cineplex-bonn")
    parser.add_argument("--email", required=True, help="login e-mail of the admin")
    parser.add_argument("--password", required=True, help="plaintext password, will be hashed")
    args = parser.parse_args()

    asyncio.run(create_tenant(args.name, args.slug, args.email, args.password))


if __name__ == "__main__":
    main()
