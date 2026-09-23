"""
This is the entry point of your FastAPI application.

Run:
    uvicorn app.main:app --reload

Python starts from main.py.
This file creates the FastAPI application and registers
the application routes/routers.
"""

from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from app.core.config import Settings
from app.core.database import engine


app = FastAPI(
    title="Log-Analysis-AI",
    description="Backend API",
    version="1.0.0",
)


@app.get("/health")
async def check_db_connection():
    """
    Health-check endpoint.

    Checks whether the application can successfully
    connect to the database.
    """

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

        return {
            "status": "healthy",
            "database": "connected"
        }

    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e)
            }
        )