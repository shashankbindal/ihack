"""TreeSHAP factors, plain-text drivers and comparables for a single valuation.

SHAP values are additive in log(price/sqft). To express them in Rs/sqft we apply them one at a
time, largest first, starting from the model's base value; each factor's rupee effect is the
change in exp(cumulative log value). The steps then sum exactly to the final Rs/sqft, although
the split between factors depends on that ordering.
"""

import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

from src import config
from src.engine import Engine
from src.features import EARTH_RADIUS_KM

LOCATION_FACTOR = "lat_lon"
LOCAL_ADJUSTMENT = "local_market_adjustment"
CITY_NAMES = dict(enumerate(config.CITIES))

DISTANCE_LABELS = {
    "metro": "metro station", "rail": "rail station", "transit": "metro or rail station",
    "bus_station": "bus station", "airport": "airport", "major_road": "major road", "mall": "mall",
    "hospital": "hospital or clinic", "college": "college", "park": "park", "centre": "city centre",
}
COUNT_LABELS = {
    "school": "schools", "hospital": "hospitals and clinics", "mall": "malls", "supermarket": "supermarkets",
    "park": "parks", "office": "offices", "restaurant": "restaurants and cafes",
}


def describe(feature: str, value) -> str:
    if feature == LOCAL_ADJUSTMENT:
        if abs(value) < 0.005:
            return "Nearby listings: no spatial adjustment applied"
        side = "above" if value > 0 else "below"
        return f"Nearby listings priced {side} what the model expects (spatial residual)"
    if feature == LOCATION_FACTOR:
        return "Exact position within the city (latitude/longitude)"
    if pd.isna(value):
        return f"{feature.replace('_', ' ')}: not stated"
    if feature.startswith("dist_"):
        key = feature[len("dist_"):-len("_km")]
        return f"{DISTANCE_LABELS.get(key, key)} {value:.1f} km away"
    if feature.startswith("n_"):
        category, radius = feature[2:].rsplit("_", 1)
        return f"{value:.0f} {COUNT_LABELS.get(category, category)} within {radius.replace('km', ' km')}"
    if feature.startswith("amen_"):
        return f"{feature[5:].replace('_', ' ').title()}: {'yes' if value else 'no'}"
    templates = {
        "log_area": lambda v: f"Area {np.exp(v):,.0f} sqft",
        "bhk": lambda v: f"{v:.0f} BHK",
        "area_per_bhk": lambda v: f"{v:,.0f} sqft per bedroom",
        "resale": lambda v: "Resale property" if v else "New sale",
        "amenity_count": lambda v: f"{v:.0f} amenities listed",
        "amenity_missing_share": lambda v: f"{v:.0%} of amenity fields not stated in the listing",
        "city_code": lambda v: f"City: {CITY_NAMES[int(v)]}",
    }
    return templates[feature](value) if feature in templates else f"{feature} = {value}"


def shap_factors(explainer: shap.TreeExplainer, engine: Engine, row: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    """(base log value, one row per factor with its value and SHAP contribution in log space)."""
    X = row[engine.full_columns]
    phi = explainer.shap_values(X)[0]
    factors = pd.DataFrame({"feature": engine.full_columns, "value": X.iloc[0].to_numpy(), "phi": phi})
    location = factors.feature.isin(["lat", "lon"])
    merged = pd.DataFrame({"feature": [LOCATION_FACTOR], "value": [np.nan], "phi": [factors.phi[location].sum()]})
    factors = pd.concat([factors[~location], merged], ignore_index=True)
    return float(np.ravel(explainer.expected_value)[0]), factors


def rupee_steps(base_log: float, factors: pd.DataFrame, knn_correction: float, top_k: int = 8) -> pd.DataFrame:
    ordered = factors.reindex(factors.phi.abs().sort_values(ascending=False).index)
    head, tail = ordered.iloc[:top_k], ordered.iloc[top_k:]
    rest = pd.DataFrame({"feature": [f"other_{len(tail)}_features"], "value": [np.nan], "phi": [tail.phi.sum()]})
    adjustment = pd.DataFrame({"feature": [LOCAL_ADJUSTMENT], "value": [knn_correction], "phi": [knn_correction]})
    steps = pd.concat([head, rest, adjustment], ignore_index=True)
    levels = base_log + steps.phi.cumsum()
    previous = np.exp(np.r_[base_log, levels.to_numpy()[:-1]])
    steps["effect_inr_per_sqft"] = np.exp(levels.to_numpy()) - previous
    steps["effect_pct"] = (np.exp(steps.phi) - 1) * 100
    steps["plain_text"] = [
        f"{row.feature.replace('_', ' ')}" if row.feature.startswith("other_") else describe(row.feature, row.value)
        for row in steps.itertuples()
    ]
    return steps


def top_factors(steps: pd.DataFrame, k: int = 5) -> list[dict]:
    named = steps[~steps.feature.str.startswith("other_")]
    named = named.reindex(named.effect_inr_per_sqft.abs().sort_values(ascending=False).index).head(k)
    return [
        {"feature": r.feature, "effect_inr_per_sqft": round(float(r.effect_inr_per_sqft)),
         "effect_pct": round(float(r.effect_pct), 1), "direction": "+" if r.effect_inr_per_sqft >= 0 else "-",
         "plain_text": r.plain_text}
        for r in named.itertuples()
    ]


def comparables(engine: Engine, row: pd.DataFrame, subject_log_ppsf: float,
                k: int = config.N_COMPARABLES_SHOWN, search_km: float = 3.0) -> list[dict]:
    bank = engine.bank
    same_city = np.flatnonzero(bank.city.to_numpy() == row.city.iloc[0])
    candidates = bank.iloc[same_city]
    distance_km = haversine_km(row.lat.iloc[0], row.lon.iloc[0], candidates.lat.to_numpy(), candidates.lon.to_numpy())
    nearby = distance_km <= search_km
    if nearby.sum() < k:
        nearby = distance_km <= np.sort(distance_km)[min(k, len(distance_km)) - 1]
    candidates, distance_km = candidates[nearby], distance_km[nearby]
    area_gap = np.abs(np.log(candidates.area_sqft.to_numpy() / row.area_sqft.iloc[0]))
    same_bhk = candidates.bhk.to_numpy() == row.bhk.iloc[0]
    similarity = np.exp(-distance_km / 1.0) * np.exp(-area_gap / 0.25) * np.where(same_bhk, 1.0, 0.8)
    best = np.argsort(-similarity)[:k]
    chosen = candidates.iloc[best]
    chosen_log = engine.predict_log_ppsf(chosen).mplus.to_numpy()
    listed_ppsf = (chosen.price_inr / chosen.area_sqft).to_numpy()
    adjusted = listed_ppsf * np.exp(subject_log_ppsf - chosen_log)
    return [
        {"id": c.listing_id, "locality": c.locality, "lat": float(c.lat), "lon": float(c.lon),
         "distance_m": round(float(d * 1000)), "similarity": round(float(s), 3), "area_sqft": int(c.area_sqft),
         "bhk": int(c.bhk), "listed_price_per_sqft": round(float(p)), "adj_price_per_sqft": round(float(a))}
        for c, d, s, p, a in zip(chosen.itertuples(), distance_km[best], similarity[best], listed_ppsf, adjusted)
    ]


def haversine_km(lat: float, lon: float, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    lat, lon, lats, lons = np.radians(lat), np.radians(lon), np.radians(lats), np.radians(lons)
    h = np.sin((lats - lat) / 2) ** 2 + np.cos(lat) * np.cos(lats) * np.sin((lons - lon) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(h))


def waterfall_figure(steps: pd.DataFrame, base_ppsf: float, title: str):
    labels = ["Base (avg. listing)"] + [textwrap.fill(t, 42) for t in steps.plain_text] + ["Estimate"]
    effects = steps.effect_inr_per_sqft.to_numpy()
    starts = base_ppsf + np.r_[0, np.cumsum(effects)[:-1]]
    final = base_ppsf + effects.sum()
    fig, ax = plt.subplots(figsize=(8.5, 0.5 * len(labels) + 1.2))
    y = np.arange(len(labels))[::-1]
    ax.barh(y[0], base_ppsf, color="#8a8f98")
    colors = np.where(effects >= 0, "#2a9d8f", "#d1495b")
    ax.barh(y[1:-1], effects, left=starts, color=colors)
    ax.barh(y[-1], final, color="#264653")
    for yi, start, effect in zip(y[1:-1], starts, effects):
        ax.text(max(start, start + effect) + base_ppsf * 0.01, yi, f"{effect:+,.0f}", va="center", fontsize=8)
    ax.text(final * 1.01, y[-1], f"Rs {final:,.0f}/sqft", va="center", fontsize=8, fontweight="bold")
    ax.set_yticks(y, labels, fontsize=8)
    ax.set_xlabel("Rs per sqft")
    ax.set_title(title, fontsize=10, loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_xlim(0, max(starts.max(), final, base_ppsf) * 1.25)
    fig.tight_layout()
    return fig


def shap_summary_figure(engine: Engine, frame: pd.DataFrame, path, sample: int = 2000) -> None:
    X = frame[engine.full_columns].sample(min(sample, len(frame)), random_state=config.SEED)
    values = shap.TreeExplainer(engine.full_gbm).shap_values(X)
    shap.summary_plot(values, X, max_display=15, show=False, plot_size=(8, 6))
    plt.title("SHAP summary, B3/M+ core model (effect on log price per sqft)", fontsize=10, loc="left")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close("all")


def main() -> None:
    import joblib

    from src.features import FEATURES_PATH
    from src.train import ENGINE_PATH

    config.FIGURES.mkdir(parents=True, exist_ok=True)
    shap_summary_figure(joblib.load(ENGINE_PATH), pd.read_parquet(FEATURES_PATH), config.FIGURES / "shap_summary.png")


if __name__ == "__main__":
    main()
