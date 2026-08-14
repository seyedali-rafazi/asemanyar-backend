import time
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from ....schemas.opensky import OpenSkyFlight
from ....services.opensky_service import opensky_service

router = APIRouter(prefix="/flights", tags=["Flights"])


@router.get("/interval", response_model=List[OpenSkyFlight])
async def get_flights_interval(
    begin: Optional[int] = Query(default=None, description="Start timestamp (Unix epoch in seconds)"),
    end: Optional[int] = Query(default=None, description="End timestamp (Unix epoch in seconds)"),
):
    """
    Retrieves flights in a given time interval (max interval 2 hours per OpenSky specs).
    """
    now = int(time.time())
    b = begin or (now - 3600)  # default past 1 hour
    e = end or now

    if e - b > 7200:
        raise HTTPException(status_code=400, detail="Time interval cannot exceed 2 hours (7200 seconds)")

    flights = await opensky_service.get_flights_interval(begin=b, end=e)
    return flights


@router.get("/aircraft/{icao24}", response_model=List[OpenSkyFlight])
async def get_flights_by_aircraft(
    icao24: str,
    begin: Optional[int] = Query(default=None, description="Start timestamp (Unix epoch in seconds)"),
    end: Optional[int] = Query(default=None, description="End timestamp (Unix epoch in seconds)"),
):
    """
    Retrieves flight history for a specific aircraft transponder.
    """
    now = int(time.time())
    b = begin or (now - 86400 * 2)  # default past 48 hours
    e = end or now

    flights = await opensky_service.get_flights_by_aircraft(icao24=icao24, begin=b, end=e)
    return flights


@router.get("/departures/{airport_icao}", response_model=List[OpenSkyFlight])
async def get_airport_departures(
    airport_icao: str,
    begin: Optional[int] = Query(default=None, description="Start timestamp (Unix epoch in seconds)"),
    end: Optional[int] = Query(default=None, description="End timestamp (Unix epoch in seconds)"),
):
    """
    Retrieves departures for a specific airport ICAO code (e.g. OIII, OIIE, OIMM).
    """
    now = int(time.time())
    b = begin or (now - 86400)  # default past 24 hours
    e = end or now

    flights = await opensky_service.get_departures_by_airport(airport_icao=airport_icao, begin=b, end=e)
    return flights


@router.get("/arrivals/{airport_icao}", response_model=List[OpenSkyFlight])
async def get_airport_arrivals(
    airport_icao: str,
    begin: Optional[int] = Query(default=None, description="Start timestamp (Unix epoch in seconds)"),
    end: Optional[int] = Query(default=None, description="End timestamp (Unix epoch in seconds)"),
):
    """
    Retrieves arrivals for a specific airport ICAO code (e.g. OIII, OIIE, OIMM).
    """
    now = int(time.time())
    b = begin or (now - 86400)  # default past 24 hours
    e = end or now

    flights = await opensky_service.get_arrivals_by_airport(airport_icao=airport_icao, begin=b, end=e)
    return flights
