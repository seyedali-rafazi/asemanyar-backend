import time
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
from ....services.flight_enricher import (
    enrich_airlabs_flight,
    enrich_airlabs_flight_detail,
)
from ....services.airlabs_service import airlabs_service
from ....services.sample_data_service import sample_data_service

router = APIRouter(prefix="/aircraft", tags=["Aircraft"])


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
    force_refresh: bool = Query(default=False, description="Bypass cache and force fresh request"),
):
    """
    Returns enriched live aircraft fleet from AirLabs matching query filters.
    Defaults to configured bounding box (e.g. Iran airspace) unless cleared.
    Automatically falls back to SampleData.json if AirLabs is rate-limited, offline, or returns 0 flights.
    """
    enriched_list: List[Aircraft] = []
    timestamp = int(time.time())
    is_cached = False

    try:
        flights, ts, cached_flag = await airlabs_service.get_flights(
            lamin=lamin,
            lomin=lomin,
            lamax=lamax,
            lomax=lomax,
            force_refresh=force_refresh,
        )
        timestamp = ts or timestamp
        is_cached = cached_flag

        for f in flights:
            ac = enrich_airlabs_flight(f)
            if ac:
                enriched_list.append(ac)
    except Exception:
        pass

    # If AirLabs returned no flights (due to free tier rate-limit 429, no API key, or empty bounds),
    # seamlessly fall back to local SampleData.json
    if not enriched_list:
        sample_results = sample_data_service.get_aircraft(
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
            total=len(sample_results),
            count=len(sample_results),
            time=int(time.time()),
            aircraft=sample_results,
            cached=True,
        )

    # Apply Query Filters
    filtered_list: List[Aircraft] = []
    for ac in enriched_list:
        if search:
            q = search.lower()
            match = (
                q in ac.callsign.lower()
                or q in ac.airline.lower()
                or q in ac.id.lower()
                or (ac.reg_number and q in ac.reg_number.lower())
                or (ac.flight_iata and q in ac.flight_iata.lower())
            )
            if not match:
                continue

        if airline and airline.lower() not in ac.airline.lower():
            continue

        if min_altitude is not None and ac.altitude_ft < min_altitude:
            continue

        if max_altitude is not None and ac.altitude_ft > max_altitude:
            continue

        if on_ground is not None and ac.on_ground != on_ground:
            continue

        filtered_list.append(ac)

    return AircraftListResponse(
        total=len(filtered_list),
        count=len(filtered_list),
        time=timestamp,
        aircraft=filtered_list,
        cached=is_cached,
    )


@router.get("/{aircraft_id}", response_model=AircraftDetail)
async def get_aircraft_detail(aircraft_id: str):
    """
    Retrieves full telemetry, route, and details for a specific aircraft by ICAO24 Hex or callsign.
    Falls back to SampleData.json if not found in live stream.
    """
    clean_id = aircraft_id.strip().lower()

    try:
        # 1. Direct hex query
        flights, _, _ = await airlabs_service.get_flights(hex=clean_id)
        if not flights:
            # 2. Search in current bounding box fleet
            all_flights, _, _ = await airlabs_service.get_flights(
                lamin=settings.DEFAULT_LAMIN,
                lomin=settings.DEFAULT_LOMIN,
                lamax=settings.DEFAULT_LAMAX,
                lomax=settings.DEFAULT_LOMAX,
            )
            flights = [
                f for f in all_flights
                if f.hex.lower() == clean_id
                or (f.flight_icao and f.flight_icao.lower() == clean_id)
                or (f.flight_iata and f.flight_iata.lower() == clean_id)
                or (f.reg_number and f.reg_number.lower() == clean_id)
            ]

        if flights:
            detail = enrich_airlabs_flight_detail(flights[0])
            if detail:
                return detail
    except Exception:
        pass

    # Fallback to sample data
    sample_detail = sample_data_service.get_aircraft_detail(clean_id)
    if sample_detail:
        return sample_detail

    raise HTTPException(
        status_code=404,
        detail=f"Aircraft '{aircraft_id}' not found in active reports or sample data",
    )


@router.get("/{aircraft_id}/track", response_model=AircraftTrackResponse)
async def get_aircraft_track(aircraft_id: str, time: Optional[int] = 0):
    """
    Retrieves flight trajectory / track waypoints for the specified aircraft.
    """
    clean_id = aircraft_id.strip().lower()

    try:
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
    except Exception:
        sample_track = sample_data_service.get_aircraft_track(clean_id)
        if sample_track:
            return sample_track
        raise HTTPException(
            status_code=404,
            detail=f"Track for aircraft '{aircraft_id}' not found",
        )

