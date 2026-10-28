from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.modules.organization.models import Organization


class LogRecord(Base):
    """
    Primary log storage model.
    Records every ingested log entry along with queue ticket number,
    classification prediction, and processing status.
    """

    __tablename__ = "log_records"
    __table_args__ = (
        Index("ix_log_records_created_at", "created_at"),
        Index("ix_log_records_prediction", "prediction"),
        Index("ix_log_records_queue_number", "queue_number", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Queue tracking sequence number
    queue_number: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    # Core log features
    content: Mapped[str] = mapped_column(Text, nullable=False)
    component: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    hour: Mapped[int] = mapped_column(Integer, nullable=False)
    minute: Mapped[int] = mapped_column(Integer, nullable=False)
    second: Mapped[int] = mapped_column(Integer, nullable=False)
    time_gap: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    pid_freq: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    raw_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Model evaluation & triage metadata
    predicted_by: Mapped[str] = mapped_column(String(50), nullable=False)  # 'ML', 'LLM', 'ML+LLM', 'FALLBACK'
    prediction: Mapped[str] = mapped_column(String(50), nullable=False)    # 'INFO', 'WARN', 'ERROR', 'UNKNOWN'
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="COMPLETED", nullable=False)  # 'QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED'
    has_explainability: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Audit timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationship to dedicated explainability table (1-to-1)
    explainability: Mapped[Optional["LogExplainability"]] = relationship(
        "LogExplainability",
        back_populates="log_record",
        uselist=False,
        cascade="all, delete-orphan",
    )
    organization: Mapped["Organization"] = relationship()


class LogExplainability(Base):
    """
    Dedicated database table containing ONLY logs requiring deep explainability.
    Specifically captures high-severity warnings, anomalous events, and logs
    unpredicted by the primary ML model.
    """

    __tablename__ = "log_explainability"
    __table_args__ = (
        Index("ix_log_explainability_threat", "threat_level"),
        Index("ix_log_explainability_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Foreign key link to the originating log record
    log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("log_records.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    # Queue reference for operational traceability
    queue_number: Mapped[int] = mapped_column(
        BigInteger,
        index=True,
        nullable=False,
    )

    # Threat classification and deep explanations
    threat_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # 'HIGH', 'CRITICAL', 'MEDIUM', 'UNKNOWN'

    detection_summary: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attack_type: Mapped[str] = mapped_column(String(255), nullable=False, default="Unknown")
    mitre_attack_ids: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    llm_model: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    log_record: Mapped["LogRecord"] = relationship(
        "LogRecord",
        back_populates="explainability",
    )
