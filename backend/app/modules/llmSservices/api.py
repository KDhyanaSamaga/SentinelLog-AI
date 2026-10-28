import logging
from fastapi import APIRouter, HTTPException, status
from app.core.config import settings
from app.modules.llmSservices.schemas import LogAnalysisRequest, LLMOutput
from app.modules.llmSservices.service import llm_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["AI-LLM Service"])


@router.get('/health')
async def health_check():
    """Verify connection to the Hugging Face Inference API."""
    if not settings.HF_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="HuggingFace API token (HF_TOKEN) is not configured in settings."
        )

    try:
        if not llm_service.is_configured:
            raise RuntimeError("Hugging Face token is not configured.")
        llm_service.check_connection()
        return {
            "status": "success",
            "message": "LLM connection active and verified.",
        }
    except Exception as e:
        logger.error(f"LLM health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM service connection check failed."
        )


@router.post('/analyze', response_model=LLMOutput)
async def analyze_log(payload: LogAnalysisRequest):
    """Analyze security logs using Hugging Face LLM service."""
    try:
        result = llm_service.analyze_and_explain(
            raw_log=payload.raw_log,
            component=payload.machine,
            log_type=payload.log_type,
            extra_context=payload.extra_context,
        )
        return LLMOutput.model_validate(result.model_dump())

    except Exception as e:
        logger.error(f"Log analysis request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process log analysis request."
        )