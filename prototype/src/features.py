"""Feature groups from 04_model_design.md. Nothing here reads the price columns."""

import h3
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

from src import config
from src.ingest_osm import poi_path

FEATURES_PATH = config.PROCESSED / "features_v1.parquet"
EARTH_RADIUS_KM = 6371.0

DISTANCE_CATEGORIES = ["metro", "rail", "bus_station", "airport", "major_road", "mall", "hospital", "college", "park"]
COUNT_CATEGORIES = ["school", "hospital", "mall", "supermarket", "park", "office", "restaurant"]
AMENITY_PREFIX = "amen_"
META_COLUMNS = ["listing_id", "city", "locality", "geo_precision", "price_inr", "area_sqft", "h3_feature", "h3_cv",
                "project_proxy"]


def to_radians(lat, lon) -> np.ndarray:
    return np.radians(np.column_stack([np.asarray(lat, float), np.asarray(lon, float)]))


class PoiIndex:
    """Nearest-distance and radius-count queries against cached OSM POIs."""

    def __init__(self, pois: pd.DataFrame, centres: dict[str, tuple[float, float]]):
        self.centres = centres
        self.trees = {
            (city, category): BallTree(to_radians(group.lat, group.lon), metric="haversine")
            for (city, category), group in pois.groupby(["city", "category"])
        }

    @classmethod
    def load(cls) -> "PoiIndex":
        from src.geocode import city_centres

        pois = pd.concat([pd.read_parquet(poi_path(city)) for city in config.CITIES], ignore_index=True)
        return cls(pois, city_centres())

    def query(self, city: str, lat, lon) -> pd.DataFrame:
        points = to_radians(lat, lon)
        out = {}
        for category in DISTANCE_CATEGORIES:
            tree = self.trees.get((city, category))
            out[f"dist_{category}_km"] = (
                tree.query(points, k=1)[0][:, 0] * EARTH_RADIUS_KM if tree else np.full(len(points), np.nan)
            )
        for category in COUNT_CATEGORIES:
            tree = self.trees.get((city, category))
            for radius in config.POI_RADII_KM:
                name = f"n_{category}_{radius:g}km"
                out[name] = (
                    tree.query_radius(points, r=radius / EARTH_RADIUS_KM, count_only=True)
                    if tree else np.zeros(len(points), int)
                )
        centre = to_radians(*self.centres[city])
        out["dist_centre_km"] = haversine_matrix(points, centre)[:, 0]
        frame = pd.DataFrame(out)
        frame["dist_transit_km"] = frame[["dist_metro_km", "dist_rail_km"]].min(axis=1)
        return frame


def haversine_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    dlat = a[:, None, 0] - b[None, :, 0]
    dlon = a[:, None, 1] - b[None, :, 1]
    h = np.sin(dlat / 2) ** 2 + np.cos(a[:, None, 0]) * np.cos(b[None, :, 0]) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(h))


def osm_features(frame: pd.DataFrame, index: PoiIndex) -> pd.DataFrame:
    parts = []
    for city, group in frame.groupby("city"):
        coords = group[["lat", "lon"]].drop_duplicates()
        feats = index.query(city, coords.lat, coords.lon)
        feats[["lat", "lon"]] = coords.to_numpy()
        merged = group[["lat", "lon"]].reset_index().merge(feats, on=["lat", "lon"], how="left").set_index("index")
        parts.append(merged.drop(columns=["lat", "lon"]))
    return pd.concat(parts).loc[frame.index]


def attribute_features(frame: pd.DataFrame) -> pd.DataFrame:
    amenities = [c for c in frame.columns if c.startswith(AMENITY_PREFIX)]
    out = pd.DataFrame(index=frame.index)
    out["log_area"] = np.log(frame.area_sqft)
    out["bhk"] = frame.bhk
    out["area_per_bhk"] = frame.area_sqft / frame.bhk
    out["resale"] = frame.resale
    out[amenities] = frame[amenities]
    out["amenity_count"] = frame[amenities].sum(axis=1, min_count=1)
    out["amenity_missing_share"] = frame[amenities].isna().mean(axis=1)
    return out


def location_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    out["city_code"] = frame.city.map({c: i for i, c in enumerate(config.CITIES)}).astype(int)
    out["lat"] = frame.lat
    out["lon"] = frame.lon
    return out


def h3_cells(frame: pd.DataFrame, resolution: int) -> pd.Series:
    return pd.Series(
        [h3.latlng_to_cell(lat, lon, resolution) for lat, lon in zip(frame.lat, frame.lon)],
        index=frame.index,
    )


def build_features(frame: pd.DataFrame, index: PoiIndex) -> pd.DataFrame:
    return pd.concat([attribute_features(frame), location_features(frame), osm_features(frame, index)], axis=1)


def feature_groups(columns: list[str]) -> dict[str, list[str]]:
    location = ["city_code", "lat", "lon"]
    osm = [c for c in columns if c.startswith(("dist_", "n_"))]
    attributes = [c for c in columns if c not in location and c not in osm]
    return {"attributes": attributes, "location": location, "osm": osm}


def target(frame: pd.DataFrame) -> pd.Series:
    """log(price per sqft): the modelling target."""
    return np.log(frame.price_inr / frame.area_sqft)


def main() -> pd.DataFrame:
    from src.clean import CLEAN_PATH

    listings = pd.read_parquet(CLEAN_PATH)
    features = build_features(listings, PoiIndex.load())
    table = pd.concat([listings[META_COLUMNS[:6]], features], axis=1)
    table["h3_feature"] = h3_cells(listings, config.H3_RES_FEATURE)
    table["h3_cv"] = h3_cells(listings, config.H3_RES_CV)
    table.to_parquet(FEATURES_PATH, index=False)
    return table


if __name__ == "__main__":
    main()
