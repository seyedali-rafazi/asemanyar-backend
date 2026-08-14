from typing import Any, List, Optional
from pydantic import BaseModel, Field


class OpenSkyStateVector(BaseModel):
    """
    OpenSky Network State Vector schema corresponding to index positions:
    0: icao24 (str)
    1: callsign (str | None)
    2: origin_country (str)
    3: time_position (int | None)
    4: last_contact (int)
    5: longitude (float | None)
    6: latitude (float | None)
    7: baro_altitude (float | None) [m]
    8: on_ground (bool)
    9: velocity (float | None) [m/s]
    10: true_track (float | None) [deg]
    11: vertical_rate (float | None) [m/s]
    12: sensors (List[int] | None)
    13: geo_altitude (float | None) [m]
    14: squawk (str | None)
    15: spi (bool)
    16: position_source (int) [0=ADS-B, 1=ASTERIX, 2=MLAT, 3=FLARM]
    17: category (int | None) [optional]
    """
    icao24: str
    callsign: Optional[str] = None
    origin_country: str
    time_position: Optional[int] = None
    last_contact: int
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    baro_altitude: Optional[float] = None  # in meters
    on_ground: bool = False
    velocity: Optional[float] = None  # in m/s
    true_track: Optional[float] = None  # degrees clockwise from North
    vertical_rate: Optional[float] = None  # in m/s
    sensors: Optional[List[int]] = None
    geo_altitude: Optional[float] = None  # in meters
    squawk: Optional[str] = None
    spi: bool = False
    position_source: int = 0
    category: Optional[int] = 0

    @classmethod
    def from_raw_list(cls, raw: List[Any]) -> "OpenSkyStateVector":
        return cls(
            icao24=str(raw[0]).strip().lower() if raw[0] else "",
            callsign=str(raw[1]).strip() if raw[1] is not None and str(raw[1]).strip() else None,
            origin_country=str(raw[2]) if raw[2] is not None else "",
            time_position=raw[3] if len(raw) > 3 else None,
            last_contact=raw[4] if len(raw) > 4 and raw[4] is not None else 0,
            longitude=raw[5] if len(raw) > 5 else None,
            latitude=raw[6] if len(raw) > 6 else None,
            baro_altitude=raw[7] if len(raw) > 7 else None,
            on_ground=bool(raw[8]) if len(raw) > 8 and raw[8] is not None else False,
            velocity=raw[9] if len(raw) > 9 else None,
            true_track=raw[10] if len(raw) > 10 else None,
            vertical_rate=raw[11] if len(raw) > 11 else None,
            sensors=raw[12] if len(raw) > 12 and isinstance(raw[12], list) else None,
            geo_altitude=raw[13] if len(raw) > 13 else None,
            squawk=str(raw[14]).strip() if len(raw) > 14 and raw[14] is not None else None,
            spi=bool(raw[15]) if len(raw) > 15 and raw[15] is not None else False,
            position_source=raw[16] if len(raw) > 16 and raw[16] is not None else 0,
            category=raw[17] if len(raw) > 17 else 0,
        )


class OpenSkyStatesResponse(BaseModel):
    time: int
    states: Optional[List[List[Any]]] = None


class OpenSkyFlight(BaseModel):
    icao24: str
    firstSeen: int
    estDepartureAirport: Optional[str] = None
    lastSeen: int
    estArrivalAirport: Optional[str] = None
    callsign: Optional[str] = None
    estDepartureAirportHorizDistance: Optional[int] = None
    estDepartureAirportVertDistance: Optional[int] = None
    estArrivalAirportHorizDistance: Optional[int] = None
    estArrivalAirportVertDistance: Optional[int] = None
    departureAirportCandidatesCount: Optional[int] = 0
    arrivalAirportCandidatesCount: Optional[int] = 0


class OpenSkyTrackWaypoint(BaseModel):
    time: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    baro_altitude: Optional[float] = None
    true_track: Optional[float] = None
    on_ground: bool = False


class OpenSkyTrackResponse(BaseModel):
    icao24: str
    startTime: int
    endTime: int
    callsign: Optional[str] = None
    path: List[List[Any]] = Field(default_factory=list)
