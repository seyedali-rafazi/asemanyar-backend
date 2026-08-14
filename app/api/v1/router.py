from fastapi import APIRouter

from .endpoints.aircraft import router as aircraft_router
from .endpoints.airports import router as airports_router
from .endpoints.antennas import router as antennas_router
from .endpoints.flights import router as flights_router
from .endpoints.states import router as states_router
from .endpoints.stats import router as stats_router
from .endpoints.tracks import router as tracks_router
from .endpoints.websocket import router as websocket_router

api_v1_router = APIRouter()

api_v1_router.include_router(aircraft_router)
api_v1_router.include_router(states_router)
api_v1_router.include_router(flights_router)
api_v1_router.include_router(tracks_router)
api_v1_router.include_router(airports_router)
api_v1_router.include_router(antennas_router)
api_v1_router.include_router(stats_router)
api_v1_router.include_router(websocket_router)
