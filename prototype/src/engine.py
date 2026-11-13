"""The model stack (B0, B1, B2, B3, M+ and the conformal layer) fitted as one unit."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold
from sklearn.neighbors import BallTree
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src import config
from src.calibrate import ConformalQuantileRegressor
from src.features import EARTH_RADIUS_KM, META_COLUMNS, feature_groups, target, to_radians

def gbm() -> LGBMRegressor:
    return LGBMRegressor(**config.LGBM_PARAMS)


def hedonic_model(attributes: list[str]):
    """B1: log-linear ridge on attributes with city and locality fixed effects."""
    encode = ColumnTransformer([
        ("numeric", make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler()), attributes),
        ("location", OneHotEncoder(handle_unknown="ignore", min_frequency=3), ["city", "locality"]),
    ])
    return make_pipeline(encode, Ridge(alpha=1.0))


class ResidualKNN:
    """Spatial residual smoother: a shrunken, distance-weighted mean of nearby out-of-fold residuals."""

    def __init__(self, lat, lon, residual):
        self.tree = BallTree(to_radians(lat, lon), metric="haversine")
        self.residual = np.asarray(residual)

    def neighbours(self, lat, lon) -> tuple[np.ndarray, np.ndarray]:
        k = min(config.KNN_NEIGHBOURS, len(self.residual))
        distance, index = self.tree.query(to_radians(lat, lon), k=k)
        return distance * EARTH_RADIUS_KM, index

    def correction(self, lat, lon) -> np.ndarray:
        distance_km, index = self.neighbours(lat, lon)
        weight = np.exp(-distance_km / config.KNN_BANDWIDTH_KM)
        return (weight * self.residual[index]).sum(axis=1) / (weight.sum(axis=1) + config.KNN_PRIOR_WEIGHT)

    def count_within(self, lat, lon, radius_km: float) -> np.ndarray:
        return self.tree.query_radius(to_radians(lat, lon), r=radius_km / EARTH_RADIUS_KM, count_only=True)

    def nearest_km(self, lat, lon) -> np.ndarray:
        return self.tree.query(to_radians(lat, lon), k=1)[0][:, 0] * EARTH_RADIUS_KM


KNN_WEIGHT_GRID = np.round(np.arange(0.0, 1.01, 0.1), 1)


def out_of_fold_predictions(X: pd.DataFrame, y: pd.Series, n_splits: int = 5) -> np.ndarray:
    oof = np.empty(len(y))
    for fit_idx, pred_idx in KFold(n_splits=n_splits, shuffle=True, random_state=config.SEED).split(X):
        oof[pred_idx] = gbm().fit(X.iloc[fit_idx], y.iloc[fit_idx]).predict(X.iloc[pred_idx])
    return oof


def best_knn_weight(b3: np.ndarray, correction: np.ndarray, y: np.ndarray) -> float:
    """Blend weight for the spatial residual layer, chosen on the calibration split.
    A weight of 0 means the layer does not help on unseen data and M+ falls back to B3."""
    errors = [np.median(np.abs(b3 + w * correction - y)) for w in KNN_WEIGHT_GRID]
    return float(KNN_WEIGHT_GRID[int(np.argmin(errors))])


@dataclass
class Engine:
    groups: dict[str, list[str]]
    city_median: dict[str, float]
    hedonic: object
    attributes_gbm: LGBMRegressor
    full_gbm: LGBMRegressor
    residual_knn: ResidualKNN
    conformal: ConformalQuantileRegressor
    bank: pd.DataFrame
    knn_weight: float = 1.0

    @property
    def attribute_columns(self) -> list[str]:
        return self.groups["attributes"] + ["city_code"]

    @property
    def full_columns(self) -> list[str]:
        return self.groups["attributes"] + self.groups["location"] + self.groups["osm"]

    def predict_log_ppsf(self, frame: pd.DataFrame) -> pd.DataFrame:
        b3 = self.full_gbm.predict(frame[self.full_columns])
        correction = self.knn_weight * self.residual_knn.correction(frame.lat, frame.lon)
        return pd.DataFrame({
            "b0": frame.city.map(self.city_median).to_numpy(),
            "b1": self.hedonic.predict(frame[self.groups["attributes"] + ["city", "locality"]]),
            "b2": self.attributes_gbm.predict(frame[self.attribute_columns]),
            "b3": b3,
            "knn_correction": correction,
            "mplus": b3 + correction,
        }, index=frame.index)

    def raw_interval(self, frame: pd.DataFrame, correction: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        lo, hi = self.conformal.raw_bounds(frame[self.full_columns])
        return lo + correction, hi + correction

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Point predictions (Rs) for every model, the 80% interval, and comparable-support stats."""
        logs = self.predict_log_ppsf(frame)
        lo, hi = self.raw_interval(frame, logs.knn_correction.to_numpy())
        area = frame.area_sqft.to_numpy()
        out = pd.DataFrame(index=frame.index)
        for name in ["b0", "b1", "b2", "b3", "mplus"]:
            out[f"pred_{name}"] = np.exp(logs[name]) * area
        for suffix, mondrian in [("", True), ("_pooled", False)]:
            low, high = self.conformal.interval(lo, hi, frame.city.to_numpy(), mondrian=mondrian)
            out[f"low{suffix}_inr"] = np.minimum(np.exp(low) * area, out.pred_mplus)
            out[f"high{suffix}_inr"] = np.maximum(np.exp(high) * area, out.pred_mplus)
        out["n_comparables_1km"] = self.residual_knn.count_within(frame.lat, frame.lon, config.COMPARABLE_RADIUS_KM)
        out["nearest_train_km"] = self.residual_knn.nearest_km(frame.lat, frame.lon)
        low_area, high_area = self.bank.area_sqft.quantile([0.005, 0.995])
        out["area_out_of_range"] = ~frame.area_sqft.between(low_area, high_area)
        return out


def fit_engine(train: pd.DataFrame, calib: pd.DataFrame) -> Engine:
    groups = feature_groups([c for c in train.columns if c not in META_COLUMNS])
    y = target(train)
    full_columns = groups["attributes"] + groups["location"] + groups["osm"]

    oof = out_of_fold_predictions(train[full_columns], y)
    conformal = ConformalQuantileRegressor().fit(train[full_columns], y)
    engine = Engine(
        groups=groups,
        city_median=y.groupby(train.city).median().to_dict(),
        hedonic=hedonic_model(groups["attributes"]).fit(train[groups["attributes"] + ["city", "locality"]], y),
        attributes_gbm=gbm().fit(train[groups["attributes"] + ["city_code"]], y),
        full_gbm=gbm().fit(train[full_columns], y),
        residual_knn=ResidualKNN(train.lat, train.lon, y.to_numpy() - oof),
        conformal=conformal,
        bank=train.reset_index(drop=True),
    )
    calib_logs = engine.predict_log_ppsf(calib)
    y_calib = target(calib).to_numpy()
    engine.knn_weight = best_knn_weight(calib_logs.b3.to_numpy(), calib_logs.knn_correction.to_numpy(), y_calib)
    calib_logs = engine.predict_log_ppsf(calib)
    lo, hi = engine.raw_interval(calib, calib_logs.knn_correction.to_numpy())
    conformal.calibrate(lo, hi, y_calib, calib.city.to_numpy())
    return engine
