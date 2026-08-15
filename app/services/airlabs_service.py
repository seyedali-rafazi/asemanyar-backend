import asyncio
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from ..core.config import settings
from ..core.logging import logger
from ..schemas.airlabs import AirLabsFlight, AirLabsFlightsResponse
from ..schemas.aircraft import AircraftTrackResponse, TrackWaypoint
from .cache_service import cache_service


class AirLabsService:
    """
    Asynchronous AirLabs Live Flights API Client (https://airlabs.co/docs/flights)
    with connection pooling, in-memory TTL caching, and fallback protection.
    """

    def __init__(self):
        self.base_url = settings.AIRLABS_BASE_URL.rstrip("/")
        self.timeout = httpx.Timeout(
            timeout=settings.AIRLABS_REQUEST_TIMEOUT,
            connect=settings.AIRLABS_CONNECT_TIMEOUT,
        )
        self.limits = httpx.Limits(
            max_keepalive_connections=10,
            max_connections=20,
            keepalive_expiry=120.0,
        )
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            client_kwargs: Dict[str, Any] = {
                "timeout": self.timeout,
                "limits": self.limits,
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

    def _build_cache_key(self, prefix: str, params: Dict[str, Any]) -> str:
        param_str = "_".join(f"{k}:{v}" for k, v in sorted(params.items()) if v is not None and k != "api_key")
        return f"{prefix}_{param_str}"

    def _format_error(self, e: Exception) -> str:
        err_type = type(e).__name__
        msg = str(e).strip()
        if not msg:
            if isinstance(e, httpx.ConnectTimeout):
                return f"{err_type}: Connection to AirLabs timed out (connect: {settings.AIRLABS_CONNECT_TIMEOUT}s)."
            elif isinstance(e, httpx.ReadTimeout):
                return f"{err_type}: Read timed out waiting for AirLabs response (request: {settings.AIRLABS_REQUEST_TIMEOUT}s)."
            elif isinstance(e, httpx.ConnectError):
                return f"{err_type}: Failed to connect to AirLabs. Check network connectivity."
            return f"{err_type}: Network error or host unreachable"
        return f"{err_type}: {msg}"

    async def get_flights(
        self,
        lamin: Optional[float] = None,
        lomin: Optional[float] = None,
        lamax: Optional[float] = None,
        lomax: Optional[float] = None,
        hex: Optional[str] = None,
        airline_icao: Optional[str] = None,
        flight_icao: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Tuple[List[AirLabsFlight], int, bool]:
        """
        Fetches live flight states from AirLabs API matching filters/bounding box.
        Returns (flights_list, timestamp, is_cached).
        """
        api_key = settings.AIRLABS_API_KEY
        if not api_key:
            logger.warning("AIRLABS_API_KEY is not configured in environment.")

        params: Dict[str, Any] = {
            "api_key": api_key,
        }

        # Bounding box format: South-West Lat, South-West Long, North-East Lat, North-East Long
        if lamin is not None and lomin is not None and lamax is not None and lomax is not None:
            params["bbox"] = f"{lamin},{lomin},{lamax},{lomax}"

        if hex is not None:
            params["hex"] = hex.lower()
        if airline_icao is not None:
            params["airline_icao"] = airline_icao.upper()
        if flight_icao is not None:
            params["flight_icao"] = flight_icao.upper()

        cache_key = self._build_cache_key("airlabs_flights", params)

        if not force_refresh:
            cached_data = cache_service.get(cache_key)
            if cached_data:
                flights, ts = cached_data
                return flights, ts, True

        # Fetch from AirLabs API
        client = await self.get_client()
        url = f"{self.base_url}/flights"

        for attempt in range(1, 3):
            try:
                logger.info(f"Fetching live flights from AirLabs API (attempt {attempt}/2): {params.get('bbox', hex or 'all')}")
                resp = await client.get(url, params=params)

                if resp.status_code == 200:
                    data = resp.json()
                    raw_flights = data.get("response") or []
                    ts = int(time.time())

                    flights: List[AirLabsFlight] = []
                    for item in raw_flights:
                        if isinstance(item, dict) and "hex" in item:
                            try:
                                flights.append(AirLabsFlight(**item))
                            except Exception as parse_err:
                                logger.debug(f"Failed to parse AirLabs flight item: {parse_err}")

                    cache_service.set(cache_key, (flights, ts), ttl=settings.CACHE_TTL_SECONDS)
                    logger.info(f"Retrieved {len(flights)} live flights from AirLabs API.")
                    return flights, ts, False

                elif resp.status_code == 401:
                    logger.error(f"AirLabs API returned HTTP 401 Unauthorized. Verify AIRLABS_API_KEY.")
                    break
                elif resp.status_code == 429:
                    logger.warning("AirLabs API rate limit reached (HTTP 429). Utilizing cached fallback.")
                    break
                else:
                    logger.warning(f"AirLabs API returned HTTP {resp.status_code}: {resp.text[:200]}")
                    break

            except Exception as e:
                logger.warning(f"AirLabs API attempt {attempt} error: {self._format_error(e)}")
                if attempt < 2:
                    await asyncio.sleep(1.0)
                else:
                    logger.error(f"Error connecting to AirLabs API after 2 attempts: {self._format_error(e)}")

        # 1. Fallback to stale cache if available
        fallback = cache_service.get_fallback(cache_key)
        if fallback:
            flights, ts = fallback
            if flights and len(flights) > 0:
                logger.info(f"Returning stale AirLabs cache with {len(flights)} flights.")
                return flights, ts, True

        return [], int(time.time()), False


# Global singleton instance
airlabs_service = AirLabsService()
