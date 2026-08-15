import asyncio
import time
from typing import Optional

from ..core.config import settings
from ..core.logging import logger
from .airlabs_service import airlabs_service
from .fleet_cache_manager import fleet_cache_manager


class SyncWorker:
    """
    Background worker that runs a periodic sync loop every 2 hours
    (configurable via AIRLABS_SYNC_INTERVAL_SECONDS) to fetch global aircraft
    and update the persistent in-memory cache without exhausting free API quotas.
    """

    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._is_running: bool = False
        self._force_sync_event: asyncio.Event = asyncio.Event()

    async def _execute_sync(self) -> bool:
        """
        Executes a single sync cycle with quota enforcement and error handling.
        """
        can_call, quota_msg = fleet_cache_manager.can_make_api_call()
        if not can_call:
            logger.warning(f"Skipping scheduled AirLabs sync: {quota_msg}")
            fleet_cache_manager.last_sync_status = "quota_limit_reached"
            fleet_cache_manager.last_sync_message = quota_msg
            return False

        logger.info(f"Starting scheduled 2-hour AirLabs global sync. {quota_msg}")
        fleet_cache_manager.record_api_call()

        flights, ts, success, msg = await airlabs_service.fetch_global_flights()

        if success and flights:
            fleet_cache_manager.update_fleet(
                raw_flights=flights,
                timestamp=ts,
                status="success",
                message=f"Synced {len(flights)} aircraft at {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(ts))} UTC",
            )
            logger.info(f"Scheduled AirLabs sync completed successfully ({len(flights)} flights).")
            return True
        else:
            logger.warning(f"Scheduled AirLabs sync did not retrieve fresh flights: {msg}")
            # Ensure fallback data is loaded so users always see flights
            fleet_cache_manager.ensure_data_loaded()
            fleet_cache_manager.last_sync_status = "sync_failed_using_cached"
            fleet_cache_manager.last_sync_message = f"Last sync failed ({msg}); serving cached/fallback fleet"
            return False

    async def _run_loop(self):
        """Main background loop."""
        self._is_running = True
        logger.info(
            f"AirLabs SyncWorker started. Interval: {settings.AIRLABS_SYNC_INTERVAL_SECONDS}s "
            f"({round(settings.AIRLABS_SYNC_INTERVAL_SECONDS / 3600.0, 1)}h), Max daily requests: {settings.AIRLABS_MAX_DAILY_REQUESTS}"
        )

        # 1. Check disk cache on startup
        disk_loaded = fleet_cache_manager.load_disk_cache()
        now = time.time()
        sync_needed = True

        if disk_loaded and fleet_cache_manager.last_sync_time > 0:
            cache_age = now - fleet_cache_manager.last_sync_time
            if cache_age < settings.AIRLABS_SYNC_INTERVAL_SECONDS:
                remaining_sec = int(settings.AIRLABS_SYNC_INTERVAL_SECONDS - cache_age)
                logger.info(
                    f"Startup: Disk cache is fresh ({int(cache_age // 60)}m old). "
                    f"Next scheduled sync in {int(remaining_sec // 60)}m ({remaining_sec}s)."
                )
                fleet_cache_manager.next_sync_time = int(now + remaining_sec)
                sync_needed = False
                try:
                    # Wait remaining time or until manual trigger
                    await asyncio.wait_for(
                        self._force_sync_event.wait(),
                        timeout=remaining_sec,
                    )
                    self._force_sync_event.clear()
                    sync_needed = True
                except asyncio.TimeoutError:
                    sync_needed = True

        # 2. Perform initial sync if needed
        if sync_needed and settings.AIRLABS_AUTO_SYNC_ENABLED:
            await self._execute_sync()

        # 3. Continuous sync loop
        while self._is_running:
            fleet_cache_manager.next_sync_time = int(time.time() + settings.AIRLABS_SYNC_INTERVAL_SECONDS)
            try:
                # Wait for interval or manual trigger event
                await asyncio.wait_for(
                    self._force_sync_event.wait(),
                    timeout=float(settings.AIRLABS_SYNC_INTERVAL_SECONDS),
                )
                self._force_sync_event.clear()
                logger.info("Manual sync trigger received.")
            except asyncio.TimeoutError:
                pass

            if not self._is_running:
                break

            if settings.AIRLABS_AUTO_SYNC_ENABLED:
                await self._execute_sync()

    def start(self) -> None:
        """Starts the sync worker task."""
        if self._task is None or self._task.done():
            self._force_sync_event.clear()
            self._task = asyncio.create_task(self._run_loop())
            logger.info("AirLabs background SyncWorker task spawned.")

    def trigger_sync(self) -> None:
        """Wakes up the worker to run an immediate sync."""
        self._force_sync_event.set()

    async def stop(self) -> None:
        """Gracefully stops the sync worker task."""
        self._is_running = False
        if self._task and not self._task.done():
            self._force_sync_event.set()
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("AirLabs background SyncWorker task stopped.")


# Global singleton instance
sync_worker = SyncWorker()
