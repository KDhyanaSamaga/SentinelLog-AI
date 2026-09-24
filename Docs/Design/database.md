# This file contain the Database Columns and their types and additional informations

---

# TABLE-3: Log

## **This table stores the incomming log and are processed and classified**

# Table-4 :

To track short-lived authentication tokens for both **Organizations** (Super Admins) and **Admins** (Employees), you should design a token table that uses **polymorphic references** or **nullable foreign keys**.

Since an authentication token is issued to _either_ an Organization _or_ an Admin during a login session, using nullable foreign keys with a check constraint ensures clean data integrity.

---

### **1. Recommended Model: `Token` / `UserToken**`

```python
import uuid
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, UUID, ForeignKey, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

class Token(Base):
    __tablename__ = "token"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    token: Mapped[str] = mapped_column(
        String(512),
        unique=True,
        nullable=False,
        index=True,
    )

    token_type: Mapped[str] = mapped_column(
        String(20),
        default="bearer",
        nullable=False,
    )  # e.g., "access", "refresh", "reset_password"

    user_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )  # "organization" or "admin"

    # Foreign Key for Organization (Super Admin) login
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Foreign Key for Admin (Employee) login
    admin_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("admin.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    expires_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Constraint to ensure token belongs to EXACTLY ONE entity
    __table_args__ = (
        CheckConstraint(
            "(organization_id IS NOT NULL AND admin_id IS NULL) OR "
            "(organization_id IS NULL AND admin_id IS NOT NULL)",
            name="check_token_owner",
        ),
    )

    # Relationships
    organization: Mapped[Optional["Organization"]] = relationship("Organization")
    admin: Mapped[Optional["Admin"]] = relationship("Admin")

```

**This table contain the toekn assigned by the server**
