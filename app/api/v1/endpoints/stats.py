import time
from typing import Optional
from fastapi import APIRouter, Query

from ....core.config import settings
from ....schemas.aircraft import FleetStats
from ....services.flight_enricher import enrich_state_vector
from ....services.opensky_service import opensky_service

router = APIRouter(prefix="/stats", tags=["Stats"])


@router.get("", response_model=FleetStats)
async def get_fleet_stats(
    lamin: Optional[float] = Query(default=settings.DEFAULT_LAMIN, description="Lower latitude bound"),
    lomin: Optional[float] = Query(default=settings.DEFAULT_LOMIN, description="Lower longitude bound"),
    lamax: Optional[float] = Query(default=settings.DEFAULT_LAMAX, description="Upper latitude bound"),
    lomax: Optional[float] = Query(default=settings.DEFAULT_LOMAX, description="Upper longitude bound"),
):
    """
    Computes summary telemetry and metrics for the active fleet.
    """
    state_vectors, timestamp, _ = await opensky_service.get_states(
        lamin=lamin,
        lomin=lomin,
        lamax=lamax,
        lomax=lomax,
    )

    enriched = [enrich_state_vector(sv) for sv in state_vectors]
    valid = [ac for ac in enriched if ac is not None]

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
        timestamp=timestamp or int(time.time()),
    )
