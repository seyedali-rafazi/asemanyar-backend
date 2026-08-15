import datetime
import math
import time
from typing import Any, Dict, List, Optional, Tuple

from ..schemas.aircraft import Aircraft, AircraftDetail
from ..schemas.airlabs import AirLabsFlight

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
    "KU": "Kuwait Airways",
    "OAS": "Oman Air",
    "WY": "Oman Air",
    "RJA": "Royal Jordanian",
    "RJ": "Royal Jordanian",
    "MEA": "Middle East Airlines",
    "ME": "Middle East Airlines",
    "IRAQ": "Iraqi Airways",
    "IAW": "Iraqi Airways",
    "IA": "Iraqi Airways",
    "PIA": "Pakistan International Airlines",
    "PK": "Pakistan International Airlines",
    "AIC": "Air India",
    "AI": "Air India",
    "AXB": "Air India Express",
    "IX": "Air India Express",
    "IGO": "IndiGo",
    "6E": "IndiGo",
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
    "LX": "Swiss International Air Lines",
    "CSN": "China Southern Airlines",
    "CZ": "China Southern Airlines",
    "CCA": "Air China",
    "CA": "Air China",
    "CES": "China Eastern Airlines",
    "MU": "China Eastern Airlines",
    "CSH": "Shanghai Airlines",
    "FM": "Shanghai Airlines",
    "ETD": "Etihad Airways",
    "EY": "Etihad Airways",
    "SVA": "Saudia",
    "SV": "Saudia",
    "OMA": "Oman Air",
    "JZR": "Jazeera Airways",
    "J9": "Jazeera Airways",
    "PGT": "Pegasus Airlines",
    "PC": "Pegasus Airlines",
    "WZZ": "Wizz Air",
    "W6": "Wizz Air",
    "WAZ": "Wizz Air Abu Dhabi",
    "5W": "Wizz Air Abu Dhabi",
    "RBG": "Air Arabia Egypt",
    "E5": "Air Arabia Egypt",
    "MAC": "Air Arabia Maroc",
    "3O": "Air Arabia Maroc",
}

# Airport IATA/ICAO code to friendly formatted city name
AIRPORT_MAP: Dict[str, str] = {
    # Iranian Airports
    "IKA": "Tehran (IKA)",
    "OIIE": "Tehran (IKA)",
    "THR": "Tehran (THR)",
    "OIII": "Tehran (THR)",
    "MHD": "Mashhad (MHD)",
    "OIMM": "Mashhad (MHD)",
    "SYZ": "Shiraz (SYZ)",
    "OISS": "Shiraz (SYZ)",
    "IFN": "Isfahan (IFN)",
    "OIFM": "Isfahan (IFN)",
    "TBZ": "Tabriz (TBZ)",
    "OITT": "Tabriz (TBZ)",
    "BND": "Bandar Abbas (BND)",
    "OIKB": "Bandar Abbas (BND)",
    "KIH": "Kish (KIH)",
    "OIBK": "Kish (KIH)",
    "AWZ": "Ahvaz (AWZ)",
    "OIAW": "Ahvaz (AWZ)",
    "KER": "Kerman (KER)",
    "OIKK": "Kerman (KER)",
    "ZAH": "Zahedan (ZAH)",
    "OIZH": "Zahedan (ZAH)",
    "RAS": "Rasht (RAS)",
    "OIGG": "Rasht (RAS)",
    "OMH": "Urmia (OMH)",
    "OITR": "Urmia (OMH)",
    "AZD": "Yazd (AZD)",
    "OIYY": "Yazd (AZD)",
    "XBJ": "Birjand (XBJ)",
    "OIMB": "Birjand (XBJ)",
    "PGU": "Asaluyeh (PGU)",
    "OIBP": "Asaluyeh (PGU)",
    "GSM": "Qeshm (GSM)",
    "OIKQ": "Qeshm (GSM)",
    "KSH": "Kermanshah (KSH)",
    "OICC": "Kermanshah (KSH)",
    "SRY": "Sari (SRY)",
    "OINZ": "Sari (SRY)",
    "CQD": "Shahrekord (CQD)",
    "OIFS": "Shahrekord (CQD)",
    "JWN": "Zanjan (JWN)",
    "OITZ": "Zanjan (JWN)",
    "DEF": "Dezful (DEF)",
    "OIAD": "Dezful (DEF)",
    "NSH": "Noshahr (NSH)",
    "OINN": "Noshahr (NSH)",
    "MRX": "Mahshahr (MRX)",
    "OIAM": "Mahshahr (MRX)",

    # Regional & International Hubs
    "DXB": "Dubai (DXB)",
    "OMDB": "Dubai (DXB)",
    "DWC": "Dubai (DWC)",
    "OMDW": "Dubai (DWC)",
    "SHJ": "Sharjah (SHJ)",
    "OMSJ": "Sharjah (SHJ)",
    "AUH": "Abu Dhabi (AUH)",
    "OMAA": "Abu Dhabi (AUH)",
    "DOH": "Doha (DOH)",
    "OTHH": "Doha (DOH)",
    "KWI": "Kuwait (KWI)",
    "OKKK": "Kuwait (KWI)",
    "IST": "Istanbul (IST)",
    "LTFM": "Istanbul (IST)",
    "SAW": "Istanbul (SAW)",
    "LTFJ": "Istanbul (SAW)",
    "ESB": "Ankara (ESB)",
    "LTAC": "Ankara (ESB)",
    "BGW": "Baghdad (BGW)",
    "ORBI": "Baghdad (BGW)",
    "NJF": "Najaf (NJF)",
    "ORNI": "Najaf (NJF)",
    "EBL": "Erbil (EBL)",
    "ORER": "Erbil (EBL)",
    "BSR": "Basra (BSR)",
    "ORMM": "Basra (BSR)",
    "MCT": "Muscat (MCT)",
    "OOMS": "Muscat (MCT)",
    "BAH": "Bahrain (BAH)",
    "OBBI": "Bahrain (BAH)",
    "RUH": "Riyadh (RUH)",
    "OERK": "Riyadh (RUH)",
    "JED": "Jeddah (JED)",
    "OEJN": "Jeddah (JED)",
    "DMM": "Dammam (DMM)",
    "OEDF": "Dammam (DMM)",
    "MED": "Medina (MED)",
    "OEMA": "Medina (MED)",
    "ISB": "Islamabad (ISB)",
    "OPIS": "Islamabad (ISB)",
    "KHI": "Karachi (KHI)",
    "OPKC": "Karachi (KHI)",
    "LHE": "Lahore (LHE)",
    "OPLA": "Lahore (LHE)",
    "BOM": "Mumbai (BOM)",
    "VABB": "Mumbai (BOM)",
    "DEL": "Delhi (DEL)",
    "VIDP": "Delhi (DEL)",
    "LHR": "London (LHR)",
    "EGLL": "London (LHR)",
    "CDG": "Paris (CDG)",
    "LFPG": "Paris (CDG)",
    "FRA": "Frankfurt (FRA)",
    "EDDF": "Frankfurt (FRA)",
    "AMS": "Amsterdam (AMS)",
    "EHAM": "Amsterdam (AMS)",
    "VIE": "Vienna (VIE)",
    "LOWW": "Vienna (VIE)",
    "SVO": "Moscow (SVO)",
    "UUEE": "Moscow (SVO)",
    "DME": "Moscow (DME)",
    "UUDD": "Moscow (DME)",
    "VKO": "Moscow (VKO)",
    "UUWW": "Moscow (VKO)",
    "EVN": "Yerevan (EVN)",
    "UDYZ": "Yerevan (EVN)",
    "TBS": "Tbilisi (TBS)",
    "UGTB": "Tbilisi (TBS)",
    "GYD": "Baku (GYD)",
    "UBBB": "Baku (GYD)",
    "DYU": "Dushanbe (DYU)",
    "UTDD": "Dushanbe (DYU)",
    "TAS": "Tashkent (TAS)",
    "UTTT": "Tashkent (TAS)",
    "ALA": "Almaty (ALA)",
    "UAAA": "Almaty (ALA)",
    "PEK": "Beijing (PEK)",
    "ZBAA": "Beijing (PEK)",
    "PKX": "Beijing (PKX)",
    "ZBAD": "Beijing (PKX)",
    "PVG": "Shanghai (PVG)",
    "ZSPD": "Shanghai (PVG)",
    "CAN": "Guangzhou (CAN)",
    "ZGGG": "Guangzhou (CAN)",
    "BKK": "Bangkok (BKK)",
    "VTBS": "Bangkok (BKK)",
    "KUL": "Kuala Lumpur (KUL)",
    "WMKK": "Kuala Lumpur (KUL)",
    "SIN": "Singapore (SIN)",
    "WSSS": "Singapore (SIN)",
    "KBL": "Kabul (KBL)",
    "OAKB": "Kabul (KBL)",
    "BEY": "Beirut (BEY)",
    "OLBA": "Beirut (BEY)",
    "DAM": "Damascus (DAM)",
    "OSDI": "Damascus (DAM)",
    "AMM": "Amman (AMM)",
    "OJAI": "Amman (AMM)",
    "CAI": "Cairo (CAI)",
    "HECA": "Cairo (CAI)",
    "SPX": "Sphinx Cairo (SPX)",
    "HESX": "Sphinx Cairo (SPX)",
}

# Aircraft ICAO type mapping to friendly name
AIRCRAFT_TYPE_MAP: Dict[str, str] = {
    "A320": "Airbus A320-200",
    "A20N": "Airbus A320neo",
    "A321": "Airbus A321-200",
    "A21N": "Airbus A321neo",
    "A319": "Airbus A319-100",
    "A19N": "Airbus A319neo",
    "A330": "Airbus A330",
    "A332": "Airbus A330-200",
    "A333": "Airbus A330-300",
    "A339": "Airbus A330-900neo",
    "A340": "Airbus A340",
    "A343": "Airbus A340-300",
    "A346": "Airbus A340-600",
    "A350": "Airbus A350",
    "A359": "Airbus A350-900",
    "A35K": "Airbus A350-1000",
    "A388": "Airbus A380-800",
    "A306": "Airbus A300-600",
    "A310": "Airbus A310-300",
    "B737": "Boeing 737",
    "B738": "Boeing 737-800",
    "B739": "Boeing 737-900",
    "B38M": "Boeing 737 MAX 8",
    "B39M": "Boeing 737 MAX 9",
    "B734": "Boeing 737-400",
    "B735": "Boeing 737-500",
    "B733": "Boeing 737-300",
    "B744": "Boeing 747-400",
    "B748": "Boeing 747-8",
    "B772": "Boeing 777-200",
    "B773": "Boeing 777-300",
    "B77W": "Boeing 777-300ER",
    "B788": "Boeing 787-8 Dreamliner",
    "B789": "Boeing 787-9 Dreamliner",
    "B78X": "Boeing 787-10 Dreamliner",
    "B752": "Boeing 757-200",
    "B763": "Boeing 767-300",
    "AT72": "ATR 72-500",
    "AT76": "ATR 72-600",
    "AT45": "ATR 42-500",
    "E190": "Embraer E190",
    "E195": "Embraer E195",
    "E75L": "Embraer E175",
    "F100": "Fokker 100",
    "F50": "Fokker 50",
    "MD82": "McDonnell Douglas MD-82",
    "MD83": "McDonnell Douglas MD-83",
    "MD88": "McDonnell Douglas MD-88",
    "CRJ9": "Bombardier CRJ-900",
    "CRJ7": "Bombardier CRJ-700",
    "C172": "Cessna 172 Skyhawk",
    "B412": "Bell 412 Helicopter",
    "B06": "Bell 206 JetRanger",
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
    ("Kuwait", (29.2267, 47.9689)),
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


def format_airport_name(iata: Optional[str], icao: Optional[str]) -> Optional[str]:
    """Resolves friendly city/airport label for IATA/ICAO codes."""
    if iata and iata.upper() in AIRPORT_MAP:
        return AIRPORT_MAP[iata.upper()]
    if icao and icao.upper() in AIRPORT_MAP:
        return AIRPORT_MAP[icao.upper()]
    if iata:
        return f"Airport ({iata.upper()})"
    if icao:
        return f"Airport ({icao.upper()})"
    return None


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
    def dist(h_lat: float, h_lon: float) -> float:
        return math.hypot(h_lat - lat, h_lon - lon)

    sorted_hubs = sorted(IRAN_HUBS, key=lambda h: dist(h[1][0], h[1][1]))
    nearest_hub = sorted_hubs[0][0]

    rad = math.radians(heading_deg)
    d_lat = math.cos(rad)
    d_lon = math.sin(rad)

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


def enrich_airlabs_flight(f: AirLabsFlight) -> Optional[Aircraft]:
    """Transforms an AirLabsFlight object into the frontend Aircraft model."""
    if f.lat is None or f.lng is None:
        return None

    callsign = (f.flight_icao or f.flight_iata or f.reg_number or f.hex).strip().upper()
    airline = identify_airline(f.airline_icao or f.airline_iata or callsign, f.flag)
    
    alt_m = f.alt or 0.0
    alt_ft = int(round(alt_m * 3.28084))

    speed_kmh = f.speed or 0.0
    speed_kts = int(round(speed_kmh * 0.539957))

    heading_deg = int(round(f.dir or 0.0)) % 360

    # Vertical rate: v_speed is in m/s (or km/h) -> ft/min
    vertical_rate_fpm = int(round((f.v_speed or 0.0) * 196.85)) if f.v_speed is not None else 0

    # Aircraft Type
    if f.aircraft_icao and f.aircraft_icao.upper() in AIRCRAFT_TYPE_MAP:
        aircraft_type = AIRCRAFT_TYPE_MAP[f.aircraft_icao.upper()]
    elif f.aircraft_icao:
        aircraft_type = f.aircraft_icao.upper()
    else:
        aircraft_type = estimate_aircraft_type(None, callsign, alt_m, speed_kmh / 3.6)

    # Route Origin & Destination
    origin_city = format_airport_name(f.dep_iata, f.dep_icao)
    dest_city = format_airport_name(f.arr_iata, f.arr_icao)

    if not origin_city or not dest_city:
        est_orig, est_dest = estimate_route(f.lat, f.lng, heading_deg, callsign)
        origin_city = origin_city or est_orig
        dest_city = dest_city or est_dest

    path = generate_synthesized_path(f.lat, f.lng, heading_deg)

    ts = f.updated or int(time.time())
    last_update = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    on_ground = f.status == "landed" or (alt_ft < 100 and speed_kts < 40)

    return Aircraft(
        id=f.hex.upper(),
        callsign=callsign,
        airline=airline,
        aircraftType=aircraft_type,
        lat=round(f.lat, 4),
        lon=round(f.lng, 4),
        altitude_ft=alt_ft,
        heading_deg=heading_deg,
        speed_kts=speed_kts,
        origin_city=origin_city,
        destination_city=dest_city,
        path=path,
        lastUpdate=last_update,
        icao24=f.hex.lower(),
        country=f.flag,
        squawk=f.squawk,
        on_ground=on_ground,
        vertical_rate_fpm=vertical_rate_fpm,
        geo_altitude_ft=alt_ft,
        category=0,
        reg_number=f.reg_number,
        flight_icao=f.flight_icao,
        flight_iata=f.flight_iata,
        dep_iata=f.dep_iata,
        dep_icao=f.dep_icao,
        arr_iata=f.arr_iata,
        arr_icao=f.arr_icao,
        airline_icao=f.airline_icao,
        airline_iata=f.airline_iata,
        aircraft_icao=f.aircraft_icao,
        status=f.status or "en-route",
    )


def enrich_airlabs_flight_detail(f: AirLabsFlight) -> Optional[AircraftDetail]:
    """Transforms an AirLabsFlight object into the detailed AircraftDetail model."""
    base_ac = enrich_airlabs_flight(f)
    if not base_ac:
        return None

    return AircraftDetail(
        **base_ac.model_dump(),
        position_source=f.type or "ADS-B",
        time_position=f.updated,
        last_contact=f.updated,
        coordinates_str=f"{base_ac.lat:.4f}°, {base_ac.lon:.4f}°",
    )
