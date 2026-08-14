import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.opensky import OpenSkyStateVector
from app.services.flight_enricher import (
    enrich_state_vector,
    enrich_state_vector_detail,
    identify_airline,
)


@pytest.mark.asyncio
async def test_root_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert "endpoints" in data


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_list_aircraft():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/aircraft")
        assert response.status_code == 200
        data = response.json()
        assert "aircraft" in data
        assert "total" in data
        assert isinstance(data["aircraft"], list)


@pytest.mark.asyncio
async def test_fleet_stats():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_aircraft" in data
        assert "airborne" in data
        assert "avg_altitude_ft" in data


@pytest.mark.asyncio
async def test_airports_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/airports")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] > 0
        assert len(data["airports"]) > 0

        # Test single airport lookup
        single_resp = await client.get("/api/v1/airports/OIII")
        assert single_resp.status_code == 200
        airport_data = single_resp.json()
        assert airport_data["icao"] == "OIII"
        assert airport_data["iata"] == "THR"


@pytest.mark.asyncio
async def test_antennas_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/antennas")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] > 0


def test_airline_identifier():
    assert identify_airline("IRA123") == "Iran Air"
    assert identify_airline("IRC456") == "Aseman Airlines"
    assert identify_airline("TBZ789") == "ATA Airlines"
    assert identify_airline("THY100") == "Turkish Airlines"
    assert identify_airline("UAE400") == "Emirates"
    assert identify_airline(None, "Iran") == "Iran"
    assert identify_airline(None, None) == "General Aviation"


def test_enrich_state_vector():
    sv = OpenSkyStateVector(
        icao24="738045",
        callsign="IRA450",
        origin_country="Iran",
        time_position=1700000000,
        last_contact=1700000000,
        longitude=51.3890,
        latitude=35.6892,
        baro_altitude=10000.0,  # meters (~32808 ft)
        on_ground=False,
        velocity=230.0,  # m/s (~447 kts)
        true_track=180.0,
        vertical_rate=5.0,
        sensors=[1, 2],
        geo_altitude=10100.0,
        squawk="4321",
        spi=False,
        position_source=0,
        category=4,
    )
    aircraft = enrich_state_vector(sv)
    assert aircraft is not None
    assert aircraft.id == "738045"
    assert aircraft.callsign == "IRA450"
    assert aircraft.airline == "Iran Air"
    assert aircraft.altitude_ft == 32808
    assert aircraft.speed_kts == 447
    assert aircraft.heading_deg == 180
    assert len(aircraft.path) > 0
