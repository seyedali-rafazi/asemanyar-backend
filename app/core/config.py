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

    # Scheduled Sync & Quota Protection (Free API Optimization)
    # Sync every 2 hours = 7200 seconds (~10-12 calls per 24 hours)
    AIRLABS_SYNC_INTERVAL_SECONDS: int = 7200
    AIRLABS_MAX_DAILY_REQUESTS: int = 10
    AIRLABS_FETCH_GLOBAL: bool = True
    AIRLABS_AUTO_SYNC_ENABLED: bool = True
    AIRLABS_CACHE_FILE: str = "app/data/aircraft_cache.json"

    # Proxy Configuration (Optional)
    PROXY_URL: Optional[str] = None
    USE_SYSTEM_PROXY: bool = False

    # Cache Settings
    CACHE_TTL_SECONDS: int = 7200
    FALLBACK_SAMPLE_CACHE: bool = True

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
