"""
Async SQLAlchemy engine, session factory, and declarative base.

The engine uses the DATABASE_URL from settings (which must specify an
async-compatible driver such as ``postgresql+asyncpg``).  Alembic
migrations run synchronously via a separate URL derived in
``alembic/env.py``.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Shared SQLAlchemy metadata base for application models and Alembic."""


engine = create_async_engine(settings.DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    """FastAPI dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        yield session
