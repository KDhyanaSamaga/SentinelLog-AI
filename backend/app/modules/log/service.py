from __future__ import annotations

import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.modules.aiModel.schemas import ModelInput
from app.modules.aiModel.service import ml_service
from app.modules.llmSservices.service import llm_service
from app.modules.log.models import LogRecord, LogExplainability
from app.modules.log.repository import log_repository
from app.modules.log.schemas import (
    LogIngestRequest,
    LogIngestResponse,
    LogExplainabilityResponse,
)

logger = logging.getLogger(__name__)


class LogTriageService:
    """
    Central orchestration service for the log triage pipeline:
    1. Validates input and extracts features.
    2. Runs inference through the trained ML classifier.
    3. If unpredicted or high-severity/unknown, escalates to the LLM service for deep explainability.
    4. Persists the record in the main logs table.
    5. Persists explainability in the dedicated explainability table (only for high/unknown).
    """

    async def process_log_entry(
        self,
        request: LogIngestRequest,
        queue_number: int,
        organization_id: uuid.UUID,
        session: AsyncSession | None = None,
    ) -> LogIngestResponse:
        """
        Processes a single log entry through ML prediction, conditional LLM explainability,
        and database storage.
        """
        # 1. Transform to ModelInput
        model_input = ModelInput(
            content=request.content,
            component=request.component,
            hour=request.hour,
            minute=request.minute,
            second=request.second,
            time_gap=request.time_gap,
            pid_freq=request.pid_freq,
        )

        # 2. ML Model Inference
        ml_result = ml_service.predict_log(model_input)
        logger.info(
            f"[Queue #{queue_number}] ML Result: predicted={ml_result.is_predicted}, "
            f"class={ml_result.prediction}, needs_llm={ml_result.needs_llm_escalation}",
        )

        # High-severity and anomaly signals
        text_to_check = f"{request.content} {request.raw_log or ''}".upper()
        high_severity_indicators = (
            "ERROR", "EXCEPTION", "CORRUPTED", "FATAL", "CRITICAL",
            "UNAUTHORIZED", "PERMISSION DENIED", "CHECKSUM", "ATTACK", "FAIL"
        )
        has_high_anomaly = any(ind in text_to_check for ind in high_severity_indicators)

        # 3. Decision Logic: Routine Normal vs High / Unknown / Unpredicted
        is_high_or_unknown = (
            ml_result.prediction in {"WARN", "ERROR", "UNKNOWN"}
            or has_high_anomaly
        )
        needs_explainability = (
            ml_result.needs_llm_escalation
            or (not ml_result.is_predicted)
            or is_high_or_unknown
        )

        explainability_data = None
        predicted_by = "ML"
        final_prediction = "WARN" if (has_high_anomaly and ml_result.prediction == "INFO") else ml_result.prediction

        if needs_explainability:
            # Escalated to LLM for threat detection & deep explainability
            effective_log_text = request.raw_log or request.content
            effective_level = final_prediction if ml_result.is_predicted else "UNKNOWN"
            explainability_data = llm_service.analyze_and_explain(
                raw_log=effective_log_text,
                component=request.component,
                log_type=effective_level,
                extra_context=(
                    f"ML classified as {ml_result.prediction} with decision score {ml_result.decision_score}."
                    if ml_result.is_predicted
                    else "ML failed to classify log or marked confidence as uncertain."
                ),
            )
            predicted_by = "ML+LLM" if ml_result.is_predicted else "LLM"
            logger.info(
                f"[Queue #{queue_number}] LLM explainability complete: Threat={explainability_data.threat_level}, "
                f"Model={explainability_data.llm_model}",
            )

        # 4. Persistence into Database
        async def _persist(s: AsyncSession) -> LogIngestResponse:
            # Create primary log record
            record = await log_repository.save_log_record(
                s,
                queue_number=queue_number,
                organization_id=organization_id,
                content=request.content,
                component=request.component,
                hour=request.hour,
                minute=request.minute,
                second=request.second,
                time_gap=request.time_gap,
                pid_freq=request.pid_freq,
                raw_log=request.raw_log,
                predicted_by=predicted_by,
                prediction=final_prediction,
                confidence=ml_result.confidence,
                status="COMPLETED",
                has_explainability=needs_explainability,
            )

            explain_resp = None
            if needs_explainability and explainability_data is not None:
                # Save into the dedicated explainability table (only for explainable entries)
                exp_entry = await log_repository.save_explainability(
                    s,
                    log_id=record.id,
                    organization_id=organization_id,
                    queue_number=queue_number,
                    threat_level=explainability_data.threat_level,
                    detection_summary=explainability_data.detection_summary,
                    explanation=explainability_data.explanation,
                    recommended_action=explainability_data.recommended_action,
                    attack_type=explainability_data.attack_type,
                    mitre_attack_ids=explainability_data.mitre_attack_ids,
                    llm_model=explainability_data.llm_model,
                    confidence_score=explainability_data.confidence_score,
                )
                explain_resp = LogExplainabilityResponse(
                    id=exp_entry.id,
                    log_id=record.id,
                    queue_number=queue_number,
                    threat_level=exp_entry.threat_level,
                    detection_summary=exp_entry.detection_summary,
                    explanation=exp_entry.explanation,
                    recommended_action=exp_entry.recommended_action,
                    attack_type=exp_entry.attack_type,
                    mitre_attack_ids=exp_entry.mitre_attack_ids,
                    llm_model=exp_entry.llm_model,
                    confidence_score=exp_entry.confidence_score,
                    created_at=exp_entry.created_at,
                )

            await s.commit()

            return LogIngestResponse(
                queue_number=queue_number,
                status="COMPLETED",
                log_id=record.id,
                predicted_by=predicted_by,
                prediction=final_prediction,
                confidence=ml_result.confidence,
                has_explainability=needs_explainability,
                explainability=explain_resp,
                message=(
                    "Log processed with ML and escalated for deep explainability in dedicated table."
                    if needs_explainability
                    else "Log successfully classified as routine by ML pipeline."
                ),
            )

        if session is not None:
            return await _persist(session)
        else:
            async with AsyncSessionLocal() as fresh_session:
                return await _persist(fresh_session)


log_service = LogTriageService()
