from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
    REFRESH_TOKEN_EXPIRE_DAYS: int =  int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS"))
    AUTO_REFRESH_THRESHOLD_SECONDS: int =  int(os.getenv("AUTO_REFRESH_THRESHOLD_SECONDS"))

    class Config:
        env_file = ".env"

settings = Settings()

#print(settings.model_dump())