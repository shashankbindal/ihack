"""Locality geocoding with Nominatim: disk-cached, rate-limited, bounded to each city."""

import json
import logging
import math
import re
import time
from difflib import SequenceMatcher

import pandas as pd
import requests

from src import config

CACHE_PATH = config.INTERIM / "geocode_cache.json"
LOCALITIES_PATH = config.INTERIM / "localities.parquet"
# Nominatim place_rank: 16 is a city, 17-22 suburbs and neighbourhoods, 26+ streets and POIs.
MIN_LOCALITY_RANK = 17
MIN_NAME_SIMILARITY = 0.8
MIN_TOKEN_OVERLAP = 0.6
PLACE_TYPES = {"suburb", "neighbourhood", "quarter", "residential", "city_district", "borough", "village",
               "hamlet", "town", "city", "locality", "isolated_dwelling", "municipality", "district"}

log = logging.getLogger(__name__)


class Nominatim:
    def __init__(self) -> None:
        self.cache: dict = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}
        self.session = requests.Session()
        self.session.headers["User-Agent"] = config.USER_AGENT
        self.last_call = 0.0

    def search(self, query: str, viewbox: str | None = None) -> list[dict]:
        """Up to five candidates. The public instance does not reliably honour `layer`, so
        resolve_locality also filters candidates by place type and name."""
        key = f"{query}|{viewbox}"
        if key not in self.cache:
            wait = config.NOMINATIM_MIN_INTERVAL_S - (time.monotonic() - self.last_call)
            if wait > 0:
                time.sleep(wait)
            params = {"q": query, "format": "jsonv2", "limit": 5, "countrycodes": "in", "layer": "address"}
            if viewbox:
                params |= {"viewbox": viewbox, "bounded": 1}
            self.cache[key] = self.get_with_backoff(params)
        return self.cache[key]

    def get_with_backoff(self, params: dict, attempts: int = 4) -> list[dict]:
        """Retry server errors and dropped connections; the public instance has both under load."""
        for attempt in range(attempts):
            last_attempt = attempt == attempts - 1
            try:
                response = self.session.get(config.NOMINATIM_URL, params=params, timeout=60)
            except (requests.ConnectionError, requests.Timeout):
                if last_attempt:
                    raise
            else:
                if response.status_code < 500 or last_attempt:
                    response.raise_for_status()
                    return response.json()
            finally:
                self.last_call = time.monotonic()
            time.sleep(10 * (attempt + 1))

    def save(self) -> None:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(self.cache, ensure_ascii=False), encoding="utf-8")


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def viewbox_around(lat: float, lon: float, radius_km: float) -> str:
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * math.cos(math.radians(lat)))
    return f"{lon - dlon},{lat + dlat},{lon + dlon},{lat - dlat}"


def simplify_locality(name: str) -> str:
    name = re.sub(r"\b(east|west|north|south|off|main|road|phase\s*\w+|sector\s*[-\d]+|stage\s*\w+)\b", " ", name, flags=re.I)
    return re.sub(r"\s+", " ", name).strip()


def name_tokens(name: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", name.lower())
    return [w for w in words if w not in {"east", "west", "north", "south", "the"}]


def names_match(query: str, candidate: str) -> bool:
    """True when the candidate's name is plausibly the queried locality, not a shop or road named after it."""
    a, b = name_tokens(query), name_tokens(candidate)
    if not a or not b:
        return False
    joined_a, joined_b = "".join(a), "".join(b)
    shorter = min(joined_a, joined_b, key=len)
    if len(shorter) >= 5 and (joined_a in joined_b or joined_b in joined_a):
        return True
    overlap = len(set(a) & set(b)) / len(set(a) | set(b))
    return overlap >= MIN_TOKEN_OVERLAP or SequenceMatcher(None, joined_a, joined_b).ratio() >= MIN_NAME_SIMILARITY


def city_centre(client: Nominatim, city: str) -> tuple[float, float]:
    hit = client.search(f"{config.CITIES[city]}, India")[0]
    return float(hit["lat"]), float(hit["lon"])


def resolve_locality(client: Nominatim, locality: str, city: str, centre: tuple[float, float]) -> dict:
    viewbox = viewbox_around(*centre, config.CITY_RADIUS_KM)
    queries = [f"{locality}, {config.CITIES[city]}", locality]
    simplified = simplify_locality(locality)
    if simplified and simplified.lower() != locality.lower():
        queries.append(simplified)
    for query in queries:
        for hit in client.search(query, viewbox):
            lat, lon = float(hit["lat"]), float(hit["lon"])
            if (
                hit.get("addresstype") not in PLACE_TYPES
                or haversine_km(lat, lon, *centre) > config.CITY_RADIUS_KM
                or not names_match(locality, hit["name"])
            ):
                continue
            precision = "locality" if int(hit.get("place_rank", 0)) >= MIN_LOCALITY_RANK else "town"
            if haversine_km(lat, lon, *centre) < 1.0 and precision == "town":
                precision = "city_centroid"
            return {"lat": lat, "lon": lon, "geo_precision": precision, "geo_query": query,
                    "geo_match_name": hit["name"], "geo_addresstype": hit.get("addresstype")}
    return {"lat": None, "lon": None, "geo_precision": "unresolved", "geo_query": None}


def geocode_localities(localities: dict[str, list[str]]) -> pd.DataFrame:
    """Geocode {city: [locality, ...]} and return one row per (city, locality)."""
    client = Nominatim()
    rows = []
    try:
        for city, names in localities.items():
            centre = city_centre(client, city)
            rows.append({"city": city, "locality": "__centre__", "lat": centre[0], "lon": centre[1],
                         "geo_precision": "city_centroid", "geo_query": config.CITIES[city]})
            for i, name in enumerate(sorted(names)):
                rows.append({"city": city, "locality": name, **resolve_locality(client, name, city, centre)})
                if i % 50 == 0:
                    client.save()
                    log.info("%s: %d/%d", city, i, len(names))
    finally:
        client.save()
    frame = pd.DataFrame(rows)
    frame.to_parquet(LOCALITIES_PATH, index=False)
    return frame


def city_centres() -> dict[str, tuple[float, float]]:
    frame = pd.read_parquet(LOCALITIES_PATH)
    centres = frame[frame.locality == "__centre__"]
    return {row.city: (row.lat, row.lon) for row in centres.itertuples()}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from src.clean import load_raw_listings, localities_to_geocode

    geocode_localities(localities_to_geocode(load_raw_listings()))
