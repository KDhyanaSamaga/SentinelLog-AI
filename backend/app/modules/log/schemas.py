from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class LogIngestRequest(BaseModel):
    """
    Validated ingestion schema for single log entry.
    Implements secure coding practices: length restrictions, character sanitization,
    boundary validation for timestamps and frequencies.
    """
    content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="The log message or payload",
        examples=["PacketResponder 1 for block blk_38865049 terminating"],
    )
    component: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="System component or logger namespace",
        examples=["dfs.DataNode$PacketResponder"],
    )
    hour: int = Field(
        ...,
        ge=0,
        le=23,
        description="Hour of occurrence (0-23)",
        examples=[20],
    )
    minute: int = Field(
        ...,
        ge=0,
        le=59,
        description="Minute of occurrence (0-59)",
        examples=[36],
    )
    second: int = Field(
        ...,
        ge=0,
        le=59,
        description="Second of occurrence (0-59)",
        examples=[15],
    )
    time_gap: float = Field(
        default=0.0,
        ge=0.0,
        le=86400.0,
        description="Time difference from previous log in seconds",
        examples=[0.0],
    )
    pid_freq: int = Field(
        default=1,
        ge=0,
        le=1000000,
        description="Process ID occurrence frequency",
        examples=[1],
    )
    raw_log: Optional[str] = Field(
        default=None,
        max_length=10000,
        description="Optional full raw log line for auditing",
    )

    @field_validator("content", "component", "raw_log")
    @classmethod
    def sanitize_input(cls, v: Optional[str]) -> Optional[str]:
        """Strip null bytes and non-printable control characters to prevent log injection / CRLF."""
        if v is None:
            return None
        v = v.replace("\x00", "")
        # Remove non-printable control characters except standard whitespace
        v = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f]", "", v)
        return v.strip()


class BatchLogIngestRequest(BaseModel):
    """Batch ingestion request schema with bounded capacity to prevent resource exhaustion."""
    logs: list[LogIngestRequest] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Array of validated logs (maximum 100 entries per batch)",
    )


class LogExplainabilityResponse(BaseModel):
    """Schema for explainability details stored in the dedicated explainability table."""
    id: uuid.UUID
    log_id: uuid.UUID
    queue_number: int
    threat_level: str
    detection_summary: str
    explanation: str
    recommended_action: Optional[str] = None
    attack_type: str = "Unknown"
    mitre_attack_ids: list[str] = Field(default_factory=list)
    llm_model: str
    confidence_score: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class LogRecordResponse(BaseModel):
    """Comprehensive representation of an ingested and processed log record."""
    id: uuid.UUID
    queue_number: int
    content: str
    component: str
    hour: int
    minute: int
    second: int
    time_gap: float
    pid_freq: int
    raw_log: Optional[str] = None
    predicted_by: str
    prediction: str
    confidence: Optional[float] = None
    status: str
    has_explainability: bool
    created_at: datetime
    updated_at: datetime
    explainability: Optional[LogExplainabilityResponse] = None

    class Config:
        from_attributes = True


class LogIngestResponse(BaseModel):
    """Response returned upon submitting a log entry into the pipeline."""
    queue_number: int
    status: str
    log_id: Optional[uuid.UUID] = None
    predicted_by: Optional[str] = None
    prediction: Optional[str] = None
    confidence: Optional[float] = None
    has_explainability: bool = False
    explainability: Optional[LogExplainabilityResponse] = None
    message: str = "Log processed and persisted successfully."


class QueueTicketResponse(BaseModel):
    """Asynchronous ticket returned when a log is enqueued for background processing."""
    queue_number: int
    status: str
    enqueued_at: datetime
    estimated_wait_seconds: float
    status_url: str


class QueueItemStatusResponse(BaseModel):
    """Status query response for a specific queue item number."""
    queue_number: int
    status: str
    enqueued_at: datetime
    completed_at: Optional[datetime] = None
    log_id: Optional[uuid.UUID] = None
    error_message: Optional[str] = None
    result: Optional[LogIngestResponse] = None


class QueueMetricsResponse(BaseModel):
    """Real-time operational health and queue processing metrics."""
    total_enqueued: int
    currently_processing: int
    total_completed: int
    total_failed: int
    current_queue_depth: int
    worker_active: bool


class LogSummaryResponse(BaseModel):
    """Tenant-scoped dashboard totals for processed and queued logs."""
    total_analyzed: int
    safe: int
    warn: int
    other: int
    pending: int
    processing: int
    failed: int
