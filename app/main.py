from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.v1.router import api_v1_router
from .core.config import settings
from .core.logging import logger, setup_logging
from .services.airlabs_service import airlabs_service
from .services.fleet_cache_manager import fleet_cache_manager
from .services.sync_worker import sync_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}...")
    logger.info(f"Flight Data Provider: AirLabs API (https://airlabs.co)")
    logger.info(f"Scheduled 2-Hour Global Cache Sync: {settings.AIRLABS_SYNC_INTERVAL_SECONDS}s interval")
    logger.info(f"Daily API Quota Limit: {settings.AIRLABS_MAX_DAILY_REQUESTS} requests/24h")

    if settings.AIRLABS_API_KEY:
        logger.info(f"AirLabs API Key: {settings.AIRLABS_API_KEY[:8]}...")
    else:
        logger.warning("AirLabs API Key: Not Configured (Using SampleData fallback)")

    # Load initial disk cache / sample data
    fleet_cache_manager.ensure_data_loaded()

    # Start background 2-hour periodic sync worker
    if settings.AIRLABS_AUTO_SYNC_ENABLED:
        sync_worker.start()

    yield

    # Shutdown
    logger.info("Shutting down backend services...")
    await sync_worker.stop()
    await airlabs_service.close()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="FastAPI Backend for Asemanha Flight Tracking - Powered by AirLabs Global Scheduled Cache",
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
        "provider": "airlabs",
        "mode": "scheduled_global_cache",
        "docs": "/docs",
        "endpoints": {
            "aircraft": f"{settings.API_V1_STR}/aircraft",
            "cache_status": f"{settings.API_V1_STR}/aircraft/cache/status",
            "states": f"{settings.API_V1_STR}/states/all",
            "flights": f"{settings.API_V1_STR}/flights/all",
            "airports": f"{settings.API_V1_STR}/airports",
            "antennas": f"{settings.API_V1_STR}/antennas",
            "stats": f"{settings.API_V1_STR}/stats",
            "websocket": f"{settings.API_V1_STR}/ws/live",
        },
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check and quota status endpoint."""
    status = fleet_cache_manager.get_cache_status()
    status["airlabs_configured"] = bool(settings.AIRLABS_API_KEY)
    return status
