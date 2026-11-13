import pytest
from fastapi.testclient import TestClient

from src.schemas import Valuation
from src.train import ENGINE_PATH

pytestmark = pytest.mark.skipif(not ENGINE_PATH.exists(), reason="run run_all.py to train the engine first")

WHITEFIELD = {"lat": 12.9698, "lon": 77.7500, "area_sqft": 1200, "bhk": 2, "resale": True}
CONTRACT_KEYS = {"valuation_id", "request", "model_version", "value", "confidence", "top_factors", "comparables",
                 "routing", "routing_reasons", "data_lineage", "disclaimer"}


@pytest.fixture(scope="module")
def client():
    from src.api import app

    with TestClient(app) as test_client:
        yield test_client


def test_valuate_returns_contract(client):
    response = client.post("/valuate", json=WHITEFIELD | {"floor": 3, "age": 5})
    assert response.status_code == 200
    body = response.json()
    Valuation.model_validate(body)
    assert CONTRACT_KEYS <= body.keys()
    value = body["value"]
    assert value["low_inr"] <= value["point_inr"] <= value["high_inr"]
    assert value["interval_level"] == 0.8
    assert body["routing"] in {"AUTO_ACCEPT", "DESKTOP_REVIEW", "PHYSICAL_VALUATION"}
    assert body["top_factors"] and body["comparables"]
    assert set(body["inputs_not_used"]) == {"floor", "age"}


def test_large_loan_forces_physical_valuation(client):
    body = client.post("/valuate", json=WHITEFIELD | {"loan_amount_inr": 80_00_000}).json()
    assert body["routing"] == "PHYSICAL_VALUATION"
    assert any("two independent valuer" in reason for reason in body["routing_reasons"])


def test_outside_coverage_is_rejected(client):
    response = client.post("/valuate", json=WHITEFIELD | {"lat": 28.61, "lon": 77.21})
    assert response.status_code == 422


def test_invalid_request_is_rejected(client):
    assert client.post("/valuate", json=WHITEFIELD | {"area_sqft": -5}).status_code == 422
