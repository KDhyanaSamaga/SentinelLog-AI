"""
SentinelLog-AI — Application entry point.

Run:
    uvicorn app.main:app --reload

This file creates the FastAPI application, registers all routers,
and configures middleware (rate limiting, error handling, worker lifecycle).
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.rate_limiter import limiter
from app.health import router as health_router
from app.modules.aiModel.api import router as ai_model_router
from app.modules.auth.api import router as auth_router
from app.modules.llmSservices.api import router as llm_router
from app.modules.log.api import router as log_router
from app.modules.log.queue import queue_manager
from app.modules.organization.api import router as org_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup initialization and graceful shutdown."""
    # ── Startup ───────────────────────────────────────────────────────────
    await queue_manager.initialize()
    queue_manager.start()
    yield
    # ── Shutdown ──────────────────────────────────────────────────────────
    await queue_manager.stop()


app = FastAPI(
    title="SentinelLog-AI",
    description="Security log analysis backend with ML triage and LLM-powered incident response.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate limiter middleware ───────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Routers ───────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(org_router)
app.include_router(llm_router)
app.include_router(ai_model_router)
app.include_router(log_router)
