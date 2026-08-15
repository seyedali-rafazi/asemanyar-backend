import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AliasChoices

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[
            str(BASE_DIR / ".env"),
            str(BASE_DIR.parent / ".env"),
            ".env",
            "backend/.env",
        ],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    APP_NAME: str = "Asemanha Flight Tracking API"
    APP_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # AirLabs API Configuration (https://airlabs.co/docs/flights)
    AIRLABS_BASE_URL: str = "https://airlabs.co/api/v9"
    AIRLABS_API_KEY: Optional[str] = Field(
        default="15d21aa3-9c9d-4ad0-ba71-5eedcb2b2f7b",
        validation_alias=AliasChoices("AIRLABS_API_KEY", "api_key", "AIRLABS_KEY")
    )
    AIRLABS_REQUEST_TIMEOUT: float = 30.0
    AIRLABS_CONNECT_TIMEOUT: float = 20.0

    # Proxy Configuration (Optional)
    PROXY_URL: Optional[str] = None
    USE_SYSTEM_PROXY: bool = False

    # Cache Settings
    CACHE_TTL_SECONDS: int = 10
    FALLBACK_SAMPLE_CACHE: bool = False

    # Default Bounding Box (Iran airspace coordinates)
    DEFAULT_LAMIN: Optional[float] = 24.0
    DEFAULT_LOMIN: Optional[float] = 44.0
    DEFAULT_LAMAX: Optional[float] = 40.0
    DEFAULT_LOMAX: Optional[float] = 64.0

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]


settings = Settings()
