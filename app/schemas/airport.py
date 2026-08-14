from typing import List, Optional
from pydantic import BaseModel


class Airport(BaseModel):
    id: str
    name: str
    iata: str
    icao: str
    lat: float
    lon: float
    city: str
    country: str
    elevation_ft: int
    runways: int


class AirportListResponse(BaseModel):
    total: int
    airports: List[Airport]
