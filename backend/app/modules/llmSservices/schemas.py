from typing import Literal

from pydantic import BaseModel, Field

class LogAnalysisRequest(BaseModel):
    raw_log: str = Field(min_length=1, max_length=10000)
    log_type: str = Field(min_length=1, max_length=50)
    machine: str = Field(min_length=1, max_length=255)
    extra_context: str | None = Field(default=None, max_length=5000)

class LLMOutput(BaseModel):
    model_config = {"extra": "forbid"}

    threat_level: Literal["HIGH", "CRITICAL", "MEDIUM", "LOW", "UNKNOWN"]
    detection_summary: str = Field(min_length=1, max_length=5000)
    explanation: str = Field(min_length=1, max_length=20000)
    recommended_action: str = Field(min_length=1, max_length=10000)
    attack_type: str = Field(min_length=1, max_length=255)
    mitre_attack_ids: list[str] = Field(default_factory=list, max_length=20)
    confidence_score: float = Field(ge=0.0, le=1.0)
    llm_model: str = Field(min_length=1, max_length=255)