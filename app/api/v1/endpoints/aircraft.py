from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from ....core.config import settings
from ....schemas.aircraft import (
    Aircraft,
    AircraftDetail,
    AircraftListResponse,
    AircraftTrackResponse,
    TrackWaypoint,
)
from ....services.flight_enricher import enrich_state_vector, enrich_state_vector_detail
from ....services.opensky_service import opensky_service

router = APIRouter(prefix="/aircraft", tags=["Aircraft"])


@router.get("", response_model=AircraftListResponse)
async def list_aircraft(
    lamin: Optional[float] = Query(default=settings.DEFAULT_LAMIN, description="Lower latitude bound"),
    lomin: Optional[float] = Query(default=settings.DEFAULT_LOMIN, description="Lower longitude bound"),
    lamax: Optional[float] = Query(default=settings.DEFAULT_LAMAX, description="Upper latitude bound"),
    lomax: Optional[float] = Query(default=settings.DEFAULT_LOMAX, description="Upper longitude bound"),
    search: Optional[str] = Query(default=None, description="Search callsign, airline, or ICAO24"),
    airline: Optional[str] = Query(default=None, description="Filter by airline name"),
    min_altitude: Optional[int] = Query(default=None, description="Min altitude in feet"),
    max_altitude: Optional[int] = Query(default=None, description="Max altitude in feet"),
    on_ground: Optional[bool] = Query(default=None, description="Filter airborne vs on ground"),
    force_refresh: bool = Query(default=False, description="Bypass cache and force fresh request"),
):
    """
    Returns enriched live aircraft fleet matching query filters.
    Defaults to configured bounding box (e.g. Iran airspace) unless cleared.
    """
    state_vectors, timestamp, is_cached = await opensky_service.get_states(
        lamin=lamin,
        lomin=lomin,
        lamax=lamax,
        lomax=lomax,
        force_refresh=force_refresh,
    )

    enriched_list: List[Aircraft] = []
    for sv in state_vectors:
        ac = enrich_state_vector(sv)
        if not ac:
            continue

        # Filters
        if search:
            q = search.lower()
            if q not in ac.callsign.lower() and q not in ac.airline.lower() and q not in ac.id.lower():
                continue

        if airline and airline.lower() not in ac.airline.lower():
            continue

        if min_altitude is not None and ac.altitude_ft < min_altitude:
            continue

        if max_altitude is not None and ac.altitude_ft > max_altitude:
            continue

        if on_ground is not None and ac.on_ground != on_ground:
            continue

        enriched_list.append(ac)

    return AircraftListResponse(
        total=len(enriched_list),
        count=len(enriched_list),
        time=timestamp,
        aircraft=enriched_list,
        cached=is_cached,
    )


@router.get("/{aircraft_id}", response_model=AircraftDetail)
async def get_aircraft_detail(aircraft_id: str):
    """
    Retrieves full telemetry, sensors, and details for a specific aircraft by ICAO24 or ID.
    """
    clean_id = aircraft_id.strip().lower()
    
    # Query specific state from OpenSky
    state_vectors, _, _ = await opensky_service.get_states(icao24=clean_id)
    
    # If not found with exact icao24 query, search current cached fleet
    if not state_vectors:
        all_states, _, _ = await opensky_service.get_states(
            lamin=settings.DEFAULT_LAMIN,
            lomin=settings.DEFAULT_LOMIN,
            lamax=settings.DEFAULT_LAMAX,
            lomax=settings.DEFAULT_LOMAX,
        )
        state_vectors = [
            sv for sv in all_states
            if sv.icao24.lower() == clean_id or (sv.callsign and sv.callsign.lower() == clean_id)
        ]

    if not state_vectors:
        raise HTTPException(
            status_code=404,
            detail=f"Aircraft '{aircraft_id}' not found in current airspace reports",
        )

    detail = enrich_state_vector_detail(state_vectors[0])
    if not detail:
        raise HTTPException(
            status_code=404,
            detail=f"Telemetry data unavailable for aircraft '{aircraft_id}'",
        )

    return detail


@router.get("/{aircraft_id}/track", response_model=AircraftTrackResponse)
async def get_aircraft_track(aircraft_id: str, time: Optional[int] = 0):
    """
    Retrieves flight trajectory / track waypoints from OpenSky for the specified aircraft.
    """
    clean_id = aircraft_id.strip().lower()
    track = await opensky_service.get_track(icao24=clean_id, timestamp=time)
    
    if not track or not track.path:
        # Generate synthetic path from current state if OpenSky track is not yet recorded
        detail = await get_aircraft_detail(clean_id)
        waypoints = [
            TrackWaypoint(
                lat=p[0],
                lon=p[1],
                altitude_ft=detail.altitude_ft,
                heading_deg=detail.heading_deg,
                speed_kts=detail.speed_kts,
            )
            for p in detail.path
        ]
        return AircraftTrackResponse(
            id=aircraft_id.upper(),
            callsign=detail.callsign,
            startTime=int(detail.time_position or 0),
            endTime=int(detail.last_contact or 0),
            waypoints=waypoints,
            path=[(p[0], p[1]) for p in detail.path],
            path_with_altitude=[(p[0], p[1], detail.altitude_ft) for p in detail.path],
        )

    waypoints: List[TrackWaypoint] = []
    path_2d = []
    path_3d = []

    for point in track.path:
        # OpenSky format: [time, latitude, longitude, baro_altitude, true_track, on_ground]
        if len(point) >= 3 and point[1] is not None and point[2] is not None:
            t = point[0]
            lat = round(float(point[1]), 4)
            lon = round(float(point[2]), 4)
            alt_m = point[3] if len(point) > 3 and point[3] is not None else 0.0
            alt_ft = int(round(alt_m * 3.28084))
            heading = int(round(point[4])) if len(point) > 4 and point[4] is not None else None

            waypoints.append(
                TrackWaypoint(
                    lat=lat,
                    lon=lon,
                    altitude_ft=alt_ft,
                    heading_deg=heading,
                    timestamp=t,
                )
            )
            path_2d.append((lat, lon))
            path_3d.append((lat, lon, alt_ft))

    return AircraftTrackResponse(
        id=track.icao24.upper(),
        callsign=track.callsign,
        startTime=track.startTime,
        endTime=track.endTime,
        waypoints=waypoints,
        path=path_2d,
        path_with_altitude=path_3d,
    )
