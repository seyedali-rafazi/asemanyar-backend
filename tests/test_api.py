import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.airlabs import AirLabsFlight
from app.services.flight_enricher import (
    enrich_airlabs_flight,
    enrich_airlabs_flight_detail,
    identify_airline,
)
from app.services.fleet_cache_manager import fleet_cache_manager


@pytest.mark.asyncio
async def test_root_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert data["provider"] == "airlabs"
        assert "endpoints" in data


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["provider"] == "airlabs"
        assert "total_cached_aircraft" in data
        assert "daily_requests_limit" in data
        assert data["daily_requests_limit"] == 10
        assert "sync_interval_hours" in data


@pytest.mark.asyncio
async def test_cache_status_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/aircraft/cache/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "total_cached_aircraft" in data
        assert "sync_interval_seconds" in data
        assert data["sync_interval_seconds"] == 7200
        assert data["daily_requests_limit"] == 10


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
        assert data["cached"] is True


@pytest.mark.asyncio
async def test_aircraft_bbox_query():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/aircraft?lamin=24.0&lomin=44.0&lamax=40.0&lomax=64.0")
        assert response.status_code == 200
        data = response.json()
        assert "aircraft" in data
        assert len(data["aircraft"]) > 0
        assert data["total"] > 0
        assert data["count"] > 0


@pytest.mark.asyncio
async def test_aircraft_detail_and_track():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        list_resp = await client.get("/api/v1/aircraft")
        assert list_resp.status_code == 200
        aircraft_list = list_resp.json()["aircraft"]
        assert len(aircraft_list) > 0
        test_id = aircraft_list[0]["id"]

        detail_resp = await client.get(f"/api/v1/aircraft/{test_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["id"] == test_id

        track_resp = await client.get(f"/api/v1/aircraft/{test_id}/track")
        assert track_resp.status_code == 200
        track = track_resp.json()
        assert track["id"] == test_id.upper()


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
async def test_raw_states_and_flights():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        states_resp = await client.get("/api/v1/states/all")
        assert states_resp.status_code == 200

        flights_resp = await client.get("/api/v1/flights/all")
        assert flights_resp.status_code == 200


@pytest.mark.asyncio
async def test_airports_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/airports")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] > 0
        assert len(data["airports"]) > 0

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
    assert identify_airline("KAC536") == "Kuwait Airways"
    assert identify_airline(None, "Iran") == "Iran"
    assert identify_airline(None, None) == "General Aviation"


def test_enrich_airlabs_flight():
    flight = AirLabsFlight(
        hex="706069",
        reg_number="9K-AKP",
        flag="KW",
        lat=29.030092,
        lng=48.011628,
        alt=939,
        dir=17.5,
        speed=466,
        v_speed=-19,
        flight_number="536",
        flight_icao="KAC536",
        flight_iata="KU536",
        dep_icao="HESX",
        dep_iata="SPX",
        arr_icao="OKKK",
        arr_iata="KWI",
        airline_icao="KAC",
        airline_iata="KU",
        aircraft_icao="A20N",
        updated=1700000000,
        status="en-route",
        type="adsb",
    )
    aircraft = enrich_airlabs_flight(flight)
    assert aircraft is not None
    assert aircraft.id == "706069"
    assert aircraft.callsign == "KAC536"
    assert aircraft.airline == "Kuwait Airways"
    assert aircraft.reg_number == "9K-AKP"
    assert aircraft.aircraftType == "Airbus A320neo"
    assert "Kuwait" in aircraft.destination_city
    assert aircraft.speed_kts == int(round(466 * 0.539957))
    assert aircraft.altitude_ft == int(round(939 * 3.28084))
    assert len(aircraft.path) > 0


def test_quota_manager():
    # Verify quota tracker works correctly
    can_call, _ = fleet_cache_manager.can_make_api_call()
    assert can_call is True
