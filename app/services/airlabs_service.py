import asyncio
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from ..core.config import settings
from ..core.logging import logger
from ..schemas.airlabs import AirLabsFlight, AirLabsFlightsResponse


class AirLabsService:
    """
    Asynchronous AirLabs API Client (https://airlabs.co/docs/flights).
    Used exclusively by the background sync worker to fetch global flight snapshots
    at scheduled intervals (e.g. every 2 hours, max 10 requests / 24h).
    """

    def __init__(self):
        self.base_url = settings.AIRLABS_BASE_URL.rstrip("/")
        self.timeout = httpx.Timeout(
            timeout=settings.AIRLABS_REQUEST_TIMEOUT,
            connect=settings.AIRLABS_CONNECT_TIMEOUT,
        )
        self.limits = httpx.Limits(
            max_keepalive_connections=5,
            max_connections=10,
            keepalive_expiry=60.0,
        )
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            client_kwargs: Dict[str, Any] = {
                "timeout": self.timeout,
                "limits": self.limits,
                "headers": {"User-Agent": "Asemanha-Flight-Tracker/2.0"},
                "trust_env": settings.USE_SYSTEM_PROXY,
            }
            if settings.PROXY_URL:
                client_kwargs["proxy"] = settings.PROXY_URL

            self._client = httpx.AsyncClient(**client_kwargs)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

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

    async def fetch_global_flights(self) -> Tuple[List[AirLabsFlight], int, bool, str]:
        """
        Executes a single global request to AirLabs for worldwide flight states.
        Called strictly by the scheduled background sync worker.
        Returns: (flights, timestamp, is_success, status_message)
        """
        api_key = settings.AIRLABS_API_KEY
        if not api_key:
            logger.warning("AIRLABS_API_KEY is not configured in environment.")
            return [], int(time.time()), False, "API key not configured"

        params: Dict[str, Any] = {
            "api_key": api_key,
        }

        # If not fetching worldwide and default bounds configured:
        if not settings.AIRLABS_FETCH_GLOBAL:
            if (
                settings.DEFAULT_LAMIN is not None
                and settings.DEFAULT_LOMIN is not None
                and settings.DEFAULT_LAMAX is not None
                and settings.DEFAULT_LOMAX is not None
            ):
                params["bbox"] = (
                    f"{settings.DEFAULT_LAMIN},{settings.DEFAULT_LOMIN},"
                    f"{settings.DEFAULT_LAMAX},{settings.DEFAULT_LOMAX}"
                )

        client = await self.get_client()
        url = f"{self.base_url}/flights"
        logger.info(f"Initiating scheduled global flight sync from AirLabs: {url}")

        for attempt in range(1, 3):
            try:
                resp = await client.get(url, params=params)
                ts = int(time.time())

                if resp.status_code == 200:
                    data = resp.json()
                    raw_flights = data.get("response") or []
                    flights: List[AirLabsFlight] = []

                    for item in raw_flights:
                        if isinstance(item, dict) and "hex" in item:
                            try:
                                flights.append(AirLabsFlight(**item))
                            except Exception:
                                continue

                    logger.info(f"AirLabs API returned {len(flights)} worldwide active flights.")
                    return flights, ts, True, f"OK ({len(flights)} flights fetched)"

                elif resp.status_code == 401:
                    msg = "AirLabs API HTTP 401 Unauthorized (Invalid API key)"
                    logger.error(msg)
                    return [], ts, False, msg

                elif resp.status_code == 429:
                    msg = "AirLabs API HTTP 429 Rate Limit Reached"
                    logger.warning(msg)
                    return [], ts, False, msg

                else:
                    msg = f"AirLabs API HTTP {resp.status_code}: {resp.text[:150]}"
                    logger.warning(msg)
                    return [], ts, False, msg

            except Exception as e:
                err_msg = self._format_error(e)
                logger.warning(f"AirLabs API attempt {attempt} failed: {err_msg}")
                if attempt < 2:
                    await asyncio.sleep(2.0)
                else:
                    return [], int(time.time()), False, f"Connection failed: {err_msg}"

        return [], int(time.time()), False, "Max attempts reached"

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
        Helper method querying cached raw flight vectors from FleetCacheManager.
        Preserved for backward compatibility.
        """
        from .fleet_cache_manager import fleet_cache_manager

        flights = fleet_cache_manager.get_raw_flights(
            lamin=lamin,
            lomin=lomin,
            lamax=lamax,
            lomax=lomax,
            hex=hex,
            airline_icao=airline_icao,
            flight_icao=flight_icao,
        )
        return flights, fleet_cache_manager.last_sync_time or int(time.time()), True


# Global singleton instance
airlabs_service = AirLabsService()
