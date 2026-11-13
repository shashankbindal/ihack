from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
MODELS = ROOT / "models"
RESULTS = ROOT / "results"
FIGURES = RESULTS / "figures"
METRICS_PATH = RESULTS / "metrics.json"

LISTINGS_DATASET = "ruchi798/housing-prices-in-metropolitan-areas-of-india"
LISTINGS_URL = f"https://www.kaggle.com/api/v1/datasets/download/{LISTINGS_DATASET}"
LISTINGS_META_URL = f"https://www.kaggle.com/api/v1/datasets/view/{LISTINGS_DATASET}"

# Dataset file stem -> name used in geocoding queries.
CITIES = {"Mumbai": "Mumbai", "Bangalore": "Bengaluru", "Hyderabad": "Hyderabad", "Chennai": "Chennai"}
CITY_RADIUS_KM = 60

USER_AGENT = "valuation-prototype/0.1"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_MIN_INTERVAL_S = 1.1

H3_RES_FEATURE = 8
H3_RES_CV = 7
N_FOLDS = 5
CALIB_SHARE = 0.2
SEED = 42

AREA_BOUNDS_SQFT = (200, 10_000)
BHK_BOUNDS = (1, 6)
# A bedroom plus its share of living space below 150 sqft, or above 3,000 sqft, is not a plausible listing.
AREA_PER_BHK_BOUNDS = (150, 3_000)
OUTLIER_ROBUST_Z = 3.5
DEDUP_PRICE_TOLERANCE = 0.02

POI_RADII_KM = (0.5, 1.0, 3.0)

KNN_NEIGHBOURS = 30
KNN_BANDWIDTH_KM = 2.0
KNN_PRIOR_WEIGHT = 3.0
COMPARABLE_RADIUS_KM = 1.0
N_COMPARABLES_SHOWN = 5

INTERVAL_LEVEL = 0.8
SHADOW_DISAGREEMENT = 0.20
OOD_NEAREST_TRAIN_KM = 3.0

# Grade thresholds on interval half-width (fraction of point value), per 05_explainability_confidence.md.
GRADE_HALF_WIDTH = {"A": 0.08, "B": 0.12, "C": 0.20}
GRADE_A_MIN_COMPARABLES = 5
ROUTING_BY_GRADE = {
    "A": "AUTO_ACCEPT",
    "B": "AUTO_ACCEPT",
    "C": "DESKTOP_REVIEW",
    "D": "PHYSICAL_VALUATION",
}

# Operating-point rule for the trade-off curve (our proposal, to be set by the lender's risk policy):
# the largest auto-accept share whose accepted cases keep MdAPE and the >20% over-valuation tail under these.
AUTO_ACCEPT_MAX_MDAPE = 10.0
AUTO_ACCEPT_MAX_OVERVAL20 = 5.0

# RBI (Housing Finance Companies) Directions, 2025: para 58 (LTV by loan amount), Annex V (two valuers).
TWO_VALUER_LOAN_THRESHOLD_INR = 75_00_000
LTV_TIERS = ((30_00_000, 0.90), (75_00_000, 0.80), (float("inf"), 0.75))

MODEL_VERSION = "gm-2026.11.0"
DISCLAIMER = (
    "Indicative AVM output trained on listing asking prices (a proxy, not registered "
    "transactions). Not a statutory valuation."
)

LGBM_PARAMS = {
    "n_estimators": 600,
    "learning_rate": 0.03,
    "num_leaves": 31,
    "min_child_samples": 20,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_lambda": 1.0,
    "random_state": SEED,
    "verbose": -1,
}
