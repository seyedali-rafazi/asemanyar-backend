from typing import List, Optional
from fastapi import APIRouter, Query

from ....core.config import settings
from ....schemas.airlabs import AirLabsFlight
from ....services.airlabs_service import airlabs_service

router = APIRouter(prefix="/states", tags=["States"])


@router.get("/all", response_model=List[AirLabsFlight])
async def get_all_state_vectors(
    lamin: Optional[float] = Query(default=settings.DEFAULT_LAMIN, description="Lower latitude bound"),
    lomin: Optional[float] = Query(default=settings.DEFAULT_LOMIN, description="Lower longitude bound"),
    lamax: Optional[float] = Query(default=settings.DEFAULT_LAMAX, description="Upper latitude bound"),
    lomax: Optional[float] = Query(default=settings.DEFAULT_LOMAX, description="Upper longitude bound"),
    icao24: Optional[str] = Query(default=None, description="Filter by ICAO 24-bit hex address"),
    force_refresh: bool = Query(default=False, description="Force fresh fetch from AirLabs"),
):
    """
    Returns raw live AirLabs flight state vectors for the bounding box or specific hex.
    """
    flights, _, _ = await airlabs_service.get_flights(
        lamin=lamin,
        lomin=lomin,
        lamax=lamax,
        lomax=lomax,
        hex=icao24,
        force_refresh=force_refresh,
    )
    return flights
