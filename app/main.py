from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.v1.router import api_v1_router
from .core.config import settings
from .core.logging import logger, setup_logging
from .services.opensky_service import opensky_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}...")
    logger.info(f"OpenSky API Target: {settings.OPENSKY_BASE_URL}")
    if settings.OPENSKY_USERNAME:
        logger.info(f"OpenSky Authenticated as: {settings.OPENSKY_USERNAME}")
    else:
        logger.info("OpenSky running in Anonymous Mode (10s rate limit)")

    yield

    # Shutdown
    logger.info("Shutting down backend services...")
    await opensky_service.close()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="FastAPI Backend for Asemanha Flight Tracking - Powered by OpenSky Network API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS for Vite & React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 router
app.include_router(api_v1_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Health"])
async def root():
    """Root info endpoint."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online",
        "docs": "/docs",
        "endpoints": {
            "aircraft": f"{settings.API_V1_STR}/aircraft",
            "states": f"{settings.API_V1_STR}/states/all",
            "flights": f"{settings.API_V1_STR}/flights/interval",
            "airports": f"{settings.API_V1_STR}/airports",
            "antennas": f"{settings.API_V1_STR}/antennas",
            "stats": f"{settings.API_V1_STR}/stats",
            "websocket": f"{settings.API_V1_STR}/ws/live",
        },
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for container / system monitoring."""
    return {
        "status": "healthy",
        "opensky_authenticated": bool(settings.OPENSKY_USERNAME),
        "cache_ttl_seconds": settings.CACHE_TTL_SECONDS,
    }
