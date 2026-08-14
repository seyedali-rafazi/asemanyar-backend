import json
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException

from ....schemas.airport import Airport, AirportListResponse

router = APIRouter(prefix="/airports", tags=["Airports"])


def _load_airports() -> List[Airport]:
    file_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "..",
        "src",
        "pages",
        "Home",
        "components",
        "AirportLayer",
        "data",
        "iran_airports.json",
    )
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [Airport(**item) for item in data]
        except Exception:
            pass

    # Built-in fallback
    return [
        Airport(id="AP001", name="Imam Khomeini International", iata="IKA", icao="OIIE", lat=35.4161, lon=51.1522, city="Tehran", country="Iran", elevation_ft=3305, runways=2),
        Airport(id="AP002", name="Mehrabad International", iata="THR", icao="OIII", lat=35.6892, lon=51.3134, city="Tehran", country="Iran", elevation_ft=3954, runways=2),
        Airport(id="AP003", name="Mashhad International", iata="MHD", icao="OIMM", lat=36.2352, lon=59.641, city="Mashhad", country="Iran", elevation_ft=3263, runways=2),
        Airport(id="AP004", name="Shiraz International", iata="SYZ", icao="OISS", lat=29.5392, lon=52.5898, city="Shiraz", country="Iran", elevation_ft=4924, runways=2),
        Airport(id="AP005", name="Isfahan International", iata="IFN", icao="OIFM", lat=32.7508, lon=51.8614, city="Isfahan", country="Iran", elevation_ft=5312, runways=2),
    ]


AIRPORTS = _load_airports()


@router.get("", response_model=AirportListResponse)
async def list_airports():
    """
    Returns reference list of major airports with ICAO/IATA codes and positions.
    """
    return AirportListResponse(total=len(AIRPORTS), airports=AIRPORTS)


@router.get("/{code}", response_model=Airport)
async def get_airport(code: str):
    """
    Retrieves airport by ICAO (e.g. OIII) or IATA (e.g. THR) or ID.
    """
    c = code.strip().upper()
    for ap in AIRPORTS:
        if ap.icao.upper() == c or ap.iata.upper() == c or ap.id.upper() == c:
            return ap
    raise HTTPException(status_code=404, detail=f"Airport '{code}' not found")
