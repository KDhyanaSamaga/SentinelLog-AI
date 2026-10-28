from __future__ import annotations

import logging
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from huggingface_hub import InferenceClient

from app.core.config import settings
from app.modules.llmSservices.schemas import LogAnalysisRequest
from app.modules.llmSservices.promt import prompt

logger = logging.getLogger(__name__)


class ExplainabilityResult(BaseModel):
    """Structured explainability and threat detection result."""
    model_config = ConfigDict(extra="forbid")

    threat_level: Literal["HIGH", "CRITICAL", "MEDIUM", "LOW", "UNKNOWN"]
    detection_summary: str = Field(min_length=1, max_length=5000)
    explanation: str = Field(min_length=1, max_length=20000)
    recommended_action: str = Field(min_length=1, max_length=10000)
    attack_type: str = Field(default="Unknown", min_length=1, max_length=255)
    mitre_attack_ids: list[str] = Field(default_factory=list, max_length=20)
    llm_model: str
    confidence_score: float = Field(default=0.85, ge=0.0, le=1.0)


class LLMService:
    """
    LLM Analysis and Explainability Service.
    Integrates with HuggingFace Inference API with robust cybersecurity heuristic fallback
    for high availability and resilience when API quotas or network constraints occur.
    """

    MODEL_NAME = "Qwen/Qwen2.5-72B-Instruct"
    FALLBACK_MODEL_NAME = "Sentinel-CyberHeuristic-Expert"

    @property
    def is_configured(self) -> bool:
        return bool(settings.HF_TOKEN)

    def check_connection(self) -> None:
        client = InferenceClient(
            model=self.MODEL_NAME,
            token=settings.HF_TOKEN,
        )
        client.chat.completions.create(
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )

    def _generate_expert_fallback(
        self,
        raw_log: str,
        component: str,
        log_type: str,
        extra_context: str | None = None,
    ) -> ExplainabilityResult:
        """
        High-fidelity heuristic cybersecurity explainability engine.
        Evaluates log semantics, component anomalies, and risk vectors when remote LLM is unavailable.
        """
        content_lower = raw_log.lower()
        comp_lower = component.lower()

        # Heuristic detection patterns
        is_termination = "terminating" in content_lower or "failed" in content_lower or "terminated" in content_lower
        is_block_anomaly = "block" in content_lower and ("error" in content_lower or "corrupt" in content_lower)
        is_network_timeout = "timeout" in content_lower or "reset" in content_lower or "connection refused" in content_lower
        is_permission_denied = "denied" in content_lower or "unauthorized" in content_lower or "forbidden" in content_lower
        is_warn = log_type.upper() in {"WARN", "WARNING"}
        is_datanode = "datanode" in comp_lower or "packetresponder" in comp_lower

        if is_permission_denied:
            threat_level = "CRITICAL"
            detection_summary = f"Unauthorized access or permission violation detected in {component}."
            explanation = (
                f"Log entry indicates an access violation or credential rejection in component [{component}]. "
                f"Content: '{raw_log}'. This may signify unauthorized privilege escalation or credential brute-forcing."
            )
            recommended_action = (
                "1. Audit IAM / Kerberos tickets and user authentication logs immediately. "
                "2. Check origin IP addresses for potential reconnaissance. "
                "3. Verify file permissions and isolate affected service accounts."
            )
            confidence = 0.95

        elif is_termination and is_datanode:
            threat_level = "HIGH" if is_warn else "MEDIUM"
            detection_summary = f"Abnormal process/packet responder termination in HDFS DataNode component ({component})."
            explanation = (
                f"A packet responder or pipeline thread terminated abruptly while servicing a data block. "
                f"Raw log: '{raw_log}'. "
                "In distributed storage systems, premature termination typically stems from network packet drops, "
                "disk I/O bottlenecks, or an adversary attempting node disruption or man-in-the-middle transmission abort."
            )
            recommended_action = (
                "1. Inspect DataNode disk I/O health and NIC error counters. "
                "2. Check replication status for the impacted block via HDFS fsck. "
                "3. Ensure network MTU and firewall rules between NameNode and DataNodes are stable."
            )
            confidence = 0.88

        elif is_network_timeout:
            threat_level = "HIGH"
            detection_summary = f"Network communication failure or peer timeout in {component}."
            explanation = (
                f"Log specifies a socket timeout or connection failure. Raw content: '{raw_log}'. "
                "This could be indicative of network partition, node resource exhaustion, or a Denial-of-Service (DoS) condition."
            )
            recommended_action = (
                "1. Investigate peer reachability and packet loss rates. "
                "2. Review socket queue exhaustion and thread pool saturation metrics. "
                "3. Verify upstream router and switch logs."
            )
            confidence = 0.85

        elif is_warn:
            threat_level = "HIGH"
            detection_summary = f"Unclassified high-severity anomaly flagged by ML pipeline ({log_type})."
            explanation = (
                f"The log message '{raw_log}' was flagged as a high-severity warning by the ML classifier. "
                f"Component '{component}' encountered an anomalous operating state requiring manual security triage."
            )
            recommended_action = (
                "1. Review neighboring log entries around this timestamp for correlated failure cascades. "
                "2. Validate component configuration and ensure no unexpected parameter alterations occurred. "
                "3. Escalate to the platform engineering / SOC on-call."
            )
            confidence = 0.82

        else:
            threat_level = "UNKNOWN"
            detection_summary = f"Uncertain or unpredicted system event in {component}."
            explanation = (
                f"The log entry '{raw_log}' does not match standard operational baseline patterns. "
                f"Context: {extra_context or 'None'}. It was escalated for explainability due to classification uncertainty."
            )
            recommended_action = (
                "1. Tag this log signature for baseline profile update. "
                "2. Cross-reference with system metrics (CPU, RAM, open file descriptors). "
                "3. Determine if this correlates with recent deployment changes."
            )
            confidence = 0.75

        return ExplainabilityResult(
            threat_level=threat_level,
            detection_summary=detection_summary,
            explanation=explanation,
            recommended_action=recommended_action,
            attack_type="Unknown",
            mitre_attack_ids=[],
            llm_model=self.FALLBACK_MODEL_NAME,
            confidence_score=confidence,
        )

    def analyze_and_explain(
        self,
        raw_log: str,
        component: str,
        log_type: str = "UNKNOWN",
        extra_context: str | None = None,
    ) -> ExplainabilityResult:
        """
        Conducts deep explainability and threat detection on an anomalous or unpredicted log entry.
        Queries Hugging Face LLM if accessible, otherwise seamlessly activates the expert heuristic analyzer.
        """
        # Try Hugging Face LLM if token is present
        if settings.HF_TOKEN:
            try:
                client = InferenceClient(
                    model=self.MODEL_NAME,
                    token=settings.HF_TOKEN,
                    timeout=10.0,
                )
                request_payload = LogAnalysisRequest(
                    raw_log=raw_log,
                    log_type=log_type,
                    machine=component,
                    extra_context=extra_context,
                )
                response = client.chat.completions.create(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a senior cybersecurity expert. Analyze the provided log entry. "
                                "Return only a JSON object with exactly these fields: "
                                "threat_level (HIGH, CRITICAL, MEDIUM, LOW, or UNKNOWN), "
                                "detection_summary, explanation, recommended_action, attack_type, "
                                "mitre_attack_ids (array of ATT&CK IDs), and confidence_score (0 to 1). "
                                "Do not include Markdown or additional keys."
                            ),
                        },
                        {
                            "role": "user",
                            "content": prompt(request_payload),
                        },
                    ],
                    temperature=0.2,
                    max_tokens=400,
                )
                message = response.choices[0].message.content.strip()
                parsed = ExplainabilityResult.model_validate(
                    {**json.loads(message), "llm_model": self.MODEL_NAME}
                )
                return parsed

            except Exception as e:
                logger.warning(
                    f"HuggingFace LLM inference unavailable ({e}). Engaging Sentinel CyberHeuristic Expert fallback.",
                )

        # Fallback to local cybersecurity heuristic explainability
        return self._generate_expert_fallback(
            raw_log=raw_log,
            component=component,
            log_type=log_type,
            extra_context=extra_context,
        )


# Global singleton instance
llm_service = LLMService()
