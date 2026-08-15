import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..core.logging import logger
from ..schemas.aircraft import (
    Aircraft,
    AircraftDetail,
    AircraftListResponse,
    AircraftTrackResponse,
    FleetStats,
    TrackWaypoint,
)


class SampleDataService:
    """
    Fallback data service that loads and serves aircraft from SampleData.json
    when upstream AirLabs / live APIs are unavailable, rate-limited (HTTP 429),
    or return empty responses.
    """

    def __init__(self):
        self._aircraft: List[Aircraft] = []
        self._aircraft_by_id: Dict[str, Aircraft] = {}
        self._is_loaded: bool = False
        self._last_loaded_time: int = 0

    def _find_sample_file(self) -> Optional[Path]:
        """Finds the SampleData.json file across known project directories."""
        current_dir = Path(__file__).resolve().parent
        candidates = [
            current_dir.parent / "data" / "SampleData.json",
            current_dir.parent.parent.parent / "src" / "components" / "sample_data" / "SampleData.json",
            Path("d:/web project/asemenaha/ase/src/components/sample_data/SampleData.json"),
            Path.cwd() / "src" / "components" / "sample_data" / "SampleData.json",
            Path.cwd().parent / "src" / "components" / "sample_data" / "SampleData.json",
        ]
        for p in candidates:
            if p.exists() and p.is_file():
                return p
        return None

    def load_data(self) -> bool:
        """Loads sample aircraft records into memory."""
        if self._is_loaded and self._aircraft:
            return True

        file_path = self._find_sample_file()
        if not file_path:
            logger.warning("SampleData.json could not be located in project paths.")
            return False

        try:
            logger.info(f"Loading fallback sample data from {file_path}...")
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_list = data.get("aircraft", [])
            aircraft_list: List[Aircraft] = []
            lookup: Dict[str, Aircraft] = {}

            for item in raw_list:
                try:
                    ac = Aircraft(**item)
                    aircraft_list.append(ac)
                    if ac.id:
                        lookup[ac.id.lower()] = ac
                    if ac.icao24:
                        lookup[ac.icao24.lower()] = ac
                    if ac.callsign:
                        lookup[ac.callsign.lower()] = ac
                    if ac.reg_number:
                        lookup[ac.reg_number.lower()] = ac
                except Exception:
                    continue

            self._aircraft = aircraft_list
            self._aircraft_by_id = lookup
            self._is_loaded = True
            self._last_loaded_time = int(data.get("time") or time.time())
            logger.info(f"Loaded {len(self._aircraft)} sample aircraft records successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to load SampleData.json: {e}")
            return False

    def get_aircraft(
        self,
        lamin: Optional[float] = None,
        lomin: Optional[float] = None,
        lamax: Optional[float] = None,
        lomax: Optional[float] = None,
        search: Optional[str] = None,
        airline: Optional[str] = None,
        min_altitude: Optional[int] = None,
        max_altitude: Optional[int] = None,
        on_ground: Optional[bool] = None,
    ) -> List[Aircraft]:
        """Filters sample aircraft matching bounding box and query criteria."""
        self.load_data()
        results: List[Aircraft] = []

        has_bbox = (
            lamin is not None and lomin is not None and lamax is not None and lomax is not None
        )

        for ac in self._aircraft:
            # Bounding box filter
            if has_bbox:
                if ac.lat < lamin or ac.lat > lamax:
                    continue
                if lomin <= lomax:
                    if ac.lon < lomin or ac.lon > lomax:
                        continue
                else:
                    # Antimeridian wrap
                    if ac.lon < lomin and ac.lon > lomax:
                        continue

            # Text search filter
            if search:
                q = search.lower()
                match = (
                    q in ac.callsign.lower()
                    or q in ac.airline.lower()
                    or q in ac.id.lower()
                    or (ac.reg_number and q in ac.reg_number.lower())
                    or (ac.flight_iata and q in ac.flight_iata.lower())
                    or (ac.flight_icao and q in ac.flight_icao.lower())
                )
                if not match:
                    continue

            # Airline filter
            if airline and airline.lower() not in ac.airline.lower():
                continue

            # Altitude filter
            if min_altitude is not None and ac.altitude_ft < min_altitude:
                continue
            if max_altitude is not None and ac.altitude_ft > max_altitude:
                continue

            # On ground filter
            if on_ground is not None and ac.on_ground != on_ground:
                continue

            results.append(ac)

        return results

    def get_aircraft_detail(self, aircraft_id: str) -> Optional[AircraftDetail]:
        """Retrieves detail for a specific aircraft by ID, ICAO24, or callsign."""
        self.load_data()
        clean_id = aircraft_id.strip().lower()
        ac = self._aircraft_by_id.get(clean_id)
        if not ac:
            return None

        return AircraftDetail(
            **ac.model_dump(),
            sensors=[],
            position_source="Sample-ADS-B",
            spi=False,
            time_position=int(time.time()),
            last_contact=int(time.time()),
            coordinates_str=f"{ac.lat:.4f}, {ac.lon:.4f}",
        )

    def get_aircraft_track(self, aircraft_id: str) -> Optional[AircraftTrackResponse]:
        """Builds track waypoint response from sample aircraft path."""
        detail = self.get_aircraft_detail(aircraft_id)
        if not detail:
            return None

        waypoints = [
            TrackWaypoint(
                lat=p[0],
                lon=p[1],
                altitude_ft=detail.altitude_ft,
                heading_deg=detail.heading_deg,
                speed_kts=detail.speed_kts,
                timestamp=int(time.time()),
            )
            for p in detail.path
        ]
        return AircraftTrackResponse(
            id=detail.id.upper(),
            callsign=detail.callsign,
            startTime=int(time.time() - 3600),
            endTime=int(time.time()),
            waypoints=waypoints,
            path=[(p[0], p[1]) for p in detail.path],
            path_with_altitude=[(p[0], p[1], detail.altitude_ft) for p in detail.path],
        )

    def get_fleet_stats(
        self,
        lamin: Optional[float] = None,
        lomin: Optional[float] = None,
        lamax: Optional[float] = None,
        lomax: Optional[float] = None,
    ) -> FleetStats:
        """Computes fleet metrics over sample aircraft in bounding box."""
        valid = self.get_aircraft(lamin=lamin, lomin=lomin, lamax=lamax, lomax=lomax)
        total = len(valid)
        airborne = sum(1 for ac in valid if not ac.on_ground and ac.altitude_ft > 500)
        on_ground = total - airborne
        unique_airlines = len(set(ac.airline for ac in valid))
        unique_types = len(set(ac.aircraftType for ac in valid))
        avg_alt = int(sum(ac.altitude_ft for ac in valid) / total) if total > 0 else 0
        avg_spd = int(sum(ac.speed_kts for ac in valid) / total) if total > 0 else 0

        return FleetStats(
            total_aircraft=total,
            airborne=airborne,
            on_ground=on_ground,
            airlines_count=unique_airlines,
            aircraft_types_count=unique_types,
            avg_altitude_ft=avg_alt,
            avg_speed_kts=avg_spd,
            timestamp=int(time.time()),
        )


sample_data_service = SampleDataService()
