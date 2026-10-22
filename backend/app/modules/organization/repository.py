"""
Database access layer for organization and admin management.

Handles CRUD operations scoped to the calling organization.
All queries enforce tenant isolation via ``organization_id``.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import Admin
from app.modules.organization.models import Organization


# ═════════════════════════════════════════════════════════════════════
# Organization CRUD
# ═════════════════════════════════════════════════════════════════════


async def create_organization(
    db: AsyncSession,
    *,
    name: str,
    email: str,
    phone: str,
    password_hash: str,
) -> Organization:
    """Persist a new organization."""
    org = Organization(
        organization_name=name,
        organization_email=email,
        organization_phone=phone,
        organization_hashed_password=password_hash,
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


async def get_organization_by_id(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> Organization | None:
    stmt = select(Organization).where(Organization.id == org_id)
    result = await db.execute(stmt)
    return result.scalars().first()


async def get_organization_by_email(
    db: AsyncSession,
    email: str,
) -> Organization | None:
    stmt = select(Organization).where(
        Organization.organization_email == email
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def update_organization(
    db: AsyncSession,
    org_id: uuid.UUID,
    **updates: object,
) -> Organization | None:
    """
    Update an organization's fields.

    Only non-None values in ``updates`` are applied.
    """
    # Filter out None values
    values = {k: v for k, v in updates.items() if v is not None}
    if not values:
        return await get_organization_by_id(db, org_id)

    stmt = (
        update(Organization)
        .where(Organization.id == org_id)
        .values(**values)
    )
    await db.execute(stmt)
    await db.commit()
    return await get_organization_by_id(db, org_id)


async def delete_organization(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> bool:
    stmt = delete(Organization).where(Organization.id == org_id)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0


# ═════════════════════════════════════════════════════════════════════
# Admin CRUD (scoped to organization)
# ═════════════════════════════════════════════════════════════════════


async def create_admin(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    name: str,
    email: str,
    phone: str,
    employee_id: str,
    password_hash: str,
) -> Admin:
    """Create an admin within the given organization."""
    admin = Admin(
        admin_name=name,
        admin_email=email,
        admin_phone=phone,
        admin_employee_id=employee_id,
        admin_hashed_password=password_hash,
        admin_organization_id=organization_id,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin


async def list_admins(
    db: AsyncSession,
    organization_id: uuid.UUID,
) -> list[Admin]:
    """List all admins belonging to the given organization."""
    stmt = select(Admin).where(
        Admin.admin_organization_id == organization_id
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_admin_by_id(
    db: AsyncSession,
    organization_id: uuid.UUID,
    admin_id: uuid.UUID,
) -> Admin | None:
    """Get a single admin, enforcing organization ownership."""
    stmt = select(Admin).where(
        Admin.id == admin_id,
        Admin.admin_organization_id == organization_id,
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def update_admin(
    db: AsyncSession,
    organization_id: uuid.UUID,
    admin_id: uuid.UUID,
    **updates: object,
) -> Admin | None:
    """Update an admin's fields, enforcing organization ownership."""
    values = {k: v for k, v in updates.items() if v is not None}
    if not values:
        return await get_admin_by_id(db, organization_id, admin_id)

    stmt = (
        update(Admin)
        .where(
            Admin.id == admin_id,
            Admin.admin_organization_id == organization_id,
        )
        .values(**values)
    )
    await db.execute(stmt)
    await db.commit()
    return await get_admin_by_id(db, organization_id, admin_id)


async def delete_admin(
    db: AsyncSession,
    organization_id: uuid.UUID,
    admin_id: uuid.UUID,
) -> bool:
    """Delete an admin, enforcing organization ownership."""
    stmt = delete(Admin).where(
        Admin.id == admin_id,
        Admin.admin_organization_id == organization_id,
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0
