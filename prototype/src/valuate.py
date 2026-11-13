"""Single-property valuation: request -> features -> M+ value, interval, grade, factors, comparables."""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cached_property

import joblib
import numpy as np
import pandas as pd
import shap

from src import config
from src.explain import comparables, rupee_steps, shap_factors, top_factors
from src.explain import haversine_km as distances_km
from src.features import PoiIndex, build_features
from src.geocode import CACHE_PATH, haversine_km
from src.ingest_listings import SOURCE_FILE
from src.ingest_osm import SOURCE_FILE as OSM_SOURCE_FILE
from src.route import apply_policy_gate, assess, ltv_cap, max_eligible_loan_inr
from src.schemas import ValuationRequest
from src.train import ENGINE_PATH

LOCALITY_SNAP_KM = 1.5
UNUSED_BY_MODEL = ("floor", "age")


class OutOfCoverage(ValueError):
    pass


@dataclass
class ValuationResult:
    contract: dict
    steps: pd.DataFrame
    base_ppsf: float


def file_timestamp(path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")


class Valuer:
    def __init__(self) -> None:
        self.engine = joblib.load(ENGINE_PATH)
        self.poi_index = PoiIndex.load()
        self.explainer = shap.TreeExplainer(self.engine.full_gbm)
        self.source = json.loads(SOURCE_FILE.read_text())
        self.osm_source = json.loads(OSM_SOURCE_FILE.read_text())
        self.amenities = [c for c in self.engine.groups["attributes"] if c.startswith("amen_")]

    @cached_property
    def lineage(self) -> list[dict]:
        return [
            {"source": f"Kaggle {self.source['dataset']} (listing asking prices)", "licence": self.source["licence"],
             "fetched_at": self.source["fetched_at"]},
            {"source": "OpenStreetMap (Geofabrik India zone extracts)", "licence": "ODbL 1.0",
             "fetched_at": min(e["downloaded_at"] for e in self.osm_source["extracts"])},
            {"source": "Nominatim geocoding of listing localities", "licence": "ODbL 1.0 (OSM data)",
             "fetched_at": file_timestamp(CACHE_PATH)},
        ]

    @cached_property
    def freshness_days(self) -> int:
        snapshot = datetime.fromisoformat(self.source["last_updated"].replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - snapshot).days

    def city_for(self, lat: float, lon: float) -> str:
        distances = {city: haversine_km(lat, lon, *centre) for city, centre in self.poi_index.centres.items()}
        city = min(distances, key=distances.get)
        if distances[city] > config.CITY_RADIUS_KM:
            raise OutOfCoverage(f"({lat}, {lon}) is outside the covered cities: {', '.join(config.CITIES)}")
        return city

    def nearest_locality(self, city: str, lat: float, lon: float) -> str:
        bank = self.engine.bank[self.engine.bank.city == city]
        distance = distances_km(lat, lon, bank.lat.to_numpy(), bank.lon.to_numpy())
        return bank.locality.iloc[distance.argmin()] if distance.min() <= LOCALITY_SNAP_KM else "unknown"

    def feature_row(self, request: ValuationRequest) -> pd.DataFrame:
        city = self.city_for(request.lat, request.lon)
        stated = {f"amen_{k.lower()}": float(v) for k, v in request.amenities.items()}
        listing = pd.DataFrame([{
            "listing_id": "request", "city": city, "locality": self.nearest_locality(city, request.lat, request.lon),
            "lat": request.lat, "lon": request.lon, "area_sqft": request.area_sqft, "bhk": request.bhk,
            "resale": int(request.resale), **{a: stated.get(a, np.nan) for a in self.amenities},
        }])
        return pd.concat([listing[["listing_id", "city", "locality", "area_sqft"]],
                          build_features(listing, self.poi_index)], axis=1)

    def valuate(self, request: ValuationRequest) -> ValuationResult:
        row = self.feature_row(request)
        logs = self.engine.predict_log_ppsf(row).iloc[0]
        prediction = self.engine.predict(row).iloc[0]
        point, low, high = prediction.pred_mplus, prediction.low_inr, prediction.high_inr

        assessment = assess(point, low, high, int(prediction.n_comparables_1km), prediction.nearest_train_km,
                            prediction.pred_b1, bool(prediction.area_out_of_range))
        assessment = apply_policy_gate(assessment, request.loan_amount_inr)

        base_log, factors = shap_factors(self.explainer, self.engine, row)
        steps = rupee_steps(base_log, factors, logs.knn_correction)
        contract = {
            "valuation_id": str(uuid.uuid4()),
            "request": request.model_dump(),
            "model_version": config.MODEL_VERSION,
            "city": row.city.iloc[0],
            "value": {"point_inr": round(point), "per_sqft_inr": round(point / request.area_sqft),
                      "low_inr": round(low), "high_inr": round(high), "interval_level": config.INTERVAL_LEVEL},
            "confidence": {"grade": assessment.grade, "score": assessment.score,
                           "interval_width_pct": round((high - low) / point * 100, 1),
                           "n_comparables": int(prediction.n_comparables_1km),
                           "data_freshness_days": self.freshness_days},
            "top_factors": top_factors(steps),
            "comparables": comparables(self.engine, row, logs.mplus),
            "routing": assessment.routing,
            "routing_reasons": assessment.reasons,
            "lending": {
                "max_eligible_loan_inr": round(max_eligible_loan_inr(point)),
                "max_eligible_loan_on_low_inr": round(max_eligible_loan_inr(low)),
                "ltv_cap_for_requested_loan": ltv_cap(request.loan_amount_inr) if request.loan_amount_inr else None,
                "policy_note": "Tiered LTV caps (90% up to Rs 30 lakh, 80% up to Rs 75 lakh, 75% above) and the "
                               "two-valuer rule for loans >= Rs 75 lakh follow RBI HFC Directions 2025.",
            },
            "inputs_not_used": [name for name in UNUSED_BY_MODEL if getattr(request, name) is not None],
            "data_lineage": self.lineage,
            "disclaimer": config.DISCLAIMER,
        }
        return ValuationResult(contract, steps, float(np.exp(base_log)))
