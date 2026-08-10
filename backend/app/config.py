import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load backend/.env explicitly
env_file_path = Path(__file__).resolve().parent.parent / ".env"
if env_file_path.exists():
    load_dotenv(dotenv_path=env_file_path, override=True)
else:
    load_dotenv(override=True)

class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    
    # MongoDB settings
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "paperlens"
    
    # ChromaDB settings
    CHROMADB_DIR: str = "./chroma_db"
    
    # OpenAI Settings
    OPENAI_API_KEY: str = ""
    
    # JWT Settings
    JWT_SECRET_KEY: str = "supersecretkeypaperlens123"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # SendGrid & OTP Settings
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = "noreply@paperlens.ai"
    SENDGRID_FROM_NAME: str = "PaperLens Workspace"
    OTP_EXPIRATION_MINUTES: int = 5
    OTP_RESEND_COOLDOWN_SECONDS: int = 60
    MAX_OTP_ATTEMPTS: int = 5
    MAX_OTP_RESENDS_PER_HOUR: int = 3

    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=str(env_file_path),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
