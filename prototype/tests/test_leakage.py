import numpy as np
import pandas as pd
import pytest

from src import config
from src.clean import CLEAN_PATH
from src.features import FEATURES_PATH, META_COLUMNS, PoiIndex, build_features, feature_groups, h3_cells
from src.train import assert_disjoint, fold_ids, split_train_calib


def synthetic_listings(n: int = 300, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "listing_id": [f"L{i}" for i in range(n)],
        "city": "Mumbai",
        "locality": rng.choice(["A", "B", "C", "D", "E", "F"], n),
        "lat": 19.0 + rng.uniform(0, 0.3, n),
        "lon": 72.8 + rng.uniform(0, 0.3, n),
        "area_sqft": rng.uniform(400, 2000, n),
        "bhk": rng.integers(1, 4, n),
        "resale": rng.integers(0, 2, n),
        "amen_gymnasium": rng.choice([0.0, 1.0, np.nan], n),
        "price_inr": rng.uniform(5e6, 5e7, n),
    })


def synthetic_index() -> PoiIndex:
    rng = np.random.default_rng(1)
    categories = ["metro", "rail", "school", "hospital", "park", "mall", "office"]
    pois = pd.DataFrame({
        "city": "Mumbai",
        "category": np.repeat(categories, 20),
        "lat": 19.0 + rng.uniform(0, 0.3, 20 * len(categories)),
        "lon": 72.8 + rng.uniform(0, 0.3, 20 * len(categories)),
    })
    return PoiIndex(pois, {"Mumbai": (19.07, 72.88)})


def test_features_do_not_depend_on_price():
    listings = synthetic_listings()
    index = synthetic_index()
    original = build_features(listings, index)
    shuffled = listings.assign(price_inr=np.random.default_rng(2).permutation(listings.price_inr.to_numpy()))
    pd.testing.assert_frame_equal(original, build_features(shuffled, index))
    assert not any("price" in c or "ppsf" in c for c in original.columns)


def test_feature_groups_exclude_target_and_metadata():
    columns = list(build_features(synthetic_listings(), synthetic_index()).columns)
    used = [c for group in feature_groups(columns).values() for c in group]
    assert set(used).isdisjoint(META_COLUMNS)
    assert not any("price" in c for c in used)


def test_spatial_folds_never_share_a_cell():
    listings = synthetic_listings(600)
    listings["h3_cv"] = h3_cells(listings, config.H3_RES_CV)
    folds = fold_ids(listings, "spatial_h3")
    assert listings.groupby("h3_cv").apply(lambda g: folds[g.index].tolist(), include_groups=False) \
        .map(lambda f: len(set(f)) == 1).all()


def test_train_calib_test_disjoint_on_cells():
    listings = synthetic_listings(600)
    listings["h3_cv"] = h3_cells(listings, config.H3_RES_CV)
    folds = fold_ids(listings, "spatial_h3")
    test = listings[folds == 0]
    train, calib = split_train_calib(listings[folds != 0], "h3_cv")
    for a, b in [(train, test), (calib, test), (train, calib)]:
        assert_disjoint(a, b, "h3_cv")
        assert_disjoint(a, b, "listing_id")


def test_assert_disjoint_detects_overlap():
    frame = synthetic_listings(10)
    with pytest.raises(AssertionError):
        assert_disjoint(frame.iloc[:6], frame.iloc[4:], "listing_id")


@pytest.mark.skipif(not CLEAN_PATH.exists(), reason="run run_all.py to build the cleaned dataset")
def test_cleaned_data_has_no_duplicate_units():
    cleaned = pd.read_parquet(CLEAN_PATH)
    keys = ["city", "locality", "area_sqft", "bhk", "resale", "price_inr"]
    assert not cleaned.duplicated(keys).any()
    assert cleaned.listing_id.is_unique


@pytest.mark.skipif(not FEATURES_PATH.exists(), reason="run run_all.py to build the feature table")
def test_real_spatial_folds_disjoint():
    table = pd.read_parquet(FEATURES_PATH)
    folds = fold_ids(table, "spatial_h3")
    cells_per_fold = [set(table.h3_cv[folds == k]) for k in range(config.N_FOLDS)]
    for i in range(config.N_FOLDS):
        for j in range(i + 1, config.N_FOLDS):
            assert cells_per_fold[i].isdisjoint(cells_per_fold[j])
