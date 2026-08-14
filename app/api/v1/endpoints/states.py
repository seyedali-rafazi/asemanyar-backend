from typing import List, Optional
from fastapi import APIRouter, Query

from ....core.config import settings
from ....schemas.opensky import OpenSkyStateVector
from ....services.opensky_service import opensky_service

router = APIRouter(prefix="/states", tags=["States"])


@router.get("/all", response_model=List[OpenSkyStateVector])
async def get_all_state_vectors(
    lamin: Optional[float] = Query(default=settings.DEFAULT_LAMIN, description="Lower latitude bound"),
    lomin: Optional[float] = Query(default=settings.DEFAULT_LOMIN, description="Lower longitude bound"),
    lamax: Optional[float] = Query(default=settings.DEFAULT_LAMAX, description="Upper latitude bound"),
    lomax: Optional[float] = Query(default=settings.DEFAULT_LOMAX, description="Upper longitude bound"),
    icao24: Optional[str] = Query(default=None, description="Filter by ICAO 24-bit hex address"),
    time: Optional[int] = Query(default=None, description="Unix timestamp"),
    force_refresh: bool = Query(default=False, description="Force fresh fetch from OpenSky"),
):
    """
    Direct proxy endpoint returning structured OpenSky state vectors.
    """
    state_vectors, _, _ = await opensky_service.get_states(
        lamin=lamin,
        lomin=lomin,
        lamax=lamax,
        lomax=lomax,
        icao24=icao24,
        timestamp=time,
        force_refresh=force_refresh,
    )
    return state_vectors
