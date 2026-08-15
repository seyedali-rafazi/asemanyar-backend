import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

from ....core.config import settings
from ....schemas.aircraft import (
    Aircraft,
    AircraftDetail,
    AircraftListResponse,
    AircraftTrackResponse,
)
from ....services.fleet_cache_manager import fleet_cache_manager
from ....services.sync_worker import sync_worker

router = APIRouter(prefix="/aircraft", tags=["Aircraft"])


@router.get("/cache/status", response_model=Dict[str, Any])
async def get_cache_status():
    """
    Returns global aircraft cache health, last sync time, next sync time,
    and 24-hour upstream API quota usage.
    """
    return fleet_cache_manager.get_cache_status()


@router.post("/cache/sync", response_model=Dict[str, Any])
async def trigger_cache_sync():
    """
    Manually triggers background sync if 24-hour quota permits.
    """
    can_call, msg = fleet_cache_manager.can_make_api_call()
    if not can_call:
        raise HTTPException(status_code=429, detail=msg)

    sync_worker.trigger_sync()
    return {
        "status": "sync_triggered",
        "message": "Manual sync event scheduled in background worker.",
        "quota": fleet_cache_manager.get_cache_status(),
    }


@router.get("", response_model=AircraftListResponse)
async def list_aircraft(
    lamin: Optional[float] = Query(default=settings.DEFAULT_LAMIN, description="Lower latitude bound"),
    lomin: Optional[float] = Query(default=settings.DEFAULT_LOMIN, description="Lower longitude bound"),
    lamax: Optional[float] = Query(default=settings.DEFAULT_LAMAX, description="Upper latitude bound"),
    lomax: Optional[float] = Query(default=settings.DEFAULT_LOMAX, description="Upper longitude bound"),
    zoom: Optional[float] = Query(default=None, description="Current map zoom level"),
    search: Optional[str] = Query(default=None, description="Search callsign, airline, or ICAO24"),
    airline: Optional[str] = Query(default=None, description="Filter by airline name"),
    min_altitude: Optional[int] = Query(default=None, description="Min altitude in feet"),
    max_altitude: Optional[int] = Query(default=None, description="Max altitude in feet"),
    on_ground: Optional[bool] = Query(default=None, description="Filter airborne vs on ground"),
    force_refresh: bool = Query(default=False, description="Ignored for rate-limit protection"),
):
    """
    Returns enriched live aircraft fleet matching query filters.
    All queries are served instantly from the persistent in-memory global cache
    (synced every 2 hours, max 10 requests / 24h) without making any external API calls.
    """
    filtered_list = fleet_cache_manager.get_aircraft(
        lamin=lamin,
        lomin=lomin,
        lamax=lamax,
        lomax=lomax,
        search=search,
        airline=airline,
        min_altitude=min_altitude,
        max_altitude=max_altitude,
        on_ground=on_ground,
    )

    return AircraftListResponse(
        total=len(filtered_list),
        count=len(filtered_list),
        time=fleet_cache_manager.last_sync_time or int(time.time()),
        aircraft=filtered_list,
        cached=True,
    )


@router.get("/{aircraft_id}", response_model=AircraftDetail)
async def get_aircraft_detail(aircraft_id: str):
    """
    Retrieves full telemetry, route, and details for a specific aircraft by ICAO24 Hex or callsign.
    Served from the global in-memory cache without making any external API calls.
    """
    detail = fleet_cache_manager.get_aircraft_detail(aircraft_id)
    if detail:
        return detail

    raise HTTPException(
        status_code=404,
        detail=f"Aircraft '{aircraft_id}' not found in active reports or sample data",
    )


@router.get("/{aircraft_id}/track", response_model=AircraftTrackResponse)
async def get_aircraft_track(aircraft_id: str, time: Optional[int] = 0):
    """
    Retrieves flight trajectory / track waypoints for the specified aircraft.
    Served from the global in-memory cache without making any external API calls.
    """
    track = fleet_cache_manager.get_aircraft_track(aircraft_id)
    if track:
        return track

    raise HTTPException(
        status_code=404,
        detail=f"Track for aircraft '{aircraft_id}' not found",
    )
