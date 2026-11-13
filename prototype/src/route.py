"""Confidence grade (A-D) and routing, per 05_explainability_confidence.md, plus the trade-off curve."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src import config
from src.metrics import summarize, update_metrics

GRADES = "ABCD"
# Half-width at which the confidence score reaches zero: twice the grade-C limit.
SCORE_ZERO_HALF_WIDTH = 2 * config.GRADE_HALF_WIDTH["C"]


@dataclass
class Assessment:
    grade: str
    routing: str
    score: float
    reasons: list[str] = field(default_factory=list)


def half_width(point: float, low: float, high: float) -> float:
    return (high - low) / 2 / point


def worse(grade: str, steps: int = 1) -> str:
    return GRADES[min(GRADES.index(grade) + steps, len(GRADES) - 1)]


def assess(point: float, low: float, high: float, n_comparables: int, nearest_train_km: float,
           shadow_point: float, area_out_of_range: bool) -> Assessment:
    width = half_width(point, low, high)
    reasons = [f"80% interval +/-{width * 100:.1f}% of value",
               f"{n_comparables} training listings within {config.COMPARABLE_RADIUS_KM:g} km"]
    limits = config.GRADE_HALF_WIDTH
    grade = next((g for g in "ABC" if width <= limits[g]), "D")
    if grade == "A" and n_comparables < config.GRADE_A_MIN_COMPARABLES:
        grade = "B"
        reasons.append(f"fewer than {config.GRADE_A_MIN_COMPARABLES} comparables, capped at B")

    shadow_gap = abs(shadow_point / point - 1)
    if shadow_gap > config.SHADOW_DISAGREEMENT:
        grade = worse(grade)
        reasons.append(f"hedonic shadow model differs by {shadow_gap * 100:.0f}%, downgraded one grade")

    if nearest_train_km > config.OOD_NEAREST_TRAIN_KM or area_out_of_range:
        grade = max(grade, "C")
        if nearest_train_km > config.OOD_NEAREST_TRAIN_KM:
            reasons.append(f"nearest training listing {nearest_train_km:.1f} km away (out of distribution)")
        if area_out_of_range:
            reasons.append("area outside the training range (out of distribution)")

    score = float(np.clip(1 - width / SCORE_ZERO_HALF_WIDTH, 0, 1))
    return Assessment(grade, config.ROUTING_BY_GRADE[grade], round(score, 3), reasons)


def apply_policy_gate(assessment: Assessment, loan_amount_inr: float | None) -> Assessment:
    """Loans at or above the two-valuer threshold always go to physical valuation, whatever the grade."""
    if loan_amount_inr is not None and loan_amount_inr >= config.TWO_VALUER_LOAN_THRESHOLD_INR:
        assessment.routing = "PHYSICAL_VALUATION"
        assessment.reasons.append(
            f"policy: loan of Rs {loan_amount_inr / 1e5:,.0f} lakh is at or above Rs "
            f"{config.TWO_VALUER_LOAN_THRESHOLD_INR / 1e5:,.0f} lakh, two independent valuer reports required"
        )
    return assessment


def ltv_cap(loan_amount_inr: float) -> float:
    return next(cap for ceiling, cap in config.LTV_TIERS if loan_amount_inr <= ceiling)


def max_eligible_loan_inr(property_value_inr: float) -> float:
    """Largest loan that satisfies the tiered LTV cap for a property of this value."""
    best, floor = 0.0, 0.0
    for ceiling, cap in config.LTV_TIERS:
        candidate = min(ceiling, cap * property_value_inr)
        if candidate > floor:
            best = max(best, candidate)
        floor = ceiling
    return best


def assess_frame(frame: pd.DataFrame) -> pd.DataFrame:
    rows = [
        assess(r.pred_mplus, r.low_inr, r.high_inr, r.n_comparables_1km, r.nearest_train_km, r.pred_b1,
               r.area_out_of_range)
        for r in frame.itertuples()
    ]
    return frame.assign(grade=[a.grade for a in rows], routing=[a.routing for a in rows],
                        confidence_score=[a.score for a in rows])


def eligible_for_auto(frame: pd.DataFrame) -> pd.Series:
    shadow_gap = (frame.pred_b1 / frame.pred_mplus - 1).abs()
    in_distribution = (frame.nearest_train_km <= config.OOD_NEAREST_TRAIN_KM) & ~frame.area_out_of_range
    return in_distribution & (shadow_gap <= config.SHADOW_DISAGREEMENT)


def routing_curve(frame: pd.DataFrame, thresholds=np.arange(0.04, 0.61, 0.02)) -> list[dict]:
    """Auto-accept everything eligible whose interval half-width is under the threshold."""
    width = (frame.high_inr - frame.low_inr) / 2 / frame.pred_mplus
    eligible = eligible_for_auto(frame)
    curve = []
    for threshold in thresholds:
        auto = frame[eligible & (width <= threshold)]
        point = {"threshold_half_width_pct": float(threshold * 100), "auto_rate": float(len(auto) / len(frame) * 100),
                 "n_auto": int(len(auto))}
        if len(auto) >= 20:
            stats = summarize(auto.price_inr, auto.pred_mplus)
            point |= {"mdape_auto": stats["mdape"], "ppe10_auto": stats["ppe10"], "ppe20_auto": stats["ppe20"],
                      "overval20_auto": stats["overval20"]}
        curve.append(point)
    return curve


def select_operating_point(curve: list[dict]) -> dict:
    rule = (f"largest auto-accept share with MdAPE <= {config.AUTO_ACCEPT_MAX_MDAPE:g}% and "
            f">20% over-valuation share <= {config.AUTO_ACCEPT_MAX_OVERVAL20:g}% among accepted cases")
    feasible = [p for p in curve if "mdape_auto" in p and p["mdape_auto"] <= config.AUTO_ACCEPT_MAX_MDAPE
                and p["overval20_auto"] <= config.AUTO_ACCEPT_MAX_OVERVAL20]
    if not feasible:
        return {"rule": rule, "found": False}
    best = max(feasible, key=lambda p: p["auto_rate"])
    return {"rule": rule, "found": True, "grade_threshold": best["threshold_half_width_pct"],
            "grade_threshold_meaning": "auto-accept when the 80% interval half-width is at most this percent",
            "auto_rate": best["auto_rate"], "mdape_auto": best["mdape_auto"],
            "ppe10_auto": best["ppe10_auto"], "overval20_auto": best["overval20_auto"], "n_auto": best["n_auto"]}


def grade_table(frame: pd.DataFrame) -> dict:
    table = {}
    for grade in GRADES:
        group = frame[frame.grade == grade]
        entry = {"share": float(len(group) / len(frame) * 100), "n": int(len(group))}
        if len(group) >= 20:
            entry |= {k: summarize(group.price_inr, group.pred_mplus)[k] for k in ("mdape", "ppe10", "overval20")}
        table[grade] = entry
    routing = frame.routing.value_counts(normalize=True).mul(100).to_dict()
    return {"by_grade": table, "routing_share": routing, "thresholds_half_width": config.GRADE_HALF_WIDTH}


def main() -> dict:
    from src.train import CV_PREDICTIONS_PATH, PRIMARY

    predictions = pd.read_parquet(CV_PREDICTIONS_PATH)
    frame = assess_frame(predictions[predictions.protocol == PRIMARY])
    seen = assess_frame(predictions[predictions.protocol == "seen_locality"])
    curve, seen_curve = routing_curve(frame), routing_curve(seen)
    eligibility = f"in-distribution and hedonic shadow within {config.SHADOW_DISAGREEMENT:.0%} of M+"
    result = {
        "routing_curve": {"protocol": PRIMARY, "points": curve, "selected": select_operating_point(curve),
                          "eligibility": eligibility},
        "routing_curve_seen_locality": {"points": seen_curve, "selected": select_operating_point(seen_curve),
                                        "eligibility": eligibility},
        "grades": grade_table(frame),
        "grades_seen_locality": grade_table(seen),
    }
    update_metrics(**result)
    return result


if __name__ == "__main__":
    main()
