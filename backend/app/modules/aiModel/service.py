from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.modules.aiModel.schemas import ModelInput, ModelPredictionOutput

logger = logging.getLogger(__name__)

# Portable path relative to current module file
MODEL_FILE_PATH = Path(__file__).resolve().parent / "hdfs_log_classifier.joblib"


class MLModelService:
    """
    Encapsulates the trained Scikit-learn Pipeline for HDFS Log Classification.
    Provides thread-safe prediction, confidence scoring, and fallback detection.
    """

    def __init__(self, model_path: Path = MODEL_FILE_PATH) -> None:
        self.model_path = model_path
        self._model: Any = None
        self._load_model()

    def _load_model(self) -> None:
        """Loads the serialized joblib pipeline model."""
        try:
            if self.model_path.exists():
                self._model = joblib.load(self.model_path)
                logger.info(f"Loaded ML model successfully from {self.model_path}")
            else:
                logger.error(f"ML model file not found at {self.model_path}")
                self._model = None
        except Exception as e:
            logger.error(f"Failed to load ML model from {self.model_path}: {e}", exc_info=True)
            self._model = None

    @property
    def is_ready(self) -> bool:
        """Check if the ML model pipeline is loaded and ready for inference."""
        return self._model is not None

    def predict_log(self, log_input: ModelInput) -> ModelPredictionOutput:
        """
        Executes prediction using the loaded Scikit-Learn Pipeline.
        
        Evaluates decision margin and classification:
        - If classification succeeds and is 'INFO' with strong decision margin -> normal, no LLM needed.
        - If classification is 'WARN' -> flagged as high severity / anomaly -> requires LLM explainability.
        - If model fails or produces uncertain/unknown results -> marked not predicted -> requires LLM.
        """
        if not self.is_ready:
            logger.warning("ML model is not loaded. Marking log as unpredicted for LLM triage.")
            return ModelPredictionOutput(
                is_predicted=False,
                prediction="UNKNOWN",
                confidence=0.0,
                decision_score=0.0,
                needs_llm_escalation=True,
                details="ML Model not initialized or pipeline unavailable.",
            )

        try:
            # Prepare dataframe adhering exactly to the training pipeline feature schema
            df = pd.DataFrame([{
                "Content": log_input.content,
                "Component": log_input.component,
                "Hour": log_input.hour,
                "Minute": log_input.minute,
                "Second": log_input.second,
                "Time_gap": float(log_input.time_gap),
                "Pid_freq": int(log_input.pid_freq),
            }])

            # Predict class
            prediction_arr = self._model.predict(df)
            prediction = str(prediction_arr[0]).strip().upper()

            # Compute decision score and calibrated pseudo-probability
            decision_score = 0.0
            confidence = 0.5
            if hasattr(self._model, "decision_function"):
                scores = self._model.decision_function(df)
                decision_score = float(scores[0])
                # Sigmoid calibration: 1 / (1 + exp(-|score|)) -> range [0.5, 1.0]
                confidence = round(1.0 / (1.0 + math.exp(-abs(decision_score))), 4)

            # High severity (WARN) or borderline uncertain predictions require deep LLM explainability
            is_warn = prediction == "WARN"
            # If decision boundary is extremely narrow (|score| < 0.05), classification confidence is weak
            is_uncertain = abs(decision_score) < 0.05

            needs_llm = is_warn or is_uncertain

            return ModelPredictionOutput(
                is_predicted=not is_uncertain,
                prediction=prediction,
                confidence=confidence,
                decision_score=decision_score,
                needs_llm_escalation=needs_llm,
                details=(
                    f"ML classified as {prediction} with confidence {confidence:.2f}"
                    + (" (Escalating to LLM)" if needs_llm else "")
                ),
            )

        except Exception as e:
            logger.error(f"Error during ML model inference: {e}", exc_info=True)
            # Graceful degradation: mark unpredicted so downstream LLM takes over
            return ModelPredictionOutput(
                is_predicted=False,
                prediction="UNKNOWN",
                confidence=0.0,
                decision_score=0.0,
                needs_llm_escalation=True,
                details=f"Inference error: {str(e)}",
            )


# Global singleton instance for efficient reuse across requests
ml_service = MLModelService()
