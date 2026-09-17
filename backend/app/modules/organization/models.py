import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base
from admin.models import Users

class Organization(Base):
    # Name of the table
    __tablename__ = "organization"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    organization_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    organization_email: Mapped[str] = mapped_column(
        String(320),
        unique=True,
        nullable=False,
        index=True,
    )

    organization_phone: Mapped[str] = mapped_column(
        String(15),
        nullable=False,
    )

    organization_hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # subscription_plan: Mapped[str] = mapped_column(
    #     String(50),
    #     default="free",
    #     nullable=False,
    # )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    users: Mapped[list["Users"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )


