from __future__ import annotations

import re
from pydantic import BaseModel, Field, field_validator


class ModelInput(BaseModel):
    """
    Validated input schema for log classification via the ML model.
    Applies secure coding practices (length limits, type constraints, and sanitization).
    """
    content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Log message text content",
        examples=["PacketResponder 1 for block blk_38865049 terminating"],
    )
    component: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Logging component or subsystem",
        examples=["dfs.DataNode$PacketResponder"],
    )
    hour: int = Field(
        ...,
        ge=0,
        le=23,
        description="Hour of day (0-23)",
        examples=[20],
    )
    minute: int = Field(
        ...,
        ge=0,
        le=59,
        description="Minute of hour (0-59)",
        examples=[36],
    )
    second: int = Field(
        ...,
        ge=0,
        le=59,
        description="Second of minute (0-59)",
        examples=[15],
    )
    time_gap: float = Field(
        default=0.0,
        ge=0.0,
        le=86400.0,
        description="Time gap in seconds since previous entry",
        examples=[0.0],
    )
    pid_freq: int = Field(
        default=1,
        ge=0,
        le=1000000,
        description="Process ID frequency statistic",
        examples=[1],
    )

    @field_validator("content", "component")
    @classmethod
    def sanitize_strings(cls, v: str) -> str:
        """Strip null bytes and non-printable control characters to prevent log injection."""
        v = v.replace("\x00", "")
        # Remove dangerous control chars except standard whitespace
        v = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f]", "", v)
        return v.strip()


class ModelPredictionOutput(BaseModel):
    """Prediction result from the ML classifier."""
    is_predicted: bool
    prediction: str
    confidence: float | None = None
    decision_score: float | None = None
    needs_llm_escalation: bool
    details: str | None = None
