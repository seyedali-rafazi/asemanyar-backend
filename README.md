# Asemanha Backend - OpenSky Flight Tracking API

High-performance, async **FastAPI** backend that fetches, enriches, caches, and serves live aircraft telemetry and airspace data directly from the **OpenSky Network REST API**, without requiring a database.

---

## Features

- ✈️ **Live OpenSky Data Integration**: Fetches real-time ADS-B transponder state vectors, tracks, and airport departures/arrivals.
- ⚡ **Zero Database Required**: Pure high-speed in-memory TTL caching and streaming.
- 🛡️ **Rate-Limit & Offline Guard**: Automatically protects against OpenSky 429 rate-limiting with graceful cache fallbacks.
- 🎯 **Domain-Enriched Telemetry**: Automatically translates raw state vectors into UI-ready models (`Aircraft`, `AircraftDetail`, airline name detection, altitude ft / speed kts conversions, routes, and waypoints).
- 🌐 **Interactive Documentation**: Built-in interactive Swagger UI (`/docs`) and ReDoc (`/redoc`).
- 🔄 **WebSocket Real-time Streaming**: Live WebSocket endpoint (`/api/v1/ws/live`) pushing periodic updates to connected clients.
- 📍 **Airspace Filtering**: Full support for bounding box coordinates (`lamin`, `lomin`, `lamax`, `lomax`), ICAO24 transponder addresses, airlines, and altitude ranges.

---

## Quick Start

### 1. Requirements

- Python 3.10+ (tested with Python 3.14)
- Pip

### 2. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Configure Environment (Optional)

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

If you have an OpenSky Network account, enter your credentials in `.env` to unlock higher rate limits (5s updates vs 10s anonymous):

```env
OPENSKY_USERNAME=your_username
OPENSKY_PASSWORD=your_password
```

### 4. Run the Server

Using the runner script:
```bash
python backend/run.py
```

Or directly via Uvicorn:
```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at: **http://localhost:8000**  
Interactive API Docs (Swagger): **http://localhost:8000/docs**  
ReDoc API Docs: **http://localhost:8000/redoc**  

---

## API Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Root information and available endpoint routes |
| `GET` | `/health` | Health check & cache status |
| `GET` | `/api/v1/aircraft` | List enriched live aircraft with filters (bbox, search, airline, altitude) |
| `GET` | `/api/v1/aircraft/{id}` | Detailed telemetry and sensors for a single aircraft |
| `GET` | `/api/v1/aircraft/{id}/track` | Trajectory waypoints for a specific aircraft |
| `GET` | `/api/v1/states/all` | Direct OpenSky state vector representations |
| `GET` | `/api/v1/flights/interval` | Flights active within a time window |
| `GET` | `/api/v1/flights/aircraft/{icao24}` | Flight history for a specific aircraft |
| `GET` | `/api/v1/flights/departures/{airport_icao}` | Departures for an airport (e.g. `OIII`, `OIIE`, `OIMM`) |
| `GET` | `/api/v1/flights/arrivals/{airport_icao}` | Arrivals for an airport |
| `GET` | `/api/v1/airports` | Major airport reference database |
| `GET` | `/api/v1/antennas` | Ground radar & ADS-B receiver database |
| `GET` | `/api/v1/stats` | Active airspace metrics (total aircraft, airborne, airlines count) |
| `WS`  | `/api/v1/ws/live` | WebSocket real-time live aircraft streaming |

---

## 📮 Postman Collection

A complete Postman collection is included at:
**[`asemanha_postman_collection.json`](file:///d:/web%20project/asemenaha/ase/backend/asemanha_postman_collection.json)**

### How to Import:
1. Open **Postman**.
2. Click **Import** (top left).
3. Select or drag-and-drop `backend/asemanha_postman_collection.json`.
4. The collection is preconfigured with collection variables (`baseUrl = http://localhost:8000`, `apiPrefix = /api/v1`).


---

## Running Tests

Run the test suite with `pytest`:

```bash
pytest backend/tests -v
```
