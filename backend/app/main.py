"""
SentinelLog-AI — Application entry point.

Run:
    uvicorn app.main:app --reload

This file creates the FastAPI application, registers all routers,
and configures middleware (rate limiting, error handling).
"""

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.rate_limiter import limiter
from app.health import router as health_router
from app.modules.auth.api import router as auth_router
from app.modules.llmSservices.api import router as llm_router
from app.modules.organization.api import router as org_router

app = FastAPI(
    title="SentinelLog-AI",
    description="Security log analysis backend with ML triage and LLM-powered incident response.",
    version="1.0.0",
)

# ── Rate limiter middleware ───────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Routers ───────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(org_router)
app.include_router(llm_router)
