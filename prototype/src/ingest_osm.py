"""OpenStreetMap POIs per city from Geofabrik extracts (ODbL), filtered with pyosmium.

Public Overpass instances proved unreliable for city-sized queries, and a dated PBF extract is
easier to reproduce. Multipolygon relations (some large parks, campuses) are not read.
"""

import json
import logging
from datetime import datetime, timezone

import osmium
import pandas as pd
import requests

from src import config
from src.geocode import Nominatim, city_centre, viewbox_around

OSM_DIR = config.RAW / "osm"
PBF_DIR = OSM_DIR / "pbf"
SOURCE_FILE = OSM_DIR / "source.json"
GEOFABRIK_URL = "https://download.geofabrik.de/asia/india/{zone}-latest.osm.pbf"
CITY_ZONE = {"Mumbai": "western-zone", "Bangalore": "southern-zone", "Hyderabad": "southern-zone",
             "Chennai": "southern-zone"}
TAG_KEYS = ("railway", "amenity", "aeroway", "highway", "shop", "leisure", "office")
MASS_TRANSIT = {"subway", "light_rail", "monorail"}
AMENITY_CATEGORY = {"bus_station": "bus_station", "school": "school", "college": "college", "university": "college",
                    "hospital": "hospital", "clinic": "hospital", "restaurant": "restaurant", "cafe": "restaurant"}
MAJOR_ROADS = {"motorway", "trunk", "primary"}

log = logging.getLogger(__name__)


def categories(tags) -> list[str]:
    found = []
    if tags.get("railway") in ("station", "halt"):
        found.append("metro" if tags.get("station") in MASS_TRANSIT else "rail")
    if tags.get("amenity") in AMENITY_CATEGORY:
        found.append(AMENITY_CATEGORY[tags["amenity"]])
    if tags.get("aeroway") == "aerodrome" and "iata" in tags:
        found.append("airport")
    if tags.get("shop") in ("mall", "supermarket"):
        found.append(tags["shop"])
    if tags.get("leisure") == "park":
        found.append("park")
    if "office" in tags:
        found.append("office")
    return found


def download_extract(zone: str) -> dict:
    path = PBF_DIR / f"{zone}-latest.osm.pbf"
    url = GEOFABRIK_URL.format(zone=zone)
    if not path.exists():
        PBF_DIR.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=600, headers={"User-Agent": config.USER_AGENT}) as response:
            response.raise_for_status()
            with path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1 << 20):
                    handle.write(chunk)
    modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    return {"zone": zone, "url": url, "file": path.name, "downloaded_at": modified}


def city_bboxes(cities) -> dict[str, tuple[float, float, float, float]]:
    client = Nominatim()
    boxes = {}
    for city in cities:
        west, north, east, south = map(float, viewbox_around(*city_centre(client, city), config.CITY_RADIUS_KM).split(","))
        boxes[city] = (south, west, north, east)
    return boxes


def inside(box, lat: float, lon: float) -> bool:
    south, west, north, east = box
    return south <= lat <= north and west <= lon <= east


def extract_pois(zone: str, boxes: dict) -> pd.DataFrame:
    rows = []
    processor = (osmium.FileProcessor(PBF_DIR / f"{zone}-latest.osm.pbf")
                 .with_locations()
                 .with_filter(osmium.filter.KeyFilter(*TAG_KEYS)))
    for obj in processor:
        if obj.is_relation():
            continue
        tags = obj.tags
        is_major_road = obj.is_way() and tags.get("highway") in MAJOR_ROADS
        found = categories(tags)
        if not found and not is_major_road:
            continue
        if obj.is_node():
            points = [(obj.location.lat, obj.location.lon)]
        else:
            nodes = [(n.location.lat, n.location.lon) for n in obj.nodes if n.location.valid()]
            if not nodes:
                continue
            points = nodes if is_major_road else [(sum(p[0] for p in nodes) / len(nodes),
                                                   sum(p[1] for p in nodes) / len(nodes))]
        name = tags.get("name")
        for city, box in boxes.items():
            for lat, lon in points:
                if not inside(box, lat, lon):
                    continue
                rows.extend({"city": city, "category": c, "lat": lat, "lon": lon, "name": name} for c in found)
                if is_major_road:
                    rows.append({"city": city, "category": "major_road", "lat": lat, "lon": lon, "name": name})
    return pd.DataFrame(rows)


def poi_path(city: str):
    return config.INTERIM / f"poi_{city}.parquet"


def main() -> dict:
    sources, counts = [], {}
    boxes = city_bboxes(config.CITIES)
    for zone in sorted(set(CITY_ZONE[c] for c in config.CITIES)):
        sources.append(download_extract(zone))
        zone_cities = {c: boxes[c] for c in config.CITIES if CITY_ZONE[c] == zone}
        if not all(poi_path(c).exists() for c in zone_cities):
            pois = extract_pois(zone, zone_cities)
            for city in zone_cities:
                pois[pois.city == city].drop_duplicates().to_parquet(poi_path(city), index=False)
        for city in zone_cities:
            table = pd.read_parquet(poi_path(city))
            counts[city] = table.category.value_counts().to_dict()
            log.info("%s: %d POI points", city, len(table))
    SOURCE_FILE.write_text(json.dumps({"provider": "Geofabrik", "licence": "ODbL 1.0", "extracts": sources}, indent=2))
    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
