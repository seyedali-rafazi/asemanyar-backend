from typing import List, Optional
from fastapi import APIRouter, Query

from ....core.config import settings
from ....schemas.airlabs import AirLabsFlight
from ....services.fleet_cache_manager import fleet_cache_manager

router = APIRouter(prefix="/states", tags=["States"])


@router.get("/all", response_model=List[AirLabsFlight])
async def get_all_state_vectors(
    lamin: Optional[float] = Query(default=settings.DEFAULT_LAMIN, description="Lower latitude bound"),
    lomin: Optional[float] = Query(default=settings.DEFAULT_LOMIN, description="Lower longitude bound"),
    lamax: Optional[float] = Query(default=settings.DEFAULT_LAMAX, description="Upper latitude bound"),
    lomax: Optional[float] = Query(default=settings.DEFAULT_LOMAX, description="Upper longitude bound"),
    icao24: Optional[str] = Query(default=None, description="Filter by ICAO 24-bit hex address"),
    force_refresh: bool = Query(default=False, description="Ignored for rate-limit protection"),
):
    """
    Returns raw cached flight state vectors matching the bounding box or specific hex.
    Zero external API calls are made.
    """
    return fleet_cache_manager.get_raw_flights(
        lamin=lamin,
        lomin=lomin,
        lamax=lamax,
        lomax=lomax,
        hex=icao24,
    )
