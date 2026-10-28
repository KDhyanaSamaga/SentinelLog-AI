from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional

from app.core.database import AsyncSessionLocal
from app.modules.log.repository import log_repository
from app.modules.log.schemas import (
    LogIngestRequest,
    LogIngestResponse,
    QueueItemStatusResponse,
    QueueMetricsResponse,
    QueueTicketResponse,
)
from app.modules.log.service import log_service

logger = logging.getLogger(__name__)


@dataclass
class QueueItem:
    """Internal representation of a task in the log ingestion queue."""
    queue_number: int
    request: LogIngestRequest
    organization_id: uuid.UUID
    enqueued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "QUEUED"  # 'QUEUED', 'PROCESSING', 'COMPLETED', 'FAILED'
    completed_at: Optional[datetime] = None
    event: asyncio.Event = field(default_factory=asyncio.Event)
    result: Optional[LogIngestResponse] = None
    error_message: Optional[str] = None


class LogQueueManager:
    """
    Asynchronous FIFO Queue Manager.
    - Assigns an auto-incrementing queue ticket number to every log request.
    - Manages background worker processing.
    - Allows synchronous clients to await processing and database persistence.
    - Allows asynchronous clients to poll by queue number.
    """

    def __init__(self, max_concurrent_workers: int = 2) -> None:
        self._queue: asyncio.Queue[QueueItem] = asyncio.Queue()
        self._items: Dict[int, QueueItem] = {}
        self._next_queue_number: int = 1
        self._number_lock = asyncio.Lock()
        self._initialized: bool = False
        self._workers: list[asyncio.Task] = []
        self._max_concurrent_workers = max_concurrent_workers
        self._is_running: bool = False

        # Metrics counters
        self._total_enqueued: int = 0
        self._currently_processing: int = 0
        self._total_completed: int = 0
        self._total_failed: int = 0

    async def initialize(self) -> None:
        """Initializes the queue counter from the maximum stored queue number in the database."""
        if self._initialized:
            return
        async with self._number_lock:
            if not self._initialized:
                try:
                    async with AsyncSessionLocal() as session:
                        max_db_num = await log_repository.get_max_queue_number(session)
                        self._next_queue_number = max_db_num + 1
                        logger.info(f"Initialized LogQueueManager. Next queue number: {self._next_queue_number}")
                except Exception as e:
                    logger.warning(f"Could not read max queue number from DB ({e}). Defaulting to 1.")
                    self._next_queue_number = 1
                self._initialized = True

    def start(self) -> None:
        """Starts background worker tasks."""
        if self._is_running:
            return
        self._is_running = True
        for i in range(self._max_concurrent_workers):
            task = asyncio.create_task(self._worker_loop(worker_id=i + 1))
            self._workers.append(task)
        logger.info(f"Started {self._max_concurrent_workers} log queue worker(s).")

    async def stop(self) -> None:
        """Gracefully terminates background worker tasks."""
        self._is_running = False
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("Log queue workers stopped.")

    async def _assign_queue_number(self) -> int:
        """Generates an atomic, unique sequential queue ticket number."""
        await self.initialize()
        async with self._number_lock:
            q_num = self._next_queue_number
            self._next_queue_number += 1
            self._total_enqueued += 1
            return q_num

    async def enqueue_and_wait(
        self,
        request: LogIngestRequest,
        organization_id: uuid.UUID,
        timeout: float = 30.0,
    ) -> LogIngestResponse:
        """
        Enqueues a log request and waits until it has been predicted and stored in the database.
        """
        queue_number = await self._assign_queue_number()
        item = QueueItem(
            queue_number=queue_number,
            request=request,
            organization_id=organization_id,
        )
        self._items[queue_number] = item
        await self._queue.put(item)

        # Wait until processing completes or timeout occurs
        try:
            await asyncio.wait_for(item.event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for log queue #{queue_number} to process.")
            raise TimeoutError(f"Log processing timed out after {timeout} seconds for queue #{queue_number}.")

        if item.status == "FAILED":
            raise RuntimeError(item.error_message or "Failed to process log entry.")

        if item.result is None:
            raise RuntimeError(f"Processing finished but no result was produced for queue #{queue_number}.")

        return item.result

    async def enqueue_async(
        self,
        request: LogIngestRequest,
        organization_id: uuid.UUID,
    ) -> QueueTicketResponse:
        """
        Enqueues a log request and immediately returns a tracking ticket.
        """
        queue_number = await self._assign_queue_number()
        item = QueueItem(
            queue_number=queue_number,
            request=request,
            organization_id=organization_id,
        )
        self._items[queue_number] = item
        await self._queue.put(item)

        depth = self._queue.qsize()
        est_wait = max(0.5, depth * 0.2)

        return QueueTicketResponse(
            queue_number=queue_number,
            status="QUEUED",
            enqueued_at=item.enqueued_at,
            estimated_wait_seconds=est_wait,
            status_url=f"/logs/queue/{queue_number}",
        )

    async def get_queue_status(
        self,
        queue_number: int,
        organization_id: uuid.UUID,
    ) -> QueueItemStatusResponse:
        """
        Retrieves the status of a specific queue ticket.
        Checks in-memory queue first; if missing (e.g. after eviction or restart), queries DB.
        """
        if queue_number in self._items:
            item = self._items[queue_number]
            if item.organization_id != organization_id:
                raise KeyError(f"Queue ticket #{queue_number} not found.")
            return QueueItemStatusResponse(
                queue_number=item.queue_number,
                status=item.status,
                enqueued_at=item.enqueued_at,
                completed_at=item.completed_at,
                log_id=item.result.log_id if item.result else None,
                error_message=item.error_message,
                result=item.result,
            )

        # Fallback: check database directly
        async with AsyncSessionLocal() as session:
            record = await log_repository.get_log_by_queue_number(
                session, queue_number, organization_id
            )
            if record is not None:
                return QueueItemStatusResponse(
                    queue_number=record.queue_number,
                    status=record.status,
                    enqueued_at=record.created_at,
                    completed_at=record.updated_at,
                    log_id=record.id,
                    error_message=None,
                    result=LogIngestResponse(
                        queue_number=record.queue_number,
                        status=record.status,
                        log_id=record.id,
                        predicted_by=record.predicted_by,
                        prediction=record.prediction,
                        confidence=record.confidence,
                        has_explainability=record.has_explainability,
                        message="Log retrieved from persistent storage.",
                    ),
                )

        raise KeyError(f"Queue ticket #{queue_number} not found.")

    def get_metrics(self) -> QueueMetricsResponse:
        """Returns real-time queue metrics and processing stats."""
        return QueueMetricsResponse(
            total_enqueued=self._total_enqueued,
            currently_processing=self._currently_processing,
            total_completed=self._total_completed,
            total_failed=self._total_failed,
            current_queue_depth=self._queue.qsize(),
            worker_active=self._is_running,
        )

    async def _worker_loop(self, worker_id: int) -> None:
        """Background worker that continuously dequeues and triages logs."""
        logger.info(f"Log worker #{worker_id} started.")
        while self._is_running:
            try:
                # Wait for next item in queue
                item = await self._queue.get()
                item.status = "PROCESSING"
                self._currently_processing += 1

                try:
                    # Execute ML triage, conditional LLM explainability, and database save
                    result = await log_service.process_log_entry(
                        request=item.request,
                        queue_number=item.queue_number,
                        organization_id=item.organization_id,
                    )
                    item.result = result
                    item.status = "COMPLETED"
                    item.completed_at = datetime.now(timezone.utc)
                    self._total_completed += 1
                except Exception as e:
                    logger.error(
                        f"Worker #{worker_id} failed on queue #{item.queue_number}: {e}",
                        exc_info=True,
                    )
                    item.status = "FAILED"
                    item.error_message = str(e)
                    item.completed_at = datetime.now(timezone.utc)
                    self._total_failed += 1
                finally:
                    self._currently_processing = max(0, self._currently_processing - 1)
                    # Notify any awaiting synchronous client
                    item.event.set()
                    self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in queue worker #{worker_id}: {e}", exc_info=True)
                await asyncio.sleep(0.5)


# Global queue manager instance
queue_manager = LogQueueManager()
