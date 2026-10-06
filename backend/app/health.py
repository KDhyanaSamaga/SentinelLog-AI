from fastapi import FastAPI, HTTPException, APIRouter

from sqlalchemy import text

from app.core.config import Settings
from app.core.database import engine

router = APIRouter(tags=["Health"])

@router.get("/health")
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