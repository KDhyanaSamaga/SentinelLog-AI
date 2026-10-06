import logging
from fastapi import APIRouter, HTTPException, status
from huggingface_hub import InferenceClient

from app.core.config import Settings
from app.modules.llmSservices.schemas import LogAnalysisRequest, LLMOutput
from app.modules.llmSservices.promt import prompt

logger = logging.getLogger(__name__)

settings = Settings()

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
        client = InferenceClient(
            model="Qwen/Qwen2.5-72B-Instruct",
            token=settings.HF_TOKEN
        )

        client.chat.completions.create(
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5
        )
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
    if not settings.HF_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="HuggingFace API token (HF_TOKEN) is not configured in settings."
        )

    try:
        client = InferenceClient(
            model="Qwen/Qwen2.5-72B-Instruct",
            token=settings.HF_TOKEN
        )
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a senior cybersecurity expert. Analyze security logs accurately and concisely."
                },
                {
                    "role": "user",
                    "content": prompt(payload)
                }
            ],
            temperature=0.3,
            max_tokens=600
        )

        message = response.choices[0].message.content.strip()

        return LLMOutput(message=message)

    except Exception as e:
        logger.error(f"Log analysis request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process log analysis request."
        )