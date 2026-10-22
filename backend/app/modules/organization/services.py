"""
Organization management services.

Handles non-authentication operations: profile retrieval, updates,
deletion, and admin CRUD.  Authentication (registration, login) lives
in ``auth.service``.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, validate_password_policy
from app.modules.organization import repository as org_repo
from app.modules.organization.models import Organization
from app.modules.organization.schemas import (
    AdminResponse,
    OrganizationProfile,
)


# ═════════════════════════════════════════════════════════════════════
# Organization profile
# ═════════════════════════════════════════════════════════════════════


async def get_organization_profile(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> OrganizationProfile:
    """Retrieve the organization's safe public profile."""
    org = await org_repo.get_organization_by_id(db, org_id)
    if org is None:
        raise ValueError("Organization not found.")
    return _to_profile(org)


async def update_organization_profile(
    db: AsyncSession,
    org_id: uuid.UUID,
    *,
    organization_name: str | None = None,
    organization_email: str | None = None,
    organization_phone: str | None = None,
) -> OrganizationProfile:
    """Update an organization's profile fields."""
    org = await org_repo.update_organization(
        db,
        org_id,
        organization_name=organization_name,
        organization_email=organization_email,
        organization_phone=organization_phone,
    )
    if org is None:
        raise ValueError("Organization not found.")
    return _to_profile(org)


async def delete_organization(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> None:
    """Delete an organization and cascade to admins."""
    deleted = await org_repo.delete_organization(db, org_id)
    if not deleted:
        raise ValueError("Organization not found.")


# ═════════════════════════════════════════════════════════════════════
# Admin management (scoped to organization)
# ═════════════════════════════════════════════════════════════════════


async def create_admin_for_organization(
    db: AsyncSession,
    org_id: uuid.UUID,
    *,
    name: str,
    email: str,
    phone: str,
    employee_id: str,
    password: str,
) -> AdminResponse:
    """Create an admin within the calling organization."""
    validate_password_policy(password)
    password_hash = hash_password(password)

    admin = await org_repo.create_admin(
        db,
        organization_id=org_id,
        name=name,
        email=email.strip().lower(),
        phone=phone,
        employee_id=employee_id,
        password_hash=password_hash,
    )
    return _to_admin_response(admin)


async def list_organization_admins(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> list[AdminResponse]:
    """List all admins belonging to the organization."""
    admins = await org_repo.list_admins(db, org_id)
    return [_to_admin_response(a) for a in admins]


async def get_organization_admin(
    db: AsyncSession,
    org_id: uuid.UUID,
    admin_id: uuid.UUID,
) -> AdminResponse:
    """Get a single admin, enforcing organization ownership."""
    admin = await org_repo.get_admin_by_id(db, org_id, admin_id)
    if admin is None:
        raise ValueError("Admin not found.")
    return _to_admin_response(admin)


async def update_organization_admin(
    db: AsyncSession,
    org_id: uuid.UUID,
    admin_id: uuid.UUID,
    **updates: object,
) -> AdminResponse:
    """Update an admin's fields."""
    admin = await org_repo.update_admin(db, org_id, admin_id, **updates)
    if admin is None:
        raise ValueError("Admin not found.")
    return _to_admin_response(admin)


async def delete_organization_admin(
    db: AsyncSession,
    org_id: uuid.UUID,
    admin_id: uuid.UUID,
) -> None:
    """Delete an admin, enforcing organization ownership."""
    deleted = await org_repo.delete_admin(db, org_id, admin_id)
    if not deleted:
        raise ValueError("Admin not found.")


# ═════════════════════════════════════════════════════════════════════
# Mappers (ORM → response schemas)
# ═════════════════════════════════════════════════════════════════════


def _to_profile(org: Organization) -> OrganizationProfile:
    return OrganizationProfile(
        unique_id=org.id,
        organization_name=org.organization_name,
        organization_email=org.organization_email,
        organization_phone=org.organization_phone,
        is_active=org.is_active,
        is_verified=org.is_verified,
    )


def _to_admin_response(admin) -> AdminResponse:
    return AdminResponse(
        unique_id=admin.id,
        admin_name=admin.admin_name,
        admin_email=admin.admin_email,
        admin_phone=admin.admin_phone,
        admin_employee_id=admin.admin_employee_id,
        is_active=admin.is_active,
        is_verified=admin.is_verified,
    )
