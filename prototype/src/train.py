"""Cross-validated evaluation of B0..B3 and M+, then the production fit.

Protocols
- spatial_h3 (primary): GroupKFold over H3 res-7 cells, so every test cell is unseen in training.
- seen_locality (secondary): K-fold grouped by a project proxy, (city, locality, amenity signature).
  New-project listings share one price per sqft across unit sizes and amenities are project-level,
  so splitting units of one project across train and test would leak its price list. Test
  localities still usually appear in training: an established micro-market, but an unseen project.
The listing data carries no dates, so no time split is possible (recorded under not_run).
"""

import logging

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, GroupShuffleSplit

from src import config
from src.engine import Engine, fit_engine
from src.features import FEATURES_PATH
from src.metrics import cluster_bootstrap_mdape_delta, summarize, update_metrics

CV_PREDICTIONS_PATH = config.RESULTS / "cv_predictions.parquet"
ENGINE_PATH = config.MODELS / "engine.joblib"
MODELS = {"B0": "pred_b0", "B1": "pred_b1", "B2": "pred_b2", "B3": "pred_b3", "M+": "pred_mplus"}
MODEL_DESCRIPTIONS = {
    "B0": "per-city median price/sqft x area",
    "B1": "hedonic log-linear ridge, attributes + city and locality fixed effects",
    "B2": "LightGBM, listing attributes + city",
    "B3": "LightGBM, attributes + location (lat/lon) + OSM accessibility features",
    "M+": "B3 + spatial kNN smoother on out-of-fold residuals, blend weight fit on the calibration split",
}
PROTOCOL_GROUP = {"spatial_h3": "h3_cv", "seen_locality": "project_proxy"}
PRIMARY = "spatial_h3"

log = logging.getLogger(__name__)


def assert_disjoint(train: pd.DataFrame, test: pd.DataFrame, column: str) -> None:
    overlap = set(train[column]) & set(test[column])
    if overlap:
        raise AssertionError(f"{len(overlap)} values of {column} appear in both train and test")


def with_project_proxy(table: pd.DataFrame) -> pd.DataFrame:
    amenities = table.filter(like="amen_").fillna(-1).astype(int).astype(str).agg("".join, axis=1)
    return table.assign(project_proxy=table.city + "|" + table.locality + "|" + amenities)


def fold_ids(table: pd.DataFrame, protocol: str) -> np.ndarray:
    folds = np.empty(len(table), dtype=int)
    splitter = GroupKFold(n_splits=config.N_FOLDS, shuffle=True, random_state=config.SEED)
    for fold, (_, test_idx) in enumerate(splitter.split(table, groups=table[PROTOCOL_GROUP[protocol]])):
        folds[test_idx] = fold
    return folds


def split_train_calib(frame: pd.DataFrame, group_column: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    splitter = GroupShuffleSplit(n_splits=1, test_size=config.CALIB_SHARE, random_state=config.SEED)
    train_idx, calib_idx = next(splitter.split(frame, groups=frame[group_column]))
    return frame.iloc[train_idx], frame.iloc[calib_idx]


def cross_validate(table: pd.DataFrame, protocol: str) -> tuple[pd.DataFrame, dict]:
    group_column = PROTOCOL_GROUP[protocol]
    folds = fold_ids(table, protocol)
    predictions, sizes = [], []
    for fold in range(config.N_FOLDS):
        test = table[folds == fold]
        train, calib = split_train_calib(table[folds != fold], group_column)
        for column in {"listing_id", group_column}:
            assert_disjoint(train, test, column)
            assert_disjoint(calib, test, column)
        engine = fit_engine(train, calib)
        predicted = engine.predict(test)
        predicted["fold"] = fold
        predicted["knn_weight"] = engine.knn_weight
        predictions.append(predicted)
        sizes.append((len(train), len(calib), len(test)))
        log.info("%s fold %d: train %d, calib %d, test %d", protocol, fold, *sizes[-1])
    meta = ["listing_id", "city", "locality", "lat", "lon", "area_sqft", "bhk", "resale", "price_inr", "h3_cv"]
    result = table[meta].join(pd.concat(predictions))
    result["protocol"] = protocol
    train_n, calib_n, _ = np.mean(sizes, axis=0)
    return result, {"n_train_per_fold": float(train_n), "n_calib_per_fold": float(calib_n),
                    "n_test": int(len(result)), "n_folds": config.N_FOLDS}


def seen_share(frame: pd.DataFrame) -> float:
    """Share of test rows whose locality also had training rows in that fold."""
    seen = [frame[frame.fold == f].locality.isin(set(frame[frame.fold != f].locality)) for f in frame.fold.unique()]
    return float(pd.concat(seen).mean() * 100)


def add_price_bands(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[float]]:
    bands, edges = pd.qcut(frame.price_inr, 5, labels=[f"Q{i}" for i in range(1, 6)], retbins=True)
    return frame.assign(price_band=bands.astype(str)), [float(e) for e in edges]


def model_table(frame: pd.DataFrame) -> dict:
    return {name: summarize(frame.price_inr, frame[column]) for name, column in MODELS.items()}


def subgroup_audit(frame: pd.DataFrame, column: str = "pred_mplus") -> dict:
    rows = []
    for dimension in ["city", "price_band", "bhk", "resale"]:
        for value, group in frame.groupby(dimension):
            if len(group) >= 50:
                rows.append({"dimension": dimension, "value": str(value), **summarize(group.price_inr, group[column])})
    worst = max(rows, key=lambda r: r["mdape"])
    return {"model": "M+", "min_group_size": 50, "groups": rows, "worst_by_mdape": worst}


def evaluate(frame: pd.DataFrame) -> dict:
    significance = {
        f"M+_vs_{base}": cluster_bootstrap_mdape_delta(frame.price_inr, frame.pred_mplus, frame[MODELS[base]], frame.h3_cv)
        for base in ["B0", "B1", "B2", "B3"]
    }
    return {
        "models": model_table(frame),
        "per_city": {city: model_table(group) for city, group in frame.groupby("city")},
        "per_price_band": {band: model_table(group) for band, group in frame.groupby("price_band")},
        "significance": significance,
        "subgroup_audit": subgroup_audit(frame),
    }


def fit_production(table: pd.DataFrame) -> Engine:
    train, calib = split_train_calib(table, "h3_cv")
    engine = fit_engine(train, calib)
    config.MODELS.mkdir(parents=True, exist_ok=True)
    joblib.dump(engine, ENGINE_PATH)
    return engine


def main() -> None:
    table = with_project_proxy(pd.read_parquet(FEATURES_PATH))
    results, sizes = {}, {}
    for protocol in PROTOCOL_GROUP:
        results[protocol], sizes[protocol] = cross_validate(table, protocol)
    predictions = pd.concat(results.values(), ignore_index=True)
    predictions, edges = add_price_bands(predictions)
    config.RESULTS.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(CV_PREDICTIONS_PATH, index=False)

    primary = predictions[predictions.protocol == PRIMARY]
    secondary = predictions[predictions.protocol == "seen_locality"]
    update_metrics(
        split="h3 (spatial block, H3 res-7 GroupKFold); no time split",
        n_train=sizes[PRIMARY]["n_train_per_fold"],
        n_calib=sizes[PRIMARY]["n_calib_per_fold"],
        n_test=sizes[PRIMARY]["n_test"],
        protocol_sizes=sizes,
        units="percent for all error metrics; INR for prices",
        model_descriptions=MODEL_DESCRIPTIONS,
        price_band_edges_inr=edges,
        **evaluate(primary),
        seen_locality=evaluate(secondary) | {
            "note": "K-fold grouped by project proxy (city, locality, amenity signature); "
                    "test localities usually seen in training, projects unseen",
            "share_test_localities_seen_in_training": seen_share(secondary)},
        knn_weight_by_fold={p: results[p].groupby("fold").knn_weight.first().tolist() for p in results},
    )
    fit_production(table)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
