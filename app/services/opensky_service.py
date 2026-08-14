import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from ..core.config import settings
from ..core.logging import logger
from ..schemas.opensky import (
    OpenSkyFlight,
    OpenSkyStateVector,
    OpenSkyStatesResponse,
    OpenSkyTrackResponse,
)
from .cache_service import cache_service


class OpenSkyService:
    """
    Asynchronous OpenSky Network REST API Client with connection pooling,
    authentication, rate limit handling, and in-memory TTL caching.
    """

    def __init__(self):
        self.base_url = settings.OPENSKY_BASE_URL.rstrip("/")
        self.timeout = httpx.Timeout(settings.OPENSKY_REQUEST_TIMEOUT, connect=6.0)
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            auth = None
            if settings.OPENSKY_USERNAME and settings.OPENSKY_PASSWORD:
                auth = (settings.OPENSKY_USERNAME, settings.OPENSKY_PASSWORD)
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                auth=auth,
                trust_env=False,
                headers={"User-Agent": "Asemanha-Flight-Tracker/1.0"},
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _build_cache_key(self, prefix: str, params: Dict[str, Any]) -> str:
        param_str = "_".join(f"{k}:{v}" for k, v in sorted(params.items()) if v is not None)
        return f"{prefix}_{param_str}"

    async def get_states(
        self,
        lamin: Optional[float] = None,
        lomin: Optional[float] = None,
        lamax: Optional[float] = None,
        lomax: Optional[float] = None,
        icao24: Optional[str] = None,
        timestamp: Optional[int] = None,
        force_refresh: bool = False,
    ) -> Tuple[List[OpenSkyStateVector], int, bool]:
        """
        Retrieves state vectors for all aircraft or within a bounding box.
        Returns (state_vectors, timestamp, is_cached).
        """
        params: Dict[str, Any] = {"extended": 1}
        if lamin is not None:
            params["lamin"] = lamin
        if lomin is not None:
            params["lomin"] = lomin
        if lamax is not None:
            params["lamax"] = lamax
        if lomax is not None:
            params["lomax"] = lomax
        if icao24 is not None:
            params["icao24"] = icao24.lower()
        if timestamp is not None:
            params["time"] = timestamp

        cache_key = self._build_cache_key("states", params)

        if not force_refresh:
            cached_data = cache_service.get(cache_key)
            if cached_data:
                state_vectors, ts = cached_data
                return state_vectors, ts, True

        # Fetch from OpenSky API
        client = await self.get_client()
        url = f"{self.base_url}/states/all"

        try:
            logger.info(f"Fetching live states from OpenSky API: {params}")
            resp = await client.get(url, params=params)
            
            if resp.status_code == 200:
                data = resp.json()
                ts = data.get("time", int(time.time()))
                raw_states = data.get("states") or []
                
                state_vectors = [
                    OpenSkyStateVector.from_raw_list(st)
                    for st in raw_states
                    if isinstance(st, list) and len(st) >= 7
                ]
                
                cache_service.set(cache_key, (state_vectors, ts), ttl=settings.CACHE_TTL_SECONDS)
                return state_vectors, ts, False

            elif resp.status_code == 429:
                logger.warning("OpenSky API rate limit reached (HTTP 429). Utilizing cached fallback.")
            else:
                logger.warning(f"OpenSky API returned HTTP {resp.status_code}: {resp.text[:200]}")

        except Exception as e:
            logger.error(f"Error connecting to OpenSky API: {str(e)}")

        # Fallback to stale cache
        fallback = cache_service.get_fallback(cache_key)
        if fallback:
            state_vectors, ts = fallback
            logger.info(f"Returning stale cache with {len(state_vectors)} aircraft.")
            return state_vectors, ts, True

        # Initial fallback seed data if OpenSky is unreachable on first boot
        seed_vectors = self._load_seed_vectors(lamin, lomin, lamax, lomax)
        curr_ts = int(time.time())
        cache_service.set(cache_key, (seed_vectors, curr_ts), ttl=settings.CACHE_TTL_SECONDS)
        return seed_vectors, curr_ts, True

    async def get_track(
        self,
        icao24: str,
        timestamp: Optional[int] = 0,
    ) -> Optional[OpenSkyTrackResponse]:
        """
        Retrieves trajectory / track waypoints for a specific aircraft transponder.
        """
        cache_key = f"track_{icao24.lower()}_{timestamp or 0}"
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        client = await self.get_client()
        url = f"{self.base_url}/tracks/all"
        params = {"icao24": icao24.lower(), "time": timestamp or 0}

        try:
            logger.info(f"Fetching track from OpenSky for {icao24}")
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                track_resp = OpenSkyTrackResponse(**data)
                cache_service.set(cache_key, track_resp, ttl=60)
                return track_resp
            elif resp.status_code == 404:
                logger.info(f"No active track found on OpenSky for {icao24}")
            else:
                logger.warning(f"OpenSky track endpoint returned HTTP {resp.status_code}")
        except Exception as e:
            logger.error(f"Error fetching track for {icao24}: {str(e)}")

        return cache_service.get_fallback(cache_key)

    async def get_flights_interval(
        self,
        begin: int,
        end: int,
    ) -> List[OpenSkyFlight]:
        """Retrieves flights active during the given time interval."""
        cache_key = f"flights_interval_{begin}_{end}"
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        client = await self.get_client()
        url = f"{self.base_url}/flights/all"
        params = {"begin": begin, "end": end}

        try:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                raw_list = resp.json() or []
                flights = [OpenSkyFlight(**item) for item in raw_list if isinstance(item, dict)]
                cache_service.set(cache_key, flights, ttl=60)
                return flights
        except Exception as e:
            logger.error(f"Error fetching interval flights: {str(e)}")

        return cache_service.get_fallback(cache_key) or []

    async def get_flights_by_aircraft(
        self,
        icao24: str,
        begin: int,
        end: int,
    ) -> List[OpenSkyFlight]:
        """Retrieves flights for a specific aircraft within time interval."""
        cache_key = f"flights_aircraft_{icao24.lower()}_{begin}_{end}"
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        client = await self.get_client()
        url = f"{self.base_url}/flights/aircraft"
        params = {"icao24": icao24.lower(), "begin": begin, "end": end}

        try:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                raw_list = resp.json() or []
                flights = [OpenSkyFlight(**item) for item in raw_list if isinstance(item, dict)]
                cache_service.set(cache_key, flights, ttl=60)
                return flights
        except Exception as e:
            logger.error(f"Error fetching flights for {icao24}: {str(e)}")

        return cache_service.get_fallback(cache_key) or []

    async def get_departures_by_airport(
        self,
        airport_icao: str,
        begin: int,
        end: int,
    ) -> List[OpenSkyFlight]:
        """Retrieves departures for a given airport (ICAO code) within interval."""
        cache_key = f"departures_{airport_icao.upper()}_{begin}_{end}"
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        client = await self.get_client()
        url = f"{self.base_url}/flights/departure"
        params = {"airport": airport_icao.upper(), "begin": begin, "end": end}

        try:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                raw_list = resp.json() or []
                flights = [OpenSkyFlight(**item) for item in raw_list if isinstance(item, dict)]
                cache_service.set(cache_key, flights, ttl=60)
                return flights
        except Exception as e:
            logger.error(f"Error fetching departures for {airport_icao}: {str(e)}")

        return cache_service.get_fallback(cache_key) or []

    async def get_arrivals_by_airport(
        self,
        airport_icao: str,
        begin: int,
        end: int,
    ) -> List[OpenSkyFlight]:
        """Retrieves arrivals for a given airport (ICAO code) within interval."""
        cache_key = f"arrivals_{airport_icao.upper()}_{begin}_{end}"
        cached = cache_service.get(cache_key)
        if cached:
            return cached

        client = await self.get_client()
        url = f"{self.base_url}/flights/arrival"
        params = {"airport": airport_icao.upper(), "begin": begin, "end": end}

        try:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                raw_list = resp.json() or []
                flights = [OpenSkyFlight(**item) for item in raw_list if isinstance(item, dict)]
                cache_service.set(cache_key, flights, ttl=60)
                return flights
        except Exception as e:
            logger.error(f"Error fetching arrivals for {airport_icao}: {str(e)}")

        return cache_service.get_fallback(cache_key) or []

    def _load_seed_vectors(
        self,
        lamin: Optional[float] = None,
        lomin: Optional[float] = None,
        lamax: Optional[float] = None,
        lomax: Optional[float] = None,
    ) -> List[OpenSkyStateVector]:
        """Loads fallback seed state vectors from local data if OpenSky is unavailable."""
        seed_files = [
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "..",
                "src",
                "pages",
                "Home",
                "components",
                "AircraftLayer",
                "data",
                "iran_aircraft_50.json",
            ),
        ]

        for path in seed_files:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    vectors = []
                    for idx, item in enumerate(data):
                        lat = item.get("lat")
                        lon = item.get("lon")
                        
                        # Apply bbox filter if provided
                        if lamin is not None and lat < lamin:
                            continue
                        if lamax is not None and lat > lamax:
                            continue
                        if lomin is not None and lon < lomin:
                            continue
                        if lomax is not None and lon > lomax:
                            continue

                        alt_m = item.get("altitude_ft", 30000) / 3.28084
                        speed_ms = item.get("speed_kts", 350) / 1.94384
                        heading = item.get("heading_deg", 0)
                        
                        sv = OpenSkyStateVector(
                            icao24=item.get("id", f"seed{idx:03d}").lower(),
                            callsign=item.get("callsign", f"FL{idx:03d}"),
                            origin_country="Iran",
                            time_position=int(time.time()),
                            last_contact=int(time.time()),
                            longitude=lon,
                            latitude=lat,
                            baro_altitude=alt_m,
                            on_ground=False,
                            velocity=speed_ms,
                            true_track=float(heading),
                            vertical_rate=0.0,
                            geo_altitude=alt_m,
                            position_source=0,
                            category=4,
                        )
                        vectors.append(sv)
                    
                    logger.info(f"Loaded {len(vectors)} seed aircraft state vectors from {path}")
                    return vectors
                except Exception as ex:
                    logger.error(f"Error loading seed vectors: {ex}")

        return []


opensky_service = OpenSkyService()
