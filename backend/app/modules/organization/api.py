"""
Organization management API endpoints.

Mounted under ``/api/v1/organization``.  All endpoints require
authentication and are scoped to the caller's organization.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import (
    get_current_organization,
    require_permission,
)
from app.modules.auth.types import AuthenticatedPrincipal
from app.modules.organization.schemas import (
    AdminResponse,
    CreateAdmin,
    OrganizationProfile,
    UpdateOrganization,
)
from app.modules.organization import services as org_svc

router = APIRouter(
    prefix="/api/v1/organization",
    tags=["Organization"],
)


# ═════════════════════════════════════════════════════════════════════
# Organization profile
# ═════════════════════════════════════════════════════════════════════


@router.get(
    "",
    response_model=OrganizationProfile,
    summary="Get organization profile",
)
async def get_organization_profile(
    principal: AuthenticatedPrincipal = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the authenticated organization's profile."""
    try:
        return await org_svc.get_organization_profile(db, principal.organization_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )


@router.patch(
    "",
    response_model=OrganizationProfile,
    summary="Update organization profile",
    dependencies=[Depends(require_permission("organization:manage"))],
)
async def update_organization(
    body: UpdateOrganization,
    principal: AuthenticatedPrincipal = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Update the authenticated organization's profile fields."""
    try:
        return await org_svc.update_organization_profile(
            db,
            principal.organization_id,
            organization_name=body.organization_name,
            organization_email=body.organization_email,
            organization_phone=body.organization_phone,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete organization",
    dependencies=[Depends(require_permission("organization:manage"))],
)
async def delete_organization(
    principal: AuthenticatedPrincipal = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Delete the authenticated organization and cascade to admins."""
    try:
        await org_svc.delete_organization(db, principal.organization_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found.",
        )


# ═════════════════════════════════════════════════════════════════════
# Organization admins
# ═════════════════════════════════════════════════════════════════════


@router.post(
    "/admins",
    response_model=AdminResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an admin",
    dependencies=[Depends(require_permission("users:manage"))],
)
async def create_admin(
    body: CreateAdmin,
    principal: AuthenticatedPrincipal = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Create an admin within the authenticated organization."""
    try:
        return await org_svc.create_admin_for_organization(
            db,
            principal.organization_id,
            name=body.admin_name,
            email=body.admin_email,
            phone=body.admin_phone,
            employee_id=body.admin_employee_id,
            password=body.password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )


@router.get(
    "/admins",
    response_model=list[AdminResponse],
    summary="List admins",
    dependencies=[Depends(require_permission("users:manage"))],
)
async def list_admins(
    principal: AuthenticatedPrincipal = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """List all admins belonging to the authenticated organization."""
    return await org_svc.list_organization_admins(db, principal.organization_id)


@router.get(
    "/admins/{admin_id}",
    response_model=AdminResponse,
    summary="Get an admin",
    dependencies=[Depends(require_permission("users:manage"))],
)
async def get_admin(
    admin_id: UUID,
    principal: AuthenticatedPrincipal = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Get a single admin, scoped to the authenticated organization."""
    try:
        return await org_svc.get_organization_admin(
            db, principal.organization_id, admin_id,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found.",
        )


@router.delete(
    "/admins/{admin_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an admin",
    dependencies=[Depends(require_permission("users:manage"))],
)
async def delete_admin(
    admin_id: UUID,
    principal: AuthenticatedPrincipal = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
):
    """Delete an admin, scoped to the authenticated organization."""
    try:
        await org_svc.delete_organization_admin(
            db, principal.organization_id, admin_id,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found.",
        )