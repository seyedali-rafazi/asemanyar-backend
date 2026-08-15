from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from ....schemas.aircraft import AircraftTrackResponse
from .aircraft import get_aircraft_track

router = APIRouter(prefix="/tracks", tags=["Tracks"])


@router.get("/all", response_model=AircraftTrackResponse)
async def get_raw_track(
    icao24: str = Query(..., description="ICAO24 transponder address (hex)"),
    time: Optional[int] = Query(default=0, description="Unix timestamp (0 for current/latest)"),
):
    """
    Returns the flight trajectory / track waypoints for an aircraft.
    """
    return await get_aircraft_track(aircraft_id=icao24, time=time)
