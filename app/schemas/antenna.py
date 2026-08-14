from typing import List
from pydantic import BaseModel


class Antenna(BaseModel):
    id: str
    name: str
    code: str
    lat: float
    lon: float
    city: str
    range_km: int
    frequency_mhz: float
    type: str
    status: str


class AntennaListResponse(BaseModel):
    total: int
    antennas: List[Antenna]
