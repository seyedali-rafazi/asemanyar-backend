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

    # OpenSky Network API
    OPENSKY_BASE_URL: str = "https://opensky-network.org/api"
    OPENSKY_AUTH_URL: str = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
    OPENSKY_USERNAME: Optional[str] = None
    OPENSKY_PASSWORD: Optional[str] = None
    OPENSKY_CLIENT_ID: Optional[str] = Field(default=None, validation_alias=AliasChoices("OPENSKY_CLIENT_ID", "clientId", "CLIENT_ID"))
    OPENSKY_CLIENT_SECRET: Optional[str] = Field(default=None, validation_alias=AliasChoices("OPENSKY_CLIENT_SECRET", "clientSecret", "CLIENT_SECRET"))
    OPENSKY_REQUEST_TIMEOUT: float = 25.0
    OPENSKY_CONNECT_TIMEOUT: float = 15.0

    # Proxy Configuration (Optional - for environments requiring proxy to reach OpenSky)
    PROXY_URL: Optional[str] = None
    USE_SYSTEM_PROXY: bool = False

    # Cache Settings
    CACHE_TTL_SECONDS: int = 10
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
