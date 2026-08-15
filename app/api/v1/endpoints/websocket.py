import asyncio
import json
import time
from typing import List, Optional, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ....core.config import settings
from ....core.logging import logger
from ....schemas.aircraft import Aircraft, AircraftListResponse
from ....services.fleet_cache_manager import fleet_cache_manager

router = APIRouter(prefix="/ws", tags=["WebSocket"])


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()


@router.websocket("/live")
async def websocket_live_aircraft(
    websocket: WebSocket,
    lamin: Optional[float] = None,
    lomin: Optional[float] = None,
    lamax: Optional[float] = None,
    lomax: Optional[float] = None,
    zoom: Optional[float] = None,
):
    """
    WebSocket endpoint streaming live flight updates from the persistent in-memory global cache.
    Clients can supply initial bounding box query parameters or send JSON commands
    e.g. {"lamin": 25.0, "lomin": 45.0, "lamax": 38.0, "lomax": 60.0} to update filters.
    All data is served from memory with zero external API calls.
    """
    await manager.connect(websocket)

    bbox = {
        "lamin": lamin if lamin is not None else settings.DEFAULT_LAMIN,
        "lomin": lomin if lomin is not None else settings.DEFAULT_LOMIN,
        "lamax": lamax if lamax is not None else settings.DEFAULT_LAMAX,
        "lomax": lomax if lomax is not None else settings.DEFAULT_LOMAX,
        "zoom": zoom,
    }

    bbox_updated_event = asyncio.Event()

    async def listen_for_client_messages():
        nonlocal bbox
        try:
            while True:
                msg = await websocket.receive_text()
                try:
                    data = json.loads(msg)
                    if isinstance(data, dict):
                        if "lamin" in data:
                            bbox["lamin"] = float(data["lamin"]) if data["lamin"] is not None else None
                        if "lomin" in data:
                            bbox["lomin"] = float(data["lomin"]) if data["lomin"] is not None else None
                        if "lamax" in data:
                            bbox["lamax"] = float(data["lamax"]) if data["lamax"] is not None else None
                        if "lomax" in data:
                            bbox["lomax"] = float(data["lomax"]) if data["lomax"] is not None else None
                        if "zoom" in data:
                            bbox["zoom"] = float(data["zoom"]) if data["zoom"] is not None else None
                        bbox_updated_event.set()
                except Exception:
                    pass
        except WebSocketDisconnect:
            pass

    async def stream_live_data():
        while True:
            try:
                valid_aircraft = fleet_cache_manager.get_aircraft(
                    lamin=bbox.get("lamin"),
                    lomin=bbox.get("lomin"),
                    lamax=bbox.get("lamax"),
                    lomax=bbox.get("lomax"),
                )

                payload = AircraftListResponse(
                    total=len(valid_aircraft),
                    count=len(valid_aircraft),
                    time=fleet_cache_manager.last_sync_time or int(time.time()),
                    aircraft=valid_aircraft,
                    cached=True,
                )

                await websocket.send_text(payload.model_dump_json())
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket stream error: {e}")
                break

            bbox_updated_event.clear()
            try:
                # Stream updates every 10 seconds or immediately when client moves bbox
                await asyncio.wait_for(bbox_updated_event.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                pass

    listener_task = asyncio.create_task(listen_for_client_messages())
    streamer_task = asyncio.create_task(stream_live_data())

    try:
        done, pending = await asyncio.wait(
            [listener_task, streamer_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
    finally:
        manager.disconnect(websocket)
