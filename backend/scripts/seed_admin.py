"""Create or reset the local test administrator account.

Run from the repository root:

    .venv\\Scripts\\python.exe backend\\scripts\\seed_admin.py
    admin@gmail.com
    1234567890
"""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.core.security import hash_password
from app.modules.admin.models import Admin
from app.modules.organization.models import Organization


ADMIN_EMAIL = "admin@gmail.com"
ADMIN_PASSWORD = "1234567890"
ORGANIZATION_EMAIL = "bootstrap-admin-org@sentinellog.local"
ORGANIZATION_PHONE = "+10000000001"
ADMIN_PHONE = "+10000000000"
EMPLOYEE_ID = "BOOTSTRAP-ADMIN"


async def seed_admin() -> uuid.UUID:
    """Create the bootstrap organization and upsert the test administrator."""
    async with AsyncSessionLocal() as db:
        admin_result = await db.execute(
            select(Admin).where(Admin.admin_email == ADMIN_EMAIL)
        )
        admin = admin_result.scalars().first()

        if admin is None:
            organization_result = await db.execute(
                select(Organization).where(
                    Organization.organization_email == ORGANIZATION_EMAIL
                )
            )
            organization = organization_result.scalars().first()

            if organization is None:
                organization = Organization(
                    organization_name="SentinelLog Bootstrap Organization",
                    organization_email=ORGANIZATION_EMAIL,
                    organization_phone=ORGANIZATION_PHONE,
                    organization_hashed_password=hash_password(ADMIN_PASSWORD),
                    is_active=True,
                    is_verified=True,
                )
                db.add(organization)
                await db.flush()

            admin = Admin(
                admin_name="SentinelLog Administrator",
                admin_email=ADMIN_EMAIL,
                admin_phone=ADMIN_PHONE,
                admin_hashed_password=hash_password(ADMIN_PASSWORD),
                admin_employee_id=EMPLOYEE_ID,
                admin_organization_id=organization.id,
                is_active=True,
                is_verified=True,
            )
            db.add(admin)
        else:
            admin.admin_hashed_password = hash_password(ADMIN_PASSWORD)
            admin.is_active = True
            admin.is_verified = True

        await db.commit()
        await db.refresh(admin)
        return admin.id


async def main() -> None:
    admin_id = await seed_admin()
    print(f"Seeded admin {ADMIN_EMAIL} ({admin_id})")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
