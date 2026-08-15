from typing import Optional
from fastapi import APIRouter, Query

from ....core.config import settings
from ....schemas.aircraft import FleetStats
from ....services.fleet_cache_manager import fleet_cache_manager

router = APIRouter(prefix="/stats", tags=["Stats"])


@router.get("", response_model=FleetStats)
async def get_fleet_stats(
    lamin: Optional[float] = Query(default=settings.DEFAULT_LAMIN, description="Lower latitude bound"),
    lomin: Optional[float] = Query(default=settings.DEFAULT_LOMIN, description="Lower longitude bound"),
    lamax: Optional[float] = Query(default=settings.DEFAULT_LAMAX, description="Upper latitude bound"),
    lomax: Optional[float] = Query(default=settings.DEFAULT_LOMAX, description="Upper longitude bound"),
    zoom: Optional[float] = Query(default=None, description="Current map zoom level"),
):
    """
    Computes summary telemetry and metrics for the active fleet using the global in-memory cache.
    Zero external API calls are made.
    """
    return fleet_cache_manager.get_fleet_stats(
        lamin=lamin,
        lomin=lomin,
        lamax=lamax,
        lomax=lomax,
    )
