from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AirLabsFlight(BaseModel):
    """
    AirLabs Live Flight / ADS-B State Object.
    Documentation: https://airlabs.co/docs/flights
    """
    hex: str
    reg_number: Optional[str] = None
    flag: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    alt: Optional[float] = None  # Altitude in meters
    dir: Optional[float] = None  # Heading in degrees (0-360)
    speed: Optional[float] = None  # Horizontal speed in km/h
    v_speed: Optional[float] = None  # Vertical speed in km/h or m/s
    squawk: Optional[str] = None
    flight_number: Optional[str] = None
    flight_icao: Optional[str] = None
    flight_iata: Optional[str] = None
    dep_icao: Optional[str] = None
    dep_iata: Optional[str] = None
    arr_icao: Optional[str] = None
    arr_iata: Optional[str] = None
    airline_icao: Optional[str] = None
    airline_iata: Optional[str] = None
    aircraft_icao: Optional[str] = None
    updated: Optional[int] = None
    status: Optional[str] = None
    type: Optional[str] = None


class AirLabsFlightsResponse(BaseModel):
    total_items: Optional[int] = 0
    response: List[AirLabsFlight] = Field(default_factory=list)
