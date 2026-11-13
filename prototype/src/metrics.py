"""Accuracy metrics from 06_accuracy_evaluation.md. Errors are reported in percent."""

import json

import numpy as np
import pandas as pd

from src import config


def signed_pct_error(true_value, predicted_value) -> np.ndarray:
    return (np.asarray(predicted_value) / np.asarray(true_value) - 1.0) * 100


def summarize(true_value, predicted_value) -> dict:
    true_value, predicted_value = np.asarray(true_value, float), np.asarray(predicted_value, float)
    signed = signed_pct_error(true_value, predicted_value)
    absolute = np.abs(signed)
    ratio = predicted_value / true_value
    median_ratio = np.median(ratio)
    return {
        "n": int(len(true_value)),
        "mdape": float(np.median(absolute)),
        "mape": float(np.mean(absolute)),
        "ppe10": float(np.mean(absolute <= 10) * 100),
        "ppe20": float(np.mean(absolute <= 20) * 100),
        "rmse_log": float(np.sqrt(np.mean((np.log(predicted_value) - np.log(true_value)) ** 2))),
        "bias": float(np.median(signed)),
        "overval20": float(np.mean(signed > 20) * 100),
        "cod": float(100 * np.mean(np.abs(ratio - median_ratio)) / median_ratio),
        "prd": float(np.mean(ratio) / (predicted_value.sum() / true_value.sum())),
    }


def cluster_bootstrap_mdape_delta(true_value, pred_a, pred_b, clusters, n_boot: int = 2000,
                                  seed: int = config.SEED) -> dict:
    """MdAPE(a) - MdAPE(b) with a 95% CI from a paired bootstrap that resamples whole spatial
    clusters, so correlated errors inside a cell are not treated as independent."""
    ape_a = np.abs(signed_pct_error(true_value, pred_a))
    ape_b = np.abs(signed_pct_error(true_value, pred_b))
    codes, uniques = pd.factorize(np.asarray(clusters))
    members = [np.flatnonzero(codes == k) for k in range(len(uniques))]
    rng = np.random.default_rng(seed)
    deltas = np.empty(n_boot)
    for i in range(n_boot):
        rows = np.concatenate([members[k] for k in rng.integers(0, len(members), len(members))])
        deltas[i] = np.median(ape_a[rows]) - np.median(ape_b[rows])
    low, high = np.percentile(deltas, [2.5, 97.5])
    delta = float(np.median(ape_a) - np.median(ape_b))
    return {
        "delta_mdape": delta,
        "relative_reduction_pct": float(-delta / np.median(ape_b) * 100),
        "ci95": [float(low), float(high)],
        "ci_excludes_zero": bool(high < 0 or low > 0),
        "n_clusters": len(members),
        "n_boot": n_boot,
        "method": "paired cluster bootstrap over H3 res-7 cells",
    }


def load_metrics() -> dict:
    return json.loads(config.METRICS_PATH.read_text()) if config.METRICS_PATH.exists() else {}


def rounded(value, digits: int = 4):
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, dict):
        return {k: rounded(v, digits) for k, v in value.items()}
    if isinstance(value, list):
        return [rounded(v, digits) for v in value]
    return value


def update_metrics(**sections) -> None:
    metrics = load_metrics() | rounded(sections)
    config.METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.METRICS_PATH.write_text(json.dumps(metrics, indent=2))
