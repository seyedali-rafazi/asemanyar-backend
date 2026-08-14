from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from ....schemas.opensky import OpenSkyTrackResponse
from ....services.opensky_service import opensky_service

router = APIRouter(prefix="/tracks", tags=["Tracks"])


@router.get("/all", response_model=OpenSkyTrackResponse)
async def get_raw_track(
    icao24: str = Query(..., description="ICAO24 transponder address (hex)"),
    time: Optional[int] = Query(default=0, description="Unix timestamp (0 for current/latest)"),
):
    """
    Direct proxy endpoint returning the raw OpenSky trajectory/track for an aircraft.
    """
    track = await opensky_service.get_track(icao24=icao24, timestamp=time)
    if not track:
        raise HTTPException(
            status_code=404,
            detail=f"Track for aircraft '{icao24}' not found or has no recorded waypoints",
        )
    return track
