"""Conformalized quantile regression (Romano et al. 2019), Mondrian by city."""

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from src import config
from src.metrics import update_metrics

POOLED = "__all__"


def conformal_quantile(scores: np.ndarray, level: float) -> float:
    n = len(scores)
    rank = min(np.ceil((n + 1) * level) / n, 1.0)
    return float(np.quantile(scores, rank, method="higher"))


class ConformalQuantileRegressor:
    def __init__(self, level: float = config.INTERVAL_LEVEL):
        self.level = level
        alpha = (1 - level) / 2
        self.lower = LGBMRegressor(objective="quantile", alpha=alpha, **config.LGBM_PARAMS)
        self.upper = LGBMRegressor(objective="quantile", alpha=1 - alpha, **config.LGBM_PARAMS)
        self.margin: dict[str, float] = {}

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "ConformalQuantileRegressor":
        self.lower.fit(X, y)
        self.upper.fit(X, y)
        return self

    def raw_bounds(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        lo, hi = self.lower.predict(X), self.upper.predict(X)
        return np.minimum(lo, hi), np.maximum(lo, hi)

    def calibrate(self, lo: np.ndarray, hi: np.ndarray, y: np.ndarray, segments: np.ndarray) -> None:
        scores = np.maximum(lo - y, y - hi)
        self.margin = {POOLED: conformal_quantile(scores, self.level)}
        for segment in np.unique(segments):
            self.margin[segment] = conformal_quantile(scores[segments == segment], self.level)

    def interval(self, lo, hi, segments, mondrian: bool = True) -> tuple[np.ndarray, np.ndarray]:
        margin = np.array([self.margin.get(s, self.margin[POOLED]) if mondrian else self.margin[POOLED]
                           for s in segments])
        return lo - margin, hi + margin


def coverage_summary(frame: pd.DataFrame, low: str, high: str) -> dict:
    inside = (frame.price_inr >= frame[low]) & (frame.price_inr <= frame[high])
    width = (frame[high] - frame[low]) / frame.pred_mplus * 100

    def block(mask) -> dict:
        return {"coverage": float(inside[mask].mean() * 100), "median_width_pct": float(width[mask].median()),
                "n": int(mask.sum())}

    everything = pd.Series(True, index=frame.index)
    return {
        "overall": block(everything),
        "per_city": {city: block(frame.city == city) for city in sorted(frame.city.unique())},
        "per_price_band": {band: block(frame.price_band == band) for band in sorted(frame.price_band.unique())},
    }


def main() -> dict:
    from src.train import CV_PREDICTIONS_PATH

    predictions = pd.read_parquet(CV_PREDICTIONS_PATH)
    frame = predictions[predictions.protocol == "spatial_h3"]
    seen = predictions[predictions.protocol == "seen_locality"]
    result = {
        "level": config.INTERVAL_LEVEL,
        "method": "CQR (LightGBM quantile 10/90) + Mondrian conformal margin per city",
        "protocol": "spatial_h3",
        **coverage_summary(frame, "low_inr", "high_inr"),
        "pooled_conformal_for_contrast": coverage_summary(frame, "low_pooled_inr", "high_pooled_inr"),
        "seen_locality": coverage_summary(seen, "low_inr", "high_inr"),
    }
    update_metrics(coverage_80=result)
    return result


if __name__ == "__main__":
    main()
