from __future__ import annotations

import uuid
from typing import Optional, Sequence
from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.log.models import LogRecord, LogExplainability


class LogRepository:
    """Async database repository handling persistence and querying for logs and explainability."""

    async def get_max_queue_number(self, session: AsyncSession) -> int:
        """Retrieves the highest assigned queue number from persistent storage."""
        stmt = select(func.max(LogRecord.queue_number))
        result = await session.execute(stmt)
        max_num = result.scalar()
        return int(max_num) if max_num is not None else 0

    async def get_summary(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
    ) -> dict[str, int]:
        """Return aggregate prediction totals for one organization."""
        stmt = select(
            func.count(LogRecord.id),
            func.sum(case((LogRecord.prediction == "INFO", 1), else_=0)),
            func.sum(
                case(
                    (LogRecord.prediction.in_(("WARN", "ERROR")), 1),
                    else_=0,
                )
            ),
            func.sum(
                case(
                    (LogRecord.prediction.not_in(("INFO", "WARN", "ERROR")), 1),
                    else_=0,
                )
            ),
            func.sum(case((LogRecord.status == "FAILED", 1), else_=0)),
        ).where(LogRecord.organization_id == organization_id)
        total, safe, warn, other, failed = (await session.execute(stmt)).one()
        return {
            "total_analyzed": int(total or 0),
            "safe": int(safe or 0),
            "warn": int(warn or 0),
            "other": int(other or 0),
            "pending": 0,
            "processing": 0,
            "failed": int(failed or 0),
        }

    async def save_log_record(
        self,
        session: AsyncSession,
        *,
        organization_id: uuid.UUID,
        queue_number: int,
        content: str,
        component: str,
        hour: int,
        minute: int,
        second: int,
        time_gap: float,
        pid_freq: int,
        raw_log: Optional[str],
        predicted_by: str,
        prediction: str,
        confidence: Optional[float],
        status: str,
        has_explainability: bool,
    ) -> LogRecord:
        """Creates and persists a new LogRecord."""
        record = LogRecord(
            queue_number=queue_number,
            organization_id=organization_id,
            content=content,
            component=component,
            hour=hour,
            minute=minute,
            second=second,
            time_gap=time_gap,
            pid_freq=pid_freq,
            raw_log=raw_log,
            predicted_by=predicted_by,
            prediction=prediction,
            confidence=confidence,
            status=status,
            has_explainability=has_explainability,
        )
        session.add(record)
        await session.flush()
        return record

    async def save_explainability(
        self,
        session: AsyncSession,
        *,
        organization_id: uuid.UUID,
        log_id: uuid.UUID,
        queue_number: int,
        threat_level: str,
        detection_summary: str,
        explanation: str,
        recommended_action: Optional[str],
        attack_type: str,
        mitre_attack_ids: list[str],
        llm_model: str,
        confidence_score: Optional[float],
    ) -> LogExplainability:
        """Creates and persists an explainability entry in the dedicated explainability table."""
        explain_entry = LogExplainability(
            log_id=log_id,
            organization_id=organization_id,
            queue_number=queue_number,
            threat_level=threat_level,
            detection_summary=detection_summary,
            explanation=explanation,
            recommended_action=recommended_action,
            attack_type=attack_type,
            mitre_attack_ids=mitre_attack_ids,
            llm_model=llm_model,
            confidence_score=confidence_score,
        )
        session.add(explain_entry)
        await session.flush()
        return explain_entry

    async def get_log_by_id(
        self,
        session: AsyncSession,
        log_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Optional[LogRecord]:
        """Fetches a single log record by ID with eager loading of explainability if present."""
        stmt = (
            select(LogRecord)
            .options(selectinload(LogRecord.explainability))
            .where(
                LogRecord.id == log_id,
                LogRecord.organization_id == organization_id,
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_log_by_queue_number(
        self,
        session: AsyncSession,
        queue_number: int,
        organization_id: uuid.UUID,
    ) -> Optional[LogRecord]:
        """Fetches a log record by its assigned queue number."""
        stmt = (
            select(LogRecord)
            .options(selectinload(LogRecord.explainability))
            .where(
                LogRecord.queue_number == queue_number,
                LogRecord.organization_id == organization_id,
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_logs(
        self,
        session: AsyncSession,
        *,
        organization_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
        prediction: Optional[str] = None,
        component: Optional[str] = None,
        has_explainability: Optional[bool] = None,
    ) -> Sequence[LogRecord]:
        """Queries log records with optional filtering and pagination."""
        stmt = (
            select(LogRecord)
            .options(selectinload(LogRecord.explainability))
            .order_by(desc(LogRecord.created_at))
        ).where(LogRecord.organization_id == organization_id)
        if prediction:
            stmt = stmt.where(LogRecord.prediction == prediction.upper())
        if component:
            stmt = stmt.where(LogRecord.component == component)
        if has_explainability is not None:
            stmt = stmt.where(LogRecord.has_explainability == has_explainability)

        stmt = stmt.offset(skip).limit(limit)
        result = await session.execute(stmt)
        return result.scalars().all()

    async def list_explainable_logs(
        self,
        session: AsyncSession,
        *,
        organization_id: uuid.UUID,
        skip: int = 0,
        limit: int = 50,
        threat_level: Optional[str] = None,
    ) -> Sequence[LogExplainability]:
        """
        Directly queries the dedicated explainability table.
        Returns records that required deep explainability (HIGH / UNKNOWN / Anomaly).
        """
        stmt = (
            select(LogExplainability)
            .order_by(desc(LogExplainability.created_at))
        ).where(LogExplainability.organization_id == organization_id)
        if threat_level:
            stmt = stmt.where(LogExplainability.threat_level == threat_level.upper())

        stmt = stmt.offset(skip).limit(limit)
        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_explainability_by_log_id(
        self,
        session: AsyncSession,
        log_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Optional[LogExplainability]:
        """Retrieves explainability record corresponding to a specific log ID."""
        stmt = select(LogExplainability).where(
            LogExplainability.log_id == log_id,
            LogExplainability.organization_id == organization_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


log_repository = LogRepository()
