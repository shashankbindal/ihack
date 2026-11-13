"""Cleaning rules from 03_data_sources.md applied to the raw listing files."""

import json
import logging
import re

import numpy as np
import pandas as pd

from src import config
from src.ingest_listings import LISTINGS_DIR, SOURCE_FILE

CLEAN_PATH = config.PROCESSED / "listings_clean.parquet"
# The source marks "amenity not mentioned" with 9.
AMENITY_MISSING_CODE = 9
BASE_COLUMNS = {"Price": "price_inr", "Area": "area_sqft", "Location": "locality",
                "No. of Bedrooms": "bhk", "Resale": "resale"}

log = logging.getLogger(__name__)


def snake(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def to_rupees(value) -> float:
    """Parse numeric rupees or Indian text forms such as '85 Lac', '1.2 Cr', '45,00,000'."""
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    text = str(value).lower().replace(",", "").replace("rs", "").replace("₹", "").strip()
    match = re.fullmatch(r"([\d.]+)\s*(cr|crore|crores|l|lac|lacs|lakh|lakhs)?", text)
    if not match:
        return float("nan")
    number, unit = float(match.group(1)), match.group(2) or ""
    if unit.startswith("c"):
        return number * 1e7
    if unit.startswith("l"):
        return number * 1e5
    return number


def load_raw_listings() -> pd.DataFrame:
    source = json.loads(SOURCE_FILE.read_text())
    frames = []
    for city in config.CITIES:
        raw = pd.read_csv(LISTINGS_DIR / f"{city}.csv")
        frame = raw.rename(columns=BASE_COLUMNS)
        frame.columns = [c if c in BASE_COLUMNS.values() else f"amen_{snake(c)}" for c in frame.columns]
        frame["city"] = city
        frames.append(frame)
    listings = pd.concat(frames, ignore_index=True)
    listings["locality"] = listings["locality"].astype(str).str.strip()
    listings["price_inr"] = listings["price_inr"].map(to_rupees)
    amenities = amenity_columns(listings)
    listings[amenities] = listings[amenities].where(listings[amenities] != AMENITY_MISSING_CODE).astype("float32")
    listings["area_basis"] = "as_listed_unspecified"
    listings["source"] = source["dataset"]
    listings["fetched_at"] = source["fetched_at"]
    return listings


def amenity_columns(frame: pd.DataFrame) -> list[str]:
    return [c for c in frame.columns if c.startswith("amen_")]


def drop_invalid(frame: pd.DataFrame) -> pd.DataFrame:
    lo_area, hi_area = config.AREA_BOUNDS_SQFT
    lo_bhk, hi_bhk = config.BHK_BOUNDS
    valid = (
        (frame.price_inr > 0)
        & frame.area_sqft.between(lo_area, hi_area)
        & frame.bhk.between(lo_bhk, hi_bhk)
        & (frame.area_sqft / frame.bhk).between(*config.AREA_PER_BHK_BOUNDS)
    )
    return frame[valid].copy()


def drop_missing_amenities(frame: pd.DataFrame) -> pd.DataFrame:
    """Drop listings whose amenity fields are all unstated. In this dataset that segment has a
    within-locality price/sqft spread several times that of complete records (see
    amenity_missing_evidence), so its location or price fields cannot be trusted."""
    return frame[frame[amenity_columns(frame)].notna().any(axis=1)].copy()


def within_locality_spread(frame: pd.DataFrame) -> float:
    """Standard deviation of log price/sqft around each locality's median."""
    log_ppsf = np.log(frame.price_inr / frame.area_sqft)
    return float((log_ppsf - log_ppsf.groupby([frame.city, frame.locality]).transform("median")).std())


def amenity_missing_evidence(frame: pd.DataFrame) -> dict:
    missing = frame[amenity_columns(frame)].isna().all(axis=1)
    by_city = {}
    for city, group in frame.groupby("city"):
        flag = missing[group.index]
        by_city[city] = {"share_all_missing": float(flag.mean() * 100),
                         "log_ppsf_spread_complete": within_locality_spread(group[~flag]),
                         "log_ppsf_spread_all_missing": within_locality_spread(group[flag]) if flag.any() else None}
    return by_city


def deduplicate(frame: pd.DataFrame, tolerance: float = config.DEDUP_PRICE_TOLERANCE) -> pd.DataFrame:
    """Collapse repeat listings of the same unit: same city, locality, area, BHK, resale flag
    and a price within `tolerance` of the first listing in the cluster."""
    keys = ["city", "locality", "area_sqft", "bhk", "resale"]
    ordered = frame.sort_values(keys + ["price_inr"]).copy()
    same_unit = (ordered[keys] == ordered[keys].shift()).all(axis=1)
    cluster_ids = []
    cluster, anchor_price = -1, np.nan
    for is_same, price in zip(same_unit, ordered.price_inr):
        if not (is_same and price <= anchor_price * (1 + tolerance)):
            cluster += 1
            anchor_price = price
        cluster_ids.append(cluster)
    ordered["unit_id"] = cluster_ids
    return ordered.drop_duplicates("unit_id").drop(columns="unit_id").sort_index()


def remove_price_outliers(frame: pd.DataFrame, max_z: float = config.OUTLIER_ROBUST_Z) -> pd.DataFrame:
    log_ppsf = np.log(frame.price_inr / frame.area_sqft)
    by_city = log_ppsf.groupby(frame.city)
    median = by_city.transform("median")
    mad = by_city.transform(lambda s: (s - s.median()).abs().median()) * 1.4826
    robust_z = (log_ppsf - median) / mad
    return frame[robust_z.abs() <= max_z].copy()


def attach_coordinates(frame: pd.DataFrame, localities: pd.DataFrame) -> pd.DataFrame:
    located = frame.merge(localities[["city", "locality", "lat", "lon", "geo_precision"]],
                          on=["city", "locality"], how="left")
    return located[located.geo_precision == "locality"].copy()


def pre_geocode_steps(raw: pd.DataFrame) -> dict[str, pd.DataFrame]:
    steps = {"raw": raw}
    steps["valid"] = drop_invalid(steps["raw"])
    steps["amenities_stated"] = drop_missing_amenities(steps["valid"])
    steps["deduplicated"] = deduplicate(steps["amenities_stated"])
    steps["outliers_removed"] = remove_price_outliers(steps["deduplicated"])
    return steps


def localities_to_geocode(raw: pd.DataFrame) -> dict[str, list[str]]:
    kept = pre_geocode_steps(raw)["outliers_removed"]
    return {city: sorted(group.locality.unique()) for city, group in kept.groupby("city")}


def clean(raw: pd.DataFrame, localities: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    steps = pre_geocode_steps(raw)
    steps["geocoded"] = attach_coordinates(steps["outliers_removed"], localities)
    counts = {name: df.groupby("city").size().to_dict() | {"total": len(df)} for name, df in steps.items()}
    final = steps["geocoded"].reset_index(drop=True)
    final["listing_id"] = [f"{c[:3].upper()}-{i:05d}" for i, c in enumerate(final.city)]
    return final, counts


def main() -> dict:
    from src.geocode import LOCALITIES_PATH

    raw = load_raw_listings()
    cleaned, counts = clean(raw, pd.read_parquet(LOCALITIES_PATH))
    CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_parquet(CLEAN_PATH, index=False)
    log.info("cleaned rows: %s", counts["geocoded"])
    return {"row_counts_by_step": counts, "amenity_missing_evidence": amenity_missing_evidence(drop_invalid(raw))}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
