import time
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from ....schemas.airlabs import AirLabsFlight
from ....services.airlabs_service import airlabs_service

router = APIRouter(prefix="/flights", tags=["Flights"])


@router.get("/all", response_model=List[AirLabsFlight])
async def get_all_flights(
    airline_icao: Optional[str] = Query(default=None, description="Filter by Airline ICAO code"),
    flight_icao: Optional[str] = Query(default=None, description="Filter by Flight ICAO number"),
):
    """
    Retrieves active live flights matching airline or flight code from AirLabs.
    """
    flights, _, _ = await airlabs_service.get_flights(
        airline_icao=airline_icao,
        flight_icao=flight_icao,
    )
    return flights


@router.get("/aircraft/{icao24}", response_model=List[AirLabsFlight])
async def get_flights_by_aircraft(
    icao24: str,
):
    """
    Retrieves flight telemetry for a specific aircraft transponder (hex).
    """
    flights, _, _ = await airlabs_service.get_flights(hex=icao24)
    return flights
