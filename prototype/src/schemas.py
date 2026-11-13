"""Request and response contract from 05_explainability_confidence.md."""

from typing import Literal

from pydantic import BaseModel, Field

Routing = Literal["AUTO_ACCEPT", "DESKTOP_REVIEW", "PHYSICAL_VALUATION"]


class ValuationRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    type: Literal["apartment"] = "apartment"
    area_sqft: float = Field(gt=0)
    bhk: int = Field(ge=1, le=10)
    floor: int | None = None
    age: float | None = None
    resale: bool = True
    amenities: dict[str, bool] = Field(default_factory=dict)
    loan_amount_inr: float | None = Field(default=None, gt=0)


class Value(BaseModel):
    point_inr: float
    per_sqft_inr: float
    low_inr: float
    high_inr: float
    interval_level: float


class Confidence(BaseModel):
    grade: Literal["A", "B", "C", "D"]
    score: float
    interval_width_pct: float
    n_comparables: int
    data_freshness_days: int


class Factor(BaseModel):
    feature: str
    effect_inr_per_sqft: float
    effect_pct: float
    direction: Literal["+", "-"]
    plain_text: str


class Comparable(BaseModel):
    id: str
    locality: str
    lat: float
    lon: float
    distance_m: float
    similarity: float
    area_sqft: int
    bhk: int
    listed_price_per_sqft: float
    adj_price_per_sqft: float


class Lineage(BaseModel):
    source: str
    licence: str
    fetched_at: str


class Lending(BaseModel):
    max_eligible_loan_inr: float
    max_eligible_loan_on_low_inr: float
    ltv_cap_for_requested_loan: float | None
    policy_note: str


class Valuation(BaseModel):
    valuation_id: str
    request: ValuationRequest
    model_version: str
    city: str
    value: Value
    confidence: Confidence
    top_factors: list[Factor]
    comparables: list[Comparable]
    routing: Routing
    routing_reasons: list[str]
    lending: Lending
    inputs_not_used: list[str]
    data_lineage: list[Lineage]
    disclaimer: str
