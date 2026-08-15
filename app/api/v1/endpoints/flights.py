from typing import List, Optional
from fastapi import APIRouter, Query

from ....schemas.airlabs import AirLabsFlight
from ....services.fleet_cache_manager import fleet_cache_manager

router = APIRouter(prefix="/flights", tags=["Flights"])


@router.get("/all", response_model=List[AirLabsFlight])
async def get_all_flights(
    airline_icao: Optional[str] = Query(default=None, description="Filter by Airline ICAO code"),
    flight_icao: Optional[str] = Query(default=None, description="Filter by Flight ICAO number"),
):
    """
    Retrieves active flights matching airline or flight code from the in-memory cache.
    Zero external API calls are made.
    """
    return fleet_cache_manager.get_raw_flights(
        airline_icao=airline_icao,
        flight_icao=flight_icao,
    )


@router.get("/aircraft/{icao24}", response_model=List[AirLabsFlight])
async def get_flights_by_aircraft(
    icao24: str,
):
    """
    Retrieves flight telemetry for a specific aircraft transponder (hex) from cache.
    Zero external API calls are made.
    """
    return fleet_cache_manager.get_raw_flights(hex=icao24)
