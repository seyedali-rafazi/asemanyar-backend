from typing import List, Optional, Tuple
from pydantic import BaseModel, Field


class Aircraft(BaseModel):
    id: str  # ICAO24 or formatted ID
    callsign: str
    airline: str
    aircraftType: str
    lat: float
    lon: float
    altitude_ft: int
    heading_deg: int
    speed_kts: int
    origin_city: str
    destination_city: str
    path: List[Tuple[float, float]] = Field(default_factory=list)
    lastUpdate: str
    
    # Extended properties
    icao24: Optional[str] = None
    country: Optional[str] = None
    squawk: Optional[str] = None
    on_ground: Optional[bool] = False
    vertical_rate_fpm: Optional[int] = 0
    geo_altitude_ft: Optional[int] = None
    category: Optional[int] = 0

    # Rich AirLabs / Route properties
    reg_number: Optional[str] = None
    flight_icao: Optional[str] = None
    flight_iata: Optional[str] = None
    dep_iata: Optional[str] = None
    dep_icao: Optional[str] = None
    arr_iata: Optional[str] = None
    arr_icao: Optional[str] = None
    airline_icao: Optional[str] = None
    airline_iata: Optional[str] = None
    aircraft_icao: Optional[str] = None
    status: Optional[str] = None


class AircraftDetail(Aircraft):
    sensors: Optional[List[int]] = None
    position_source: Optional[str] = "ADS-B"
    spi: Optional[bool] = False
    time_position: Optional[int] = None
    last_contact: Optional[int] = None
    coordinates_str: Optional[str] = None


class AircraftListResponse(BaseModel):
    total: int
    count: int
    time: int
    aircraft: List[Aircraft]
    cached: bool = False


class FleetStats(BaseModel):
    total_aircraft: int
    airborne: int
    on_ground: int
    airlines_count: int
    aircraft_types_count: int
    avg_altitude_ft: int
    avg_speed_kts: int
    timestamp: int


class TrackWaypoint(BaseModel):
    lat: float
    lon: float
    altitude_ft: int
    heading_deg: Optional[int] = None
    speed_kts: Optional[int] = None
    timestamp: Optional[int] = None


class AircraftTrackResponse(BaseModel):
    id: str
    callsign: Optional[str] = None
    startTime: int
    endTime: int
    waypoints: List[TrackWaypoint] = Field(default_factory=list)
    path: List[Tuple[float, float]] = Field(default_factory=list)
    path_with_altitude: List[Tuple[float, float, int]] = Field(default_factory=list)
