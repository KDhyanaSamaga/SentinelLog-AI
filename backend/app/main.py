"""
This is the entry point of your FastAPI application.

Run:
    uvicorn app.main:app --reload

Python starts from main.py.
This file creates the FastAPI application and registers
the application routes/routers.
"""

from fastapi import FastAPI

from app.modules.llmSservices.api import router as llm_router
from app.health import router as health_router

app = FastAPI(
    title="Log-Analysis-AI",
    description="Backend API",
    version="1.0.0",
)

# Register routers
app.include_router(health_router)
app.include_router(llm_router)


