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
    
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ]

    model_config = SettingsConfigDict(
        env_file=str(env_file_path),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
