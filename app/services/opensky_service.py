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
        self.auth_url = settings.OPENSKY_AUTH_URL
        self.timeout = httpx.Timeout(
            timeout=settings.OPENSKY_REQUEST_TIMEOUT,
            connect=settings.OPENSKY_CONNECT_TIMEOUT,
        )
        self._client: Optional[httpx.AsyncClient] = None
        self._oauth_token: Optional[str] = None
        self._oauth_token_expiry: float = 0.0

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            auth = None
            if settings.OPENSKY_USERNAME and settings.OPENSKY_PASSWORD:
                auth = (settings.OPENSKY_USERNAME, settings.OPENSKY_PASSWORD)

            client_kwargs: Dict[str, Any] = {
                "timeout": self.timeout,
                "auth": auth,
                "headers": {"User-Agent": "Asemanha-Flight-Tracker/1.0"},
                "trust_env": settings.USE_SYSTEM_PROXY,
            }
            if settings.PROXY_URL:
                client_kwargs["proxy"] = settings.PROXY_URL

            self._client = httpx.AsyncClient(**client_kwargs)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def get_auth_headers(self) -> Dict[str, str]:
        """
        Returns authorization headers using OAuth2 Bearer token if clientId & clientSecret
        are configured.
        """
        client_id = settings.OPENSKY_CLIENT_ID
        client_secret = settings.OPENSKY_CLIENT_SECRET

        if not client_id or not client_secret:
            return {}

        # Check if valid cached OAuth2 token exists
        if self._oauth_token and time.time() < (self._oauth_token_expiry - 60):
            return {"Authorization": f"Bearer {self._oauth_token}"}

        # Request fresh OAuth2 access token
        try:
            client = await self.get_client()
            logger.info(f"Requesting OpenSky OAuth2 token for client ID '{client_id}'...")
            payload = {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            }
            resp = await client.post(
                self.auth_url,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if resp.status_code == 200:
                data = resp.json()
                self._oauth_token = data.get("access_token")
                expires_in = data.get("expires_in", 1800)
                self._oauth_token_expiry = time.time() + expires_in
                logger.info(f"OpenSky OAuth2 token refreshed successfully (expires in {expires_in}s).")
                return {"Authorization": f"Bearer {self._oauth_token}"}
            else:
                logger.error(f"OpenSky OAuth2 token request failed ({resp.status_code}): {resp.text}")
                self._oauth_token = None
        except Exception as e:
            logger.error(f"Error fetching OpenSky OAuth2 token: {self._format_error(e)}")
            self._oauth_token = None

        return {}

    def _format_error(self, e: Exception) -> str:
        err_type = type(e).__name__
        msg = str(e).strip()
        if not msg:
            if isinstance(e, httpx.ConnectTimeout):
                return f"{err_type}: Connection to OpenSky timed out (exceeded {settings.OPENSKY_CONNECT_TIMEOUT}s). OpenSky might be blocked or unreachable from this network."
            elif isinstance(e, httpx.ReadTimeout):
                return f"{err_type}: Read timed out while waiting for OpenSky response (exceeded {settings.OPENSKY_REQUEST_TIMEOUT}s)."
            elif isinstance(e, httpx.ConnectError):
                return f"{err_type}: Failed to connect to OpenSky. Check network or proxy settings."
            return f"{err_type}: Network error or host unreachable"
        return f"{err_type}: {msg}"

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
        headers = await self.get_auth_headers()
        url = f"{self.base_url}/states/all"

        try:
            logger.info(f"Fetching live states from OpenSky API: {params}")
            resp = await client.get(url, params=params, headers=headers)
            
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

            elif resp.status_code == 401:
                logger.warning("OpenSky API returned HTTP 401 Unauthorized. Invalidating cached OAuth2 token.")
                self._oauth_token = None
            elif resp.status_code == 429:
                logger.warning("OpenSky API rate limit reached (HTTP 429). Utilizing cached fallback.")
            else:
                logger.warning(f"OpenSky API returned HTTP {resp.status_code}: {resp.text[:200]}")

        except Exception as e:
            logger.error(f"Error connecting to OpenSky API: {self._format_error(e)}")

        # 1. Fallback to stale cache if it contains aircraft
        fallback = cache_service.get_fallback(cache_key)
        if fallback:
            state_vectors, ts = fallback
            if state_vectors and len(state_vectors) > 0:
                logger.info(f"Returning stale cache with {len(state_vectors)} aircraft.")
                return state_vectors, ts, True

        # 2. Initial fallback seed data if OpenSky is unreachable or cache was empty
        if settings.FALLBACK_SAMPLE_CACHE:
            seed_vectors = self._load_seed_vectors(lamin, lomin, lamax, lomax)
            if seed_vectors:
                curr_ts = int(time.time())
                cache_service.set(cache_key, (seed_vectors, curr_ts), ttl=settings.CACHE_TTL_SECONDS)
                logger.info(f"Returning {len(seed_vectors)} seed fallback aircraft vectors.")
                return seed_vectors, curr_ts, True

        return [], int(time.time()), True

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
        headers = await self.get_auth_headers()
        url = f"{self.base_url}/tracks/all"
        params = {"icao24": icao24.lower(), "time": timestamp or 0}

        try:
            logger.info(f"Fetching track from OpenSky for {icao24}")
            resp = await client.get(url, params=params, headers=headers)
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
            logger.error(f"Error fetching track for {icao24}: {self._format_error(e)}")

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
        headers = await self.get_auth_headers()
        url = f"{self.base_url}/flights/all"
        params = {"begin": begin, "end": end}

        try:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                raw_list = resp.json() or []
                flights = [OpenSkyFlight(**item) for item in raw_list if isinstance(item, dict)]
                cache_service.set(cache_key, flights, ttl=60)
                return flights
        except Exception as e:
            logger.error(f"Error fetching interval flights: {self._format_error(e)}")

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
        headers = await self.get_auth_headers()
        url = f"{self.base_url}/flights/aircraft"
        params = {"icao24": icao24.lower(), "begin": begin, "end": end}

        try:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                raw_list = resp.json() or []
                flights = [OpenSkyFlight(**item) for item in raw_list if isinstance(item, dict)]
                cache_service.set(cache_key, flights, ttl=60)
                return flights
        except Exception as e:
            logger.error(f"Error fetching flights for {icao24}: {self._format_error(e)}")

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
        headers = await self.get_auth_headers()
        url = f"{self.base_url}/flights/departure"
        params = {"airport": airport_icao.upper(), "begin": begin, "end": end}

        try:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                raw_list = resp.json() or []
                flights = [OpenSkyFlight(**item) for item in raw_list if isinstance(item, dict)]
                cache_service.set(cache_key, flights, ttl=60)
                return flights
        except Exception as e:
            logger.error(f"Error fetching departures for {airport_icao}: {self._format_error(e)}")

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
        headers = await self.get_auth_headers()
        url = f"{self.base_url}/flights/arrival"
        params = {"airport": airport_icao.upper(), "begin": begin, "end": end}

        try:
            resp = await client.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                raw_list = resp.json() or []
                flights = [OpenSkyFlight(**item) for item in raw_list if isinstance(item, dict)]
                cache_service.set(cache_key, flights, ttl=60)
                return flights
        except Exception as e:
            logger.error(f"Error fetching arrivals for {airport_icao}: {self._format_error(e)}")

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
            os.path.join(os.path.dirname(__file__), "..", "data", "iran_aircraft_50.json"),
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
            os.path.join(os.getcwd(), "backend", "app", "data", "iran_aircraft_50.json"),
            os.path.join(os.getcwd(), "src", "pages", "Home", "components", "AircraftLayer", "data", "iran_aircraft_50.json"),
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
                    
                    if vectors:
                        logger.info(f"Loaded {len(vectors)} seed aircraft state vectors from {path}")
                        return vectors
                except Exception as ex:
                    logger.error(f"Error loading seed vectors: {ex}")

        # Fallback synthetic seed vectors if file could not be loaded
        synthetic = []
        sample_coords = [
            ("738045", "IRA450", 35.6892, 51.3134, 32000, 440, 120),
            ("738046", "MAH512", 32.7508, 51.8614, 28000, 420, 85),
            ("738047", "TBZ601", 36.2352, 59.6410, 34000, 460, 240),
            ("738048", "IRC205", 29.5392, 52.5898, 25000, 380, 15),
            ("738049", "VRH300", 38.1339, 46.2350, 30000, 410, 160),
            ("738050", "QSM710", 27.2183, 56.3778, 31000, 430, 330),
        ]
        curr_t = int(time.time())
        for idx, (icao, cs, lat, lon, alt_ft, spd_kts, hdg) in enumerate(sample_coords):
            if lamin is not None and lat < lamin:
                continue
            if lamax is not None and lat > lamax:
                continue
            if lomin is not None and lon < lomin:
                continue
            if lomax is not None and lon > lomax:
                continue
            synthetic.append(
                OpenSkyStateVector(
                    icao24=icao,
                    callsign=cs,
                    origin_country="Iran",
                    time_position=curr_t,
                    last_contact=curr_t,
                    longitude=lon,
                    latitude=lat,
                    baro_altitude=alt_ft / 3.28084,
                    on_ground=False,
                    velocity=spd_kts / 1.94384,
                    true_track=float(hdg),
                    vertical_rate=0.0,
                    geo_altitude=alt_ft / 3.28084,
                    position_source=0,
                    category=4,
                )
            )
        return synthetic


opensky_service = OpenSkyService()
