from typing import List, Optional
from pydantic import BaseModel


class Antenna(BaseModel):
    id: str
    name: str
    type: str
    lat: float
    lon: float
    range_km: Optional[int] = 0
    status: Optional[str] = "active"
    frequency: Optional[str] = None
    frequency_mhz: Optional[float] = None
    operator: Optional[str] = None
    city: Optional[str] = None
    code: Optional[str] = None


class AntennaListResponse(BaseModel):
    total: int
    antennas: List[Antenna]
