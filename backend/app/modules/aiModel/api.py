import logging
from fastapi import APIRouter, HTTPException, status

from app.modules.aiModel.schemas import ModelInput, ModelPredictionOutput
from app.modules.aiModel.service import ml_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/model", tags=["AI-Model"])


@router.get("/health")
def model_health():
    """Check readiness and availability of the trained ML pipeline."""
    return {
        "status": "ready" if ml_service.is_ready else "unavailable",
        "model_path": str(ml_service.model_path),
        "is_ready": ml_service.is_ready,
    }


@router.post("/predict", response_model=ModelPredictionOutput)
def predict_log(payload: ModelInput):
    """
    Direct ML model inference endpoint.
    Receives validated structured log attributes and returns ML prediction.
    """
    if not ml_service.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ML Classifier is not initialized or model file is unavailable.",
        )

    try:
        result = ml_service.predict_log(payload)
        return result
    except Exception as e:
        logger.error(f"Prediction failed in API handler: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error executing model prediction.",
        )
