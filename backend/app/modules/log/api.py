from __future__ import annotations

import logging
import uuid
from typing import Optional, Sequence
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_principal
from app.modules.auth.types import AuthenticatedPrincipal
from app.modules.log.queue import queue_manager
from app.modules.log.repository import log_repository
from app.modules.log.schemas import (
    BatchLogIngestRequest,
    LogExplainabilityResponse,
    LogIngestRequest,
    LogIngestResponse,
    LogRecordResponse,
    QueueItemStatusResponse,
    QueueMetricsResponse,
    QueueTicketResponse,
    LogSummaryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/logs", tags=["Log Pipeline & Ingestion Queue"])


@router.post(
    "/ingest",
    response_model=LogIngestResponse | QueueTicketResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest a log entry into the triage queue",
)
async def ingest_log(
    payload: LogIngestRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    wait: bool = Query(
        default=True,
        description="If True, awaits until log is predicted by ML/LLM and persisted in DB. If False, returns queue ticket immediately.",
    ),
):
    """
    Ingests a log entry into the FIFO processing queue.
    - Assigns an atomic, unique queue ticket number.
    - If `wait=True` (default): waits until ML classification, conditional LLM explainability,
      and database persistence complete, returning full results.
    - If `wait=False`: returns a 202 ticket response for asynchronous tracking.
    """
    try:
        if wait:
            result = await queue_manager.enqueue_and_wait(
                payload, principal.organization_id, timeout=30.0
            )
            return result
        else:
            ticket = await queue_manager.enqueue_async(
                payload, principal.organization_id
            )
            return ticket
    except TimeoutError as e:
        logger.warning(f"Ingest wait timed out: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to ingest log: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Log ingestion pipeline failed: {str(e)}",
        )


@router.post(
    "/batch",
    response_model=list[LogIngestResponse],
    summary="Ingest a batch of logs into the triage queue",
)
async def ingest_batch_logs(
    payload: BatchLogIngestRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """
    Batch ingestion endpoint.
    Safely enqueues multiple logs, each assigned an individual queue number,
    and returns when all entries have completed triage and storage.
    """
    results: list[LogIngestResponse] = []
    for log_req in payload.logs:
        try:
            res = await queue_manager.enqueue_and_wait(
                log_req, principal.organization_id, timeout=30.0
            )
            results.append(res)
        except Exception as e:
            logger.error(f"Batch item failed: {e}")
            results.append(
                LogIngestResponse(
                    queue_number=0,
                    status="FAILED",
                    message=f"Processing failed: {str(e)}",
                )
            )
    return results


@router.get(
    "/queue/metrics",
    response_model=QueueMetricsResponse,
    summary="Get queue processing health and operational metrics",
)
def get_queue_metrics(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """Returns real-time processing statistics for the ingestion queue."""
    return queue_manager.get_metrics()


@router.get(
    "/summary",
    response_model=LogSummaryResponse,
    summary="Get tenant-scoped dashboard log totals",
)
async def get_log_summary(
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """Combine persisted prediction totals with live queue metrics."""
    summary = await log_repository.get_summary(db, principal.organization_id)
    metrics = queue_manager.get_metrics()
    summary["pending"] = metrics.current_queue_depth
    summary["processing"] = metrics.currently_processing
    return summary


@router.get(
    "/queue/{queue_number}",
    response_model=QueueItemStatusResponse,
    summary="Check status of a specific queue ticket number",
)
async def get_queue_status(
    queue_number: int,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """
    Queries the processing status of a log by its assigned queue ticket number.
    """
    try:
        status_info = await queue_manager.get_queue_status(
            queue_number, principal.organization_id
        )
        return status_info
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Queue number #{queue_number} was not found.",
        )


@router.get(
    "/explainable",
    response_model=list[LogExplainabilityResponse],
    summary="Query dedicated table containing ONLY explainable logs",
)
async def list_explainable_logs(
    threat_level: Optional[str] = Query(None, description="Filter by threat level (HIGH, CRITICAL, MEDIUM, UNKNOWN)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """
    Directly queries the dedicated `log_explainability` database table.
    This table contains ONLY logs that were high severity, anomalies, or unpredicted by ML.
    """
    entries = await log_repository.list_explainable_logs(
        db,
        organization_id=principal.organization_id,
        skip=skip,
        limit=limit,
        threat_level=threat_level,
    )
    return entries


@router.get(
    "/explainable/{log_id}",
    response_model=LogExplainabilityResponse,
    summary="Get explainability details for a specific log record ID",
)
async def get_explainability_for_log(
    log_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """Fetches explainability record from the dedicated table for a given log ID."""
    entry = await log_repository.get_explainability_by_log_id(
        db, log_id, principal.organization_id
    )
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Explainability record for log {log_id} not found.",
        )
    return entry


@router.get(
    "/{log_id}",
    response_model=LogRecordResponse,
    summary="Get single log entry by UUID",
)
async def get_log_by_id(
    log_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """Retrieves a single log record and its associated explainability data (if present)."""
    record = await log_repository.get_log_by_id(
        db, log_id, principal.organization_id
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Log record {log_id} not found.",
        )
    return record


@router.get(
    "",
    response_model=list[LogRecordResponse],
    summary="List ingested logs with optional filtering",
)
async def list_logs(
    prediction: Optional[str] = Query(None, description="Filter by prediction (INFO, WARN, UNKNOWN)"),
    component: Optional[str] = Query(None, description="Filter by component name"),
    has_explainability: Optional[bool] = Query(None, description="Filter by presence of explainability"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
):
    """Queries all ingested logs with pagination and filters."""
    records = await log_repository.list_logs(
        db,
        organization_id=principal.organization_id,
        skip=skip,
        limit=limit,
        prediction=prediction,
        component=component,
        has_explainability=has_explainability,
    )
    return records
