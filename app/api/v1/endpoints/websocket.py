import asyncio
import json
from typing import List, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ....core.config import settings
from ....core.logging import logger
from ....schemas.aircraft import AircraftListResponse
from ....services.flight_enricher import enrich_state_vector
from ....services.opensky_service import opensky_service

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
async def websocket_live_aircraft(websocket: WebSocket):
    """
    WebSocket endpoint streaming live flight updates every 10 seconds.
    Clients can send JSON commands to filter bounding boxes e.g.:
    {"lamin": 25.0, "lomin": 45.0, "lamax": 38.0, "lomax": 60.0}
    """
    await manager.connect(websocket)
    
    # Default filters
    bbox = {
        "lamin": settings.DEFAULT_LAMIN,
        "lomin": settings.DEFAULT_LOMIN,
        "lamax": settings.DEFAULT_LAMAX,
        "lomax": settings.DEFAULT_LOMAX,
    }

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
                        logger.info(f"WebSocket bbox updated by client: {bbox}")
                except Exception:
                    pass
        except WebSocketDisconnect:
            pass

    async def stream_live_data():
        while True:
            try:
                state_vectors, timestamp, is_cached = await opensky_service.get_states(
                    lamin=bbox.get("lamin"),
                    lomin=bbox.get("lomin"),
                    lamax=bbox.get("lamax"),
                    lomax=bbox.get("lomax"),
                )
                
                aircraft_list = [
                    enrich_state_vector(sv) for sv in state_vectors
                ]
                valid_aircraft = [ac for ac in aircraft_list if ac is not None]

                payload = AircraftListResponse(
                    total=len(valid_aircraft),
                    count=len(valid_aircraft),
                    time=timestamp,
                    aircraft=valid_aircraft,
                    cached=is_cached,
                )

                await websocket.send_text(payload.model_dump_json())
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket stream error: {e}")
                break

            await asyncio.sleep(settings.CACHE_TTL_SECONDS)

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
