"""
Validated application configuration.

All security-sensitive settings are loaded from environment variables
and validated at startup.  Missing or invalid production settings cause
startup failure rather than falling back to unsafe defaults.
"""

from __future__ import annotations

import warnings
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str

    # ── JWT ───────────────────────────────────────────────────
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "sentinellog-ai"
    JWT_AUDIENCE: str = "sentinellog-ai"

    # ── Token lifetimes ───────────────────────────────────────
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Password policy ───────────────────────────────────────
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_MAX_LENGTH: int = 128

    # ── Rate limiting ─────────────────────────────────────────
    LOGIN_RATE_LIMIT: str = "5/minute"
    REGISTER_RATE_LIMIT: str = "3/minute"
    PASSWORD_RESET_RATE_LIMIT: str = "3/minute"

    # ── External services ─────────────────────────────────────
    HF_TOKEN: str = ""

    # ── Deprecated (backward compatibility) ───────────────────
    AUTO_REFRESH_THRESHOLD_SECONDS: int = 300

    # ── Validators ────────────────────────────────────────────

    @field_validator("SECRET_KEY")
    @classmethod
    def _warn_default_secret(cls, v: str) -> str:
        if v == "super-secret-key-change-in-production":
            warnings.warn(
                "Using default SECRET_KEY — change this in production!",
                UserWarning,
                stacklevel=2,
            )
        if len(v) < 32:
            warnings.warn(
                "SECRET_KEY should be at least 32 characters for production use.",
                UserWarning,
                stacklevel=2,
            )
        return v

    @field_validator("ALGORITHM")
    @classmethod
    def _restrict_algorithm(cls, v: str) -> str:
        allowed = {"HS256", "HS384", "HS512"}
        if v not in allowed:
            raise ValueError(f"ALGORITHM must be one of {allowed}, got {v!r}")
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def _validate_database_url(cls, v: str) -> str:
        if not v.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection string.")
        return v


settings = Settings()
