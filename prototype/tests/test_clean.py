import math

import pandas as pd
import pytest

from src.clean import deduplicate, drop_invalid, remove_price_outliers, to_rupees


@pytest.mark.parametrize("text, expected", [
    ("85 Lac", 85e5), ("1.2 Cr", 1.2e7), ("45,00,000", 45e5), ("Rs 2 crore", 2e7), (7_500_000, 7.5e6),
])
def test_to_rupees(text, expected):
    assert to_rupees(text) == pytest.approx(expected)


def test_to_rupees_rejects_garbage():
    assert math.isnan(to_rupees("price on request"))


def listing(**overrides) -> dict:
    return {"city": "Mumbai", "locality": "Powai", "area_sqft": 1000, "bhk": 2, "resale": 1,
            "price_inr": 2.0e7} | overrides


def test_dedup_collapses_relistings_within_tolerance():
    frame = pd.DataFrame([listing(), listing(price_inr=2.02e7), listing(price_inr=2.5e7)])
    assert sorted(deduplicate(frame, tolerance=0.02).price_inr) == [2.0e7, 2.5e7]


def test_dedup_keeps_different_units():
    frame = pd.DataFrame([listing(), listing(area_sqft=1001), listing(bhk=3), listing(locality="Chembur")])
    assert len(deduplicate(frame)) == 4


def test_drop_invalid_applies_bounds():
    frame = pd.DataFrame([listing(), listing(area_sqft=50), listing(bhk=0), listing(price_inr=0)])
    assert len(drop_invalid(frame)) == 1


def test_outlier_removal_is_per_city():
    normal = [listing(price_inr=1000 * (9000 + 50 * i)) for i in range(40)]
    extreme = listing(price_inr=1000 * 900_000)
    cheap_city = [listing(city="Hyderabad", price_inr=1000 * (4000 + 30 * i)) for i in range(40)]
    cleaned = remove_price_outliers(pd.DataFrame(normal + [extreme] + cheap_city))
    assert len(cleaned) == 80
    assert cleaned.price_inr.max() < 900_000 * 1000
