import json
import os
from typing import List
from fastapi import APIRouter, HTTPException

from ....schemas.antenna import Antenna, AntennaListResponse

router = APIRouter(prefix="/antennas", tags=["Antennas"])


def _load_antennas() -> List[Antenna]:
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
        "AntennaLayer",
        "data",
        "iran_antennas.json",
    )
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [Antenna(**item) for item in data]
        except Exception:
            pass

    return [
        Antenna(id="ANT001", name="Tehran North Radar", code="THR-RAD-1", lat=35.75, lon=51.40, city="Tehran", range_km=250, frequency_mhz=1090.0, type="Primary Radar", status="Active"),
        Antenna(id="ANT002", name="Mashhad East Sensor", code="MHD-ADS-1", lat=36.25, lon=59.60, city="Mashhad", range_km=300, frequency_mhz=1090.0, type="ADS-B Receiver", status="Active"),
        Antenna(id="ANT003", name="Shiraz South Sensor", code="SYZ-ADS-1", lat=29.55, lon=52.60, city="Shiraz", range_km=280, frequency_mhz=1090.0, type="ADS-B Receiver", status="Active"),
    ]


ANTENNAS = _load_antennas()


@router.get("", response_model=AntennaListResponse)
async def list_antennas():
    """
    Returns reference list of ground tracking antennas and ADS-B receivers.
    """
    return AntennaListResponse(total=len(ANTENNAS), antennas=ANTENNAS)


@router.get("/{antenna_id}", response_model=Antenna)
async def get_antenna(antenna_id: str):
    """
    Retrieves antenna details by ID or code.
    """
    a_id = antenna_id.strip().upper()
    for ant in ANTENNAS:
        if ant.id.upper() == a_id or ant.code.upper() == a_id:
            return ant
    raise HTTPException(status_code=404, detail=f"Antenna '{antenna_id}' not found")
