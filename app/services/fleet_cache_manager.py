import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..core.config import settings
from ..core.logging import logger
from ..schemas.aircraft import (
    Aircraft,
    AircraftDetail,
    AircraftTrackResponse,
    FleetStats,
    TrackWaypoint,
)
from ..schemas.airlabs import AirLabsFlight
from .flight_enricher import (
    enrich_airlabs_flight,
    enrich_airlabs_flight_detail,
)
from .sample_data_service import sample_data_service


class FleetCacheManager:
    """
    Singleton in-memory and disk-persisted global aircraft cache manager.
    Enforces strict upstream quota (e.g. 10 requests per 24 hours) by serving
    all user requests (REST, WebSocket, stats, details, tracks) from the cached global fleet.
    """

    def __init__(self):
        self._aircraft: List[Aircraft] = []
        self._raw_flights: List[AirLabsFlight] = []
        self._aircraft_by_id: Dict[str, Aircraft] = {}
        self._raw_by_id: Dict[str, AirLabsFlight] = {}

        self.last_sync_time: int = 0
        self.next_sync_time: int = 0
        self.last_sync_status: str = "initial"
        self.last_sync_message: str = "Waiting for initial sync"
        self.is_using_fallback: bool = False

        # Rolling 24-hour request log
        self._api_call_timestamps: List[float] = []

    def _get_cache_file_path(self) -> Path:
        raw_path = Path(settings.AIRLABS_CACHE_FILE)
        if raw_path.is_absolute():
            return raw_path
        backend_dir = Path(__file__).resolve().parent.parent.parent
        return backend_dir / raw_path

    def _prune_old_api_calls(self) -> None:
        """Removes timestamps older than 24 hours."""
        cutoff = time.time() - 86400.0
        self._api_call_timestamps = [ts for ts in self._api_call_timestamps if ts >= cutoff]

    def can_make_api_call(self) -> Tuple[bool, str]:
        """
        Checks if an external API call is allowed under the 24-hour quota limit.
        """
        self._prune_old_api_calls()
        limit = settings.AIRLABS_MAX_DAILY_REQUESTS
        current_count = len(self._api_call_timestamps)

        if current_count >= limit:
            oldest = min(self._api_call_timestamps) if self._api_call_timestamps else time.time()
            wait_sec = int(max(0, (oldest + 86400.0) - time.time()))
            msg = (
                f"Daily API request limit reached ({current_count}/{limit} in 24h). "
                f"Next request slot available in ~{wait_sec // 60} minutes."
            )
            return False, msg

        return True, f"OK ({current_count}/{limit} requests used in 24h)"

    def record_api_call(self) -> None:
        """Records a timestamp for an external API call."""
        now = time.time()
        self._api_call_timestamps.append(now)
        self._prune_old_api_calls()
        logger.info(
            f"Recorded external AirLabs API call. Quota used: "
            f"{len(self._api_call_timestamps)}/{settings.AIRLABS_MAX_DAILY_REQUESTS} (24h window)"
        )

    def load_disk_cache(self) -> bool:
        """
        Loads cached global aircraft snapshot from disk on application startup.
        Returns True if cache was loaded and is usable.
        """
        cache_path = self._get_cache_file_path()
        if not cache_path.exists() or not cache_path.is_file():
            logger.info(f"No existing disk cache found at {cache_path}.")
            return False

        try:
            logger.info(f"Loading persistent aircraft cache from {cache_path}...")
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_aircraft = data.get("aircraft", [])
            raw_flights = data.get("raw_flights", [])
            cached_time = int(data.get("time") or 0)

            parsed_aircraft: List[Aircraft] = []
            lookup: Dict[str, Aircraft] = {}
            for item in raw_aircraft:
                try:
                    ac = Aircraft(**item)
                    parsed_aircraft.append(ac)
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

            parsed_raw: List[AirLabsFlight] = []
            raw_lookup: Dict[str, AirLabsFlight] = {}
            for item in raw_flights:
                try:
                    rf = AirLabsFlight(**item)
                    parsed_raw.append(rf)
                    if rf.hex:
                        raw_lookup[rf.hex.lower()] = rf
                except Exception:
                    continue

            if parsed_aircraft:
                self._aircraft = parsed_aircraft
                self._aircraft_by_id = lookup
                self._raw_flights = parsed_raw
                self._raw_by_id = raw_lookup
                self.last_sync_time = cached_time or int(time.time())
                self.next_sync_time = self.last_sync_time + settings.AIRLABS_SYNC_INTERVAL_SECONDS
                self.last_sync_status = "loaded_from_disk"
                self.last_sync_message = f"Loaded {len(parsed_aircraft)} global aircraft from disk cache"
                self.is_using_fallback = False
                logger.info(
                    f"Successfully loaded {len(parsed_aircraft)} aircraft from disk cache (recorded: {self.last_sync_time})."
                )
                return True

        except Exception as e:
            logger.error(f"Failed to read disk cache from {cache_path}: {e}")

        return False

    def save_disk_cache(self) -> bool:
        """
        Persists in-memory global aircraft to disk cache JSON file atomically.
        """
        cache_path = self._get_cache_file_path()
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "time": self.last_sync_time,
                "count": len(self._aircraft),
                "aircraft": [ac.model_dump() for ac in self._aircraft],
                "raw_flights": [rf.model_dump() for rf in self._raw_flights],
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }
            tmp_path = cache_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            tmp_path.replace(cache_path)
            logger.info(f"Saved {len(self._aircraft)} aircraft to persistent disk cache at {cache_path}.")
            return True
        except Exception as e:
            logger.error(f"Failed to write disk cache to {cache_path}: {e}")
            return False

    def update_fleet(
        self,
        raw_flights: List[AirLabsFlight],
        timestamp: Optional[int] = None,
        status: str = "success",
        message: str = "Successfully updated from AirLabs API",
    ) -> None:
        """
        Updates the global cache from fresh AirLabs API flight data.
        """
        now = timestamp or int(time.time())
        enriched_list: List[Aircraft] = []
        lookup: Dict[str, Aircraft] = {}
        raw_lookup: Dict[str, AirLabsFlight] = {}

        for f in raw_flights:
            if f.hex:
                raw_lookup[f.hex.lower()] = f
            ac = enrich_airlabs_flight(f)
            if ac:
                enriched_list.append(ac)
                if ac.id:
                    lookup[ac.id.lower()] = ac
                if ac.icao24:
                    lookup[ac.icao24.lower()] = ac
                if ac.callsign:
                    lookup[ac.callsign.lower()] = ac
                if ac.reg_number:
                    lookup[ac.reg_number.lower()] = ac

        if enriched_list:
            self._aircraft = enriched_list
            self._aircraft_by_id = lookup
            self._raw_flights = raw_flights
            self._raw_by_id = raw_lookup
            self.last_sync_time = now
            self.next_sync_time = now + settings.AIRLABS_SYNC_INTERVAL_SECONDS
            self.last_sync_status = status
            self.last_sync_message = message
            self.is_using_fallback = False
            self.save_disk_cache()
            logger.info(
                f"Global cache updated with {len(enriched_list)} aircraft. Next sync in {settings.AIRLABS_SYNC_INTERVAL_SECONDS}s."
            )
        else:
            logger.warning("Empty aircraft list received during update; preserving existing cache.")
            self.last_sync_status = "warning_empty"
            self.last_sync_message = "AirLabs returned empty aircraft array; existing cache retained"

    def ensure_data_loaded(self) -> None:
        """
        Ensures either cached data or sample fallback data is present in memory.
        """
        if not self._aircraft:
            loaded = self.load_disk_cache()
            if not loaded and settings.FALLBACK_SAMPLE_CACHE:
                logger.info("Initializing cache with sample data fallback.")
                sample_data_service.load_data()
                sample_list = sample_data_service._aircraft
                self._aircraft = sample_list
                self._aircraft_by_id = sample_data_service._aircraft_by_id
                self.last_sync_time = int(time.time())
                self.next_sync_time = self.last_sync_time + settings.AIRLABS_SYNC_INTERVAL_SECONDS
                self.last_sync_status = "sample_fallback"
                self.last_sync_message = "Operating in fallback mode (SampleData.json)"
                self.is_using_fallback = True

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
        """
        Filters the global cached fleet in-memory without making ANY external API requests.
        """
        self.ensure_data_loaded()

        has_bbox = (
            lamin is not None and lomin is not None and lamax is not None and lomax is not None
        )

        results: List[Aircraft] = []
        for ac in self._aircraft:
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

            if airline and airline.lower() not in ac.airline.lower():
                continue

            if min_altitude is not None and ac.altitude_ft < min_altitude:
                continue

            if max_altitude is not None and ac.altitude_ft > max_altitude:
                continue

            if on_ground is not None and ac.on_ground != on_ground:
                continue

            results.append(ac)

        return results

    def get_aircraft_detail(self, aircraft_id: str) -> Optional[AircraftDetail]:
        """
        Retrieves detail for a specific aircraft from in-memory cache without external API call.
        """
        self.ensure_data_loaded()
        clean_id = aircraft_id.strip().lower()

        # 1. Check raw AirLabs flights if available
        raw_flight = self._raw_by_id.get(clean_id)
        if raw_flight:
            detail = enrich_airlabs_flight_detail(raw_flight)
            if detail:
                return detail

        # 2. Check cached Aircraft objects
        ac = self._aircraft_by_id.get(clean_id)
        if not ac:
            for item in self._aircraft:
                if (
                    item.id.lower() == clean_id
                    or item.callsign.lower() == clean_id
                    or (item.reg_number and item.reg_number.lower() == clean_id)
                    or (item.flight_iata and item.flight_iata.lower() == clean_id)
                    or (item.flight_icao and item.flight_icao.lower() == clean_id)
                ):
                    ac = item
                    break

        if ac:
            return AircraftDetail(
                **ac.model_dump(),
                sensors=[],
                position_source="AirLabs-Cached",
                spi=False,
                time_position=self.last_sync_time or int(time.time()),
                last_contact=self.last_sync_time or int(time.time()),
                coordinates_str=f"{ac.lat:.4f}, {ac.lon:.4f}",
            )

        # 3. Fallback to sample data
        return sample_data_service.get_aircraft_detail(clean_id)

    def get_aircraft_track(self, aircraft_id: str) -> Optional[AircraftTrackResponse]:
        """
        Constructs track waypoints for an aircraft from cached data without external API call.
        """
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
                timestamp=self.last_sync_time or int(time.time()),
            )
            for p in detail.path
        ]
        return AircraftTrackResponse(
            id=detail.id.upper(),
            callsign=detail.callsign,
            startTime=int(self.last_sync_time - 3600 if self.last_sync_time else time.time() - 3600),
            endTime=int(self.last_sync_time or time.time()),
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
        """
        Computes fleet statistics over cached aircraft without external API call.
        """
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
            timestamp=self.last_sync_time or int(time.time()),
        )

    def get_raw_flights(
        self,
        lamin: Optional[float] = None,
        lomin: Optional[float] = None,
        lamax: Optional[float] = None,
        lomax: Optional[float] = None,
        hex: Optional[str] = None,
        airline_icao: Optional[str] = None,
        flight_icao: Optional[str] = None,
    ) -> List[AirLabsFlight]:
        """
        Returns cached raw flight state vectors matching filters.
        """
        self.ensure_data_loaded()

        has_bbox = (
            lamin is not None and lomin is not None and lamax is not None and lomax is not None
        )

        results: List[AirLabsFlight] = []
        for f in self._raw_flights:
            if hex and f.hex and f.hex.lower() != hex.lower():
                continue
            if airline_icao and f.airline_icao and f.airline_icao.upper() != airline_icao.upper():
                continue
            if flight_icao and f.flight_icao and f.flight_icao.upper() != flight_icao.upper():
                continue

            if has_bbox:
                if f.lat is None or f.lng is None:
                    continue
                if f.lat < lamin or f.lat > lamax:
                    continue
                if lomin <= lomax:
                    if f.lng < lomin or f.lng > lomax:
                        continue
                else:
                    if f.lng < lomin and f.lng > lomax:
                        continue

            results.append(f)

        return results

    def get_cache_status(self) -> Dict[str, Any]:
        """
        Returns rich status and quota metrics for monitoring.
        """
        self._prune_old_api_calls()
        now = time.time()
        calls_used = len(self._api_call_timestamps)
        limit = settings.AIRLABS_MAX_DAILY_REQUESTS
        quota_remaining = max(0, limit - calls_used)

        next_sync_in = int(max(0, self.next_sync_time - now)) if self.next_sync_time else 0
        cache_age_sec = int(max(0, now - self.last_sync_time)) if self.last_sync_time else 0

        return {
            "status": "healthy",
            "provider": "airlabs",
            "mode": "periodic_global_cache",
            "total_cached_aircraft": len(self._aircraft),
            "is_using_sample_fallback": self.is_using_fallback,
            "last_sync_timestamp": self.last_sync_time,
            "last_sync_iso": (
                datetime.fromtimestamp(self.last_sync_time, tz=timezone.utc).isoformat()
                if self.last_sync_time
                else None
            ),
            "cache_age_seconds": cache_age_sec,
            "cache_age_minutes": round(cache_age_sec / 60.0, 1),
            "next_sync_timestamp": self.next_sync_time,
            "next_sync_in_seconds": next_sync_in,
            "next_sync_in_minutes": round(next_sync_in / 60.0, 1),
            "sync_interval_seconds": settings.AIRLABS_SYNC_INTERVAL_SECONDS,
            "sync_interval_hours": round(settings.AIRLABS_SYNC_INTERVAL_SECONDS / 3600.0, 2),
            "daily_requests_used": calls_used,
            "daily_requests_limit": limit,
            "daily_quota_remaining": quota_remaining,
            "last_sync_status": self.last_sync_status,
            "last_sync_message": self.last_sync_message,
        }


# Global singleton instance
fleet_cache_manager = FleetCacheManager()
