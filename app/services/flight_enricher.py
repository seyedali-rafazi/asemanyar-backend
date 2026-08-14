import datetime
import math
import re
from typing import Any, Dict, List, Optional, Tuple

from ..schemas.aircraft import Aircraft, AircraftDetail
from ..schemas.opensky import OpenSkyStateVector

# Mapping of ICAO 3-letter / IATA 2-letter airline callsign prefixes to full Airline Names
AIRLINE_PREFIX_MAP: Dict[str, str] = {
    # Iranian Airlines
    "IRA": "Iran Air",
    "IR": "Iran Air",
    "IRC": "Aseman Airlines",
    "EP": "Aseman Airlines",
    "MAH": "Mahan Air",
    "W5": "Mahan Air",
    "TBZ": "ATA Airlines",
    "I3": "ATA Airlines",
    "VRH": "Varesh Airlines",
    "VR": "Varesh Airlines",
    "QSM": "Qeshm Air",
    "QB": "Qeshm Air",
    "CAS": "Caspian Airlines",
    "IV": "Caspian Airlines",
    "KIS": "Kish Air",
    "Y9": "Kish Air",
    "TAG": "Tajik Air",
    "CPN": "Caspian Airlines",
    "IZG": "Zagros Airlines",
    "ZV": "Zagros Airlines",
    "SHI": "Iran Airtour",
    "B9": "Iran Airtour",
    "TBX": "Taban Air",
    "HH": "Taban Air",
    "MRJ": "Meraj Airlines",
    "JI": "Meraj Airlines",
    "SEB": "Sepehran Airlines",
    "IS": "Sepehran Airlines",
    "CPT": "Karun Airlines",
    "NV": "Karun Airlines",
    "PYA": "Pouya Air",
    "SAH": "Saha Air",
    "CHB": "Chabahar Airlines",
    "FL": "FlyPersia",
    "FPI": "FlyPersia",
    "YAZ": "Yazd Airways",
    "AVA": "Ava Air",

    # Regional & International Airlines
    "THY": "Turkish Airlines",
    "TK": "Turkish Airlines",
    "UAE": "Emirates",
    "EK": "Emirates",
    "QTR": "Qatar Airways",
    "QR": "Qatar Airways",
    "FDB": "flydubai",
    "FZ": "flydubai",
    "ABY": "Air Arabia",
    "GFA": "Gulf Air",
    "KAC": "Kuwait Airways",
    "OAS": "Oman Air",
    "RJA": "Royal Jordanian",
    "MEA": "Middle East Airlines",
    "IRAQ": "Iraqi Airways",
    "IAW": "Iraqi Airways",
    "PIA": "Pakistan International Airlines",
    "AIC": "Air India",
    "AFL": "Aeroflot",
    "SU": "Aeroflot",
    "DLH": "Lufthansa",
    "LH": "Lufthansa",
    "AFR": "Air France",
    "AF": "Air France",
    "BAW": "British Airways",
    "BA": "British Airways",
    "KLM": "KLM Royal Dutch Airlines",
    "KL": "KLM Royal Dutch Airlines",
    "AZA": "ITA Airways",
    "AUA": "Austrian Airlines",
    "SWR": "Swiss International Air Lines",
    "CSN": "China Southern Airlines",
    "CCA": "Air China",
    "CES": "China Eastern Airlines",
    "ETD": "Etihad Airways",
    "EY": "Etihad Airways",
    "SVA": "Saudia",
    "SV": "Saudia",
}

# Aircraft Category description mapping (OpenSky Category integer)
CATEGORY_MAP: Dict[int, str] = {
    0: "No Information",
    1: "No ADS-B Emitter Category Information",
    2: "Light (< 15,500 lbs)",
    3: "Small (15,500 to 75,000 lbs)",
    4: "Large (75,000 to 300,000 lbs)",
    5: "High Vortex Large (e.g. B757)",
    6: "Heavy (> 300,000 lbs)",
    7: "High Performance (> 5g & > 400 kts)",
    8: "Rotorcraft",
    9: "Glider / Sailplane",
    10: "Lighter-than-air",
    11: "Parachutist / Skydiver",
    12: "Ultralight / Hang-glider / Paraglider",
    13: "Reserved",
    14: "Unmanned Aerial Vehicle",
    15: "Space / Trans-atmospheric vehicle",
}

# Default Iranian & regional city hubs for heuristic origin/dest assignment
IRAN_HUBS = [
    ("Tehran", (35.6892, 51.3134)),
    ("Mashhad", (36.2352, 59.6410)),
    ("Shiraz", (29.5392, 52.5898)),
    ("Isfahan", (32.7508, 51.8614)),
    ("Tabriz", (38.1339, 46.2350)),
    ("Bandar Abbas", (27.2183, 56.3778)),
    ("Kish", (26.5262, 53.9803)),
    ("Ahvaz", (31.3374, 48.7620)),
    ("Kerman", (30.2744, 56.9511)),
    ("Zahedan", (29.4757, 60.9062)),
    ("Rasht", (37.3233, 49.6178)),
    ("Yazd", (31.9049, 54.2765)),
    ("Istanbul", (41.2753, 28.7519)),
    ("Dubai", (25.2532, 55.3657)),
    ("Doha", (25.2731, 51.6081)),
]


def identify_airline(callsign: Optional[str], country: Optional[str] = None) -> str:
    """Infers airline name from callsign prefix or country of origin."""
    if not callsign:
        return country or "General Aviation"

    clean_callsign = callsign.strip().upper()
    
    # Try 3-letter prefix
    prefix3 = clean_callsign[:3]
    if prefix3 in AIRLINE_PREFIX_MAP:
        return AIRLINE_PREFIX_MAP[prefix3]

    # Try 2-letter prefix
    prefix2 = clean_callsign[:2]
    if prefix2 in AIRLINE_PREFIX_MAP:
        return AIRLINE_PREFIX_MAP[prefix2]

    # Check matches in callsign
    for prefix, name in AIRLINE_PREFIX_MAP.items():
        if clean_callsign.startswith(prefix):
            return name

    if country and country != "Unknown":
        return f"{country} Carrier"

    return "Commercial Flight"


def estimate_aircraft_type(
    category: Optional[int],
    callsign: Optional[str],
    altitude_m: Optional[float],
    speed_ms: Optional[float]
) -> str:
    """Estimates typical aircraft type based on category, altitude, and speed."""
    alt_ft = (altitude_m or 0) * 3.28084
    speed_kts = (speed_ms or 0) * 1.94384

    if category == 8:
        return "Bell 412 / Rotorcraft"
    if category == 2:
        return "Cessna 172"
    if category == 3:
        return "ATR 72-600"
    if category == 6 or alt_ft > 38000:
        return "A350-900 / B777"
    if category == 5:
        return "B757-200"

    # Common commercial aircraft defaults
    if alt_ft > 28000:
        if speed_kts > 450:
            return "A330-300"
        return "A320-200"
    elif alt_ft > 15000:
        return "B737-800"
    elif alt_ft > 5000:
        return "Fokker 100"
    else:
        return "MD-82"


def estimate_route(
    lat: float,
    lon: float,
    heading_deg: int,
    callsign: Optional[str] = None
) -> Tuple[str, str]:
    """Estimates plausible origin and destination cities based on location & heading."""
    # Find nearest hub
    def dist(h_lat: float, h_lon: float) -> float:
        return math.hypot(h_lat - lat, h_lon - lon)

    sorted_hubs = sorted(IRAN_HUBS, key=lambda h: dist(h[1][0], h[1][1]))
    nearest_hub = sorted_hubs[0][0]

    # Choose destination based on heading vector
    # Heading: 0 = North, 90 = East, 180 = South, 270 = West
    rad = math.radians(heading_deg)
    d_lat = math.cos(rad)
    d_lon = math.sin(rad)

    # Score hubs along heading
    best_dest = None
    best_score = -999.0
    for name, (h_lat, h_lon) in IRAN_HUBS:
        if name == nearest_hub:
            continue
        vec_lat = h_lat - lat
        vec_lon = h_lon - lon
        dist_h = math.hypot(vec_lat, vec_lon)
        if dist_h < 0.2:
            continue
        # Dot product
        score = (vec_lat * d_lat + vec_lon * d_lon) / dist_h
        if score > best_score:
            best_score = score
            best_dest = name

    origin = nearest_hub if best_score > 0 else (best_dest or "Tehran")
    dest = best_dest if best_score > 0 else nearest_hub
    
    if origin == dest:
        dest = "Mashhad" if origin != "Mashhad" else "Tehran"

    return origin, dest


def generate_synthesized_path(
    lat: float,
    lon: float,
    heading_deg: int,
    points_count: int = 5
) -> List[Tuple[float, float]]:
    """Builds a smooth historical track line leading up to current coordinates."""
    path = []
    rad = math.radians((heading_deg + 180) % 360)  # backwards along track
    step_deg = 0.35  # ~35 km step

    for i in range(points_count - 1, -1, -1):
        if i == 0:
            path.append((round(lat, 4), round(lon, 4)))
        else:
            p_lat = lat + math.cos(rad) * step_deg * i
            p_lon = lon + math.sin(rad) * step_deg * i
            path.append((round(p_lat, 4), round(p_lon, 4)))

    return path


def enrich_state_vector(sv: OpenSkyStateVector) -> Optional[Aircraft]:
    """Transforms an OpenSkyStateVector into the frontend Aircraft model."""
    if sv.latitude is None or sv.longitude is None:
        return None

    callsign = (sv.callsign or sv.icao24).strip()
    airline = identify_airline(sv.callsign, sv.origin_country)
    
    altitude_m = sv.baro_altitude if sv.baro_altitude is not None else (sv.geo_altitude or 0.0)
    altitude_ft = int(round(altitude_m * 3.28084))
    
    speed_ms = sv.velocity or 0.0
    speed_kts = int(round(speed_ms * 1.94384))
    
    heading_deg = int(round(sv.true_track or 0.0)) % 360
    
    vertical_rate_fpm = int(round((sv.vertical_rate or 0.0) * 196.85))
    geo_alt_ft = int(round((sv.geo_altitude or 0.0) * 3.28084)) if sv.geo_altitude is not None else None

    aircraft_type = estimate_aircraft_type(sv.category, sv.callsign, altitude_m, speed_ms)
    origin_city, dest_city = estimate_route(sv.latitude, sv.longitude, heading_deg, sv.callsign)
    path = generate_synthesized_path(sv.latitude, sv.longitude, heading_deg)

    # Format timestamp
    ts = sv.time_position or sv.last_contact or int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    last_update = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return Aircraft(
        id=sv.icao24.upper(),
        callsign=callsign,
        airline=airline,
        aircraftType=aircraft_type,
        lat=round(sv.latitude, 4),
        lon=round(sv.longitude, 4),
        altitude_ft=altitude_ft,
        heading_deg=heading_deg,
        speed_kts=speed_kts,
        origin_city=origin_city,
        destination_city=dest_city,
        path=path,
        lastUpdate=last_update,
        icao24=sv.icao24.lower(),
        country=sv.origin_country,
        squawk=sv.squawk,
        on_ground=sv.on_ground,
        vertical_rate_fpm=vertical_rate_fpm,
        geo_altitude_ft=geo_alt_ft,
        category=sv.category or 0,
    )


def enrich_state_vector_detail(sv: OpenSkyStateVector) -> Optional[AircraftDetail]:
    """Transforms an OpenSkyStateVector into the detailed AircraftDetail model."""
    base_aircraft = enrich_state_vector(sv)
    if not base_aircraft:
        return None

    pos_source_labels = {0: "ADS-B", 1: "ASTERIX", 2: "MLAT", 3: "FLARM"}

    return AircraftDetail(
        **base_aircraft.model_dump(),
        sensors=sv.sensors,
        position_source=pos_source_labels.get(sv.position_source, "ADS-B"),
        spi=sv.spi,
        time_position=sv.time_position,
        last_contact=sv.last_contact,
        coordinates_str=f"{base_aircraft.lat:.4f}°, {base_aircraft.lon:.4f}°",
    )
