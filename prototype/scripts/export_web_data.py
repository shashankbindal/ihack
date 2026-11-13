"""Export the static JSON the web frontend reads. Run from prototype/: python -m scripts.export_web_data"""

import json
import shutil

import numpy as np
import pandas as pd

from src import config
from src.schemas import ValuationRequest
from src.train import CV_PREDICTIONS_PATH, FEATURES_PATH, PRIMARY, split_train_calib
from src.valuate import Valuer

OUT = config.ROOT.parent / "web" / "public" / "data"
SAMPLE_PER_CITY = 3
SAMPLE_SEED = 7
QUANTILES = {"p10": 0.1, "p25": 0.25, "p50": 0.5, "p75": 0.75, "p90": 0.9}


def write(name: str, payload) -> None:
    path = OUT / name
    path.write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False))
    print(f"{name}: {path.stat().st_size / 1024:.0f} KB")


def rounded(values, digits: int = 0) -> list:
    return [round(float(v), digits) for v in values]


def held_out_predictions(listings: pd.DataFrame) -> pd.DataFrame:
    predictions = pd.read_parquet(CV_PREDICTIONS_PATH)
    predictions = predictions[predictions.protocol == PRIMARY]
    merged = listings.merge(predictions[["listing_id", "pred_mplus"]], on="listing_id", how="inner")
    merged["ppsf"] = merged.price_inr / merged.area_sqft
    merged["est_ppsf"] = merged.pred_mplus / merged.area_sqft
    return merged


def listing_table(frame: pd.DataFrame) -> dict:
    cities = list(config.CITIES)
    localities = sorted(frame[["city", "locality"]].drop_duplicates().itertuples(index=False))
    locality_index = {(c, l): i for i, (c, l) in enumerate(localities)}
    return {
        "cities": cities,
        "localities": [{"city": c, "name": l} for c, l in localities],
        "city": [cities.index(c) for c in frame.city],
        "locality": [locality_index[(c, l)] for c, l in zip(frame.city, frame.locality)],
        "bhk": frame.bhk.tolist(),
        "resale": frame.resale.tolist(),
        "area_sqft": frame.area_sqft.tolist(),
        "asking_ppsf": rounded(frame.ppsf),
        "model_ppsf": rounded(frame.est_ppsf),
    }


def city_stats(frame: pd.DataFrame) -> list[dict]:
    rows = []
    for city in config.CITIES:
        group = frame[frame.city == city]
        rows.append({
            "city": city,
            "n_listings": len(group),
            "n_localities": int(group.locality.nunique()),
            "median_asking_ppsf": round(float(group.ppsf.median())),
            "median_model_ppsf": round(float(group.est_ppsf.median())),
            "asking_p25_ppsf": round(float(group.ppsf.quantile(0.25))),
            "asking_p75_ppsf": round(float(group.ppsf.quantile(0.75))),
        })
    return rows


def locality_stats(frame: pd.DataFrame, geo: pd.DataFrame) -> list[dict]:
    coords = geo.set_index(["city", "locality"])[["lat", "lon"]]
    rows = []
    for (city, locality), group in frame.groupby(["city", "locality"]):
        stats = {label: round(float(group.ppsf.quantile(q))) for label, q in QUANTILES.items()}
        rows.append({
            "city": city, "locality": locality,
            "lat": round(float(coords.loc[(city, locality), "lat"]), 5),
            "lon": round(float(coords.loc[(city, locality), "lon"]), 5),
            "n_listings": len(group), **{f"asking_{k}": v for k, v in stats.items()},
            "median_model_ppsf": round(float(group.est_ppsf.median())),
        })
    return rows


def form_localities(geo: pd.DataFrame, counts: pd.DataFrame) -> list[dict]:
    resolved = geo[geo.geo_precision != "city_centroid"].dropna(subset=["lat", "lon"])
    resolved = resolved.merge(counts, on=["city", "locality"], how="inner")
    resolved = resolved.sort_values(["city", "locality"])
    return [
        {"city": r.city, "locality": r.locality, "lat": round(r.lat, 5), "lon": round(r.lon, 5),
         "n_listings": int(r.n_listings)}
        for r in resolved.itertuples()
    ]


def sample_ids(held_out: pd.DataFrame, engine_calib_ids: set[str]) -> list[str]:
    pool = held_out[held_out.listing_id.isin(engine_calib_ids)]
    picks = [
        group.sample(SAMPLE_PER_CITY, random_state=SAMPLE_SEED).listing_id
        for _, group in pool.groupby("city")
    ]
    return sorted(pd.concat(picks))


def valuation_payloads(valuer: Valuer, rows: pd.DataFrame) -> list[dict]:
    payloads = []
    for row in rows.itertuples():
        amenities = {
            name: bool(getattr(row, f"amen_{name}")) for name in amenity_names(valuer)
            if not np.isnan(getattr(row, f"amen_{name}"))
        }
        request = ValuationRequest(lat=row.lat, lon=row.lon, area_sqft=row.area_sqft, bhk=int(row.bhk),
                                   resale=bool(row.resale), amenities=amenities)
        valuation = valuer.valuate(request).contract
        payloads.append({
            "listing_id": row.listing_id, "locality": row.locality, "city": row.city,
            "asking_price_inr": round(row.price_inr), "valuation": valuation,
        })
    return payloads


def amenity_names(valuer: Valuer) -> list[str]:
    return [column.removeprefix("amen_") for column in valuer.amenities]


def queue_rows(payloads: list[dict]) -> list[dict]:
    rows = []
    for payload in payloads:
        valuation = payload["valuation"]
        request = valuation["request"]
        estimate = valuation["value"]["point_inr"]
        rows.append({
            "listing_id": payload["listing_id"], "city": payload["city"], "locality": payload["locality"],
            "bhk": request["bhk"], "area_sqft": request["area_sqft"], "resale": request["resale"],
            "asking_price_inr": payload["asking_price_inr"],
            "asking_ppsf": round(payload["asking_price_inr"] / request["area_sqft"]),
            "estimate_inr": estimate,
            "estimate_ppsf": valuation["value"]["per_sqft_inr"],
            "variance_pct": round((payload["asking_price_inr"] / estimate - 1) * 100, 1),
            "grade": valuation["confidence"]["grade"], "routing": valuation["routing"],
        })
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    listings = pd.read_parquet(config.PROCESSED / "listings_clean.parquet")
    geo = pd.read_parquet(config.INTERIM / "localities.parquet")
    held_out = held_out_predictions(listings)
    counts = listings.groupby(["city", "locality"]).size().rename("n_listings").reset_index()

    shutil.copy(config.METRICS_PATH, OUT / "metrics.json")
    write("cities.json", city_stats(held_out))
    write("localities.json", locality_stats(held_out, geo))
    write("listings.json", listing_table(held_out))
    write("form_localities.json", form_localities(geo, counts))

    table = pd.read_parquet(FEATURES_PATH)
    _, calib = split_train_calib(table, "h3_cv")
    chosen = held_out[held_out.listing_id.isin(sample_ids(held_out, set(calib.listing_id)))]
    valuer = Valuer()
    payloads = valuation_payloads(valuer, chosen)
    write("valuations.json", {p["listing_id"]: p for p in payloads})
    write("queue.json", queue_rows(payloads))
    write("amenities.json", amenity_names(valuer))


if __name__ == "__main__":
    main()
