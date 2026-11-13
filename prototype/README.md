# Property valuation prototype (Hero Housing Fintech Challenge, PS1)

A small, reproducible automated valuation model (AVM) for apartments in Mumbai (MMR), Bengaluru,
Hyderabad and Chennai. Given a location and a few attributes it returns a value, a calibrated 80%
range, an A-D confidence grade, the main value drivers, comparable listings and a routing decision
(auto-accept, desktop review or physical valuation).

> **Ground-truth caveat.** Every accuracy number here is measured against **listing asking prices**
> from an open 2020 Kaggle snapshot, not registered transaction values or bank valuation reports.
> Asking prices are a noisy, upward-biased proxy. Treat the results as proof of method on public
> data, not as the accuracy a lender would see on its own collateral data.

Headline numbers live in `results/metrics.json` and the generated `results/summary.md`. Nothing in
this README is typed in by hand from a run.

## Quick start (Windows, Python 3.13)

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python run_all.py          # data -> models -> metrics -> figures -> latency -> tests
```

The first run downloads about 800 MB of OpenStreetMap extracts and geocodes about 700 localities
through Nominatim at 1 request/s, which can take an hour. Both are cached under `data/`, so reruns
take a few minutes. `--skip-tests` skips the final pytest run.

Serve and use the model:

```bash
.venv/Scripts/python -m uvicorn src.api:app --port 8000        # POST /valuate, docs at /docs
.venv/Scripts/python -m streamlit run app/streamlit_app.py     # UI: valuation, routing curve, economics
```

Example request:

```bash
curl -X POST localhost:8000/valuate -H "content-type: application/json" \
  -d '{"lat": 12.9698, "lon": 77.75, "area_sqft": 1200, "bhk": 2, "resale": true, "loan_amount_inr": 4000000}'
```

## Pipeline

| Step | Module | What it does |
|---|---|---|
| Listings | `src/ingest_listings.py` | Downloads the CC0 Kaggle dataset; records licence and fetch time |
| Geocoding | `src/geocode.py` | Locality name to centroid via Nominatim, bounded to 60 km of the city, place types only, name must match; cached |
| OSM | `src/ingest_osm.py` | Geofabrik India zone extracts filtered with pyosmium into POI tables per city |
| Cleaning | `src/clean.py` | Price parsing (Rs, lakh, crore), validity bounds (area 200-10,000 sqft, 1-6 BHK, 150-3,000 sqft per bedroom), drop listings with no amenity information, dedup, robust-z (3.5) outliers on log price/sqft per city, keep locality-precision geocodes only. All applied before any split; row counts per step are in `metrics.json` |
| Features | `src/features.py` | Attributes, location (city, lat/lon), OSM distances and 0.5/1/3 km counts, H3 cells. Never reads price |
| Models | `src/engine.py`, `src/train.py` | B0 city median, B1 hedonic ridge with locality effects, B2 GBM attributes, B3 GBM all features, M+ = B3 + spatial kNN on out-of-fold residuals |
| Intervals | `src/calibrate.py` | Conformalized quantile regression, Mondrian by city |
| Routing | `src/route.py` | Grade A-D from interval width, comparables, shadow-model gap, OOD checks; Rs 75 lakh two-valuer gate; tiered LTV |
| Explanation | `src/explain.py` | TreeSHAP converted to Rs/sqft steps, plain-text factors, model-adjusted comparables |
| Report | `src/report.py` | One-page HTML report (waterfall, comparables, map, lineage) and a headless-browser screenshot |
| API | `src/api.py`, `src/schemas.py`, `src/bench_api.py` | FastAPI `POST /valuate`, pydantic contract, p95 latency benchmark |
| Figures | `src/figures.py`, `src/explain.py` | Everything in `results/figures/`, read from `metrics.json` |

## Evaluation protocol

- **Primary: spatial-block CV.** 5-fold GroupKFold over H3 resolution-7 cells, so every test cell is
  absent from training. This is the honest estimate for a property in a micro-market the model has not
  seen. Inside each fold, 20% of the training cells are held out as the conformal calibration set.
- **Secondary: seen locality, unseen project.** 5-fold grouped by a project proxy (city, locality,
  amenity signature). New-project listings share one price per sqft across unit sizes and their
  amenities are project-level, so a plain random split leaks the project's price list (it gave
  implausibly low errors during development). Grouping by project keeps that out while test
  localities usually still appear in training. Reported under `seen_locality`, with its own coverage
  and routing curve.
- **No time split.** The dataset has no listing dates. This and every other skipped item is listed
  with its reason under `not_run` in `metrics.json`.
- Deduplication happens before any split; tests assert that no listing or H3 cell crosses train,
  calibration and test, and that features are unchanged when prices are shuffled.
- **Significance:** paired bootstrap of the MdAPE difference that resamples whole H3 cells, 2,000 draws.

## Design notes worth knowing

- **Dropping listings with no amenity information.** In the source data a large block of listings has
  every amenity coded "not mentioned". Their price/sqft spread around the locality median is three to
  four times that of complete listings in every city (measured, see
  `data.amenity_missing_evidence` in `metrics.json`), which points to unreliable location or price
  fields. They are removed before modelling.
- **Locality-level coordinates.** Listings carry a locality name, not an address, so all listings in
  a locality share its geocoded centroid. Distance features and comparables are therefore
  locality-resolution.
- **Area basis.** The dataset does not say whether area is carpet, built-up or super built-up, so it
  is used as listed and flagged `area_basis=as_listed_unspecified`.
- **M+ blend weight.** M+ adds a distance-weighted mean of nearby out-of-fold B3 residuals, scaled by
  a single weight chosen on the calibration split (grid 0 to 1). If the spatial layer does not help on
  unseen data, the weight goes to 0 and M+ equals B3. The chosen weight per fold is in `metrics.json`.
  The same calibration split is then used for the conformal margin; with one fitted scalar this is a
  minor departure from strict split-conformal assumptions.
- **Production engine.** `models/engine.joblib` (used by the API and UI) holds out 20% of H3 cells as
  its calibration set, the same regime as the primary protocol, so its intervals and the primary
  routing curve describe the same, conservative behaviour.
- **Intervals.** The reported range is widened, if needed, to contain the point estimate. This can
  only raise coverage.
- **SHAP in rupees.** SHAP values are additive in log price/sqft. They are applied largest first and
  converted to Rs/sqft step by step, so the steps sum exactly to the estimate; the split between
  factors depends on that order.
- **Inputs not used.** `floor` and `age` are accepted by the API (they are in the contract) but the
  data has no such fields, so the response lists them under `inputs_not_used`.
- **Policy gate.** Loans of Rs 75 lakh or more always route to physical valuation (two independent
  valuers), and the response includes the maximum loan under tiered LTV caps (90% / 80% / 75%). These
  are configuration in `src/config.py`, taken from the RBI (Housing Finance Companies) Directions, 2025
  (para 58 and Annex V).
- **Economics calculator.** Every cost and turnaround input in the UI is a labelled placeholder
  assumption; only the auto-accept share comes from the measured trade-off curve.

## Data sources

See `data/LICENCES.md`. In short: Kaggle "Housing Prices in Metropolitan Areas of India" (CC0),
OpenStreetMap via Geofabrik (ODbL), Nominatim geocoding (ODbL data, usage policy respected). No
portal scraping.

## Tests

```bash
.venv/Scripts/python -m pytest -q
```

`tests/test_clean.py` covers parsing, bounds, dedup and outliers; `tests/test_leakage.py` covers the
leakage guards; `tests/test_api.py` checks the response contract, the policy gate and input
validation (it needs a trained engine, so run `run_all.py` first).

## Environment note

`pyarrow` and `osmium` are pinned to older releases because Windows Smart App Control blocked the
DLLs in the latest wheels on the build machine.
