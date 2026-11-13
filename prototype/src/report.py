"""One-page HTML valuation report: value and range, grade, waterfall, comparables, map, lineage."""

import base64
import html
import io
import logging
import shutil
import subprocess
from pathlib import Path

import folium
import matplotlib.pyplot as plt
import pandas as pd

from src import config
from src.explain import waterfall_figure
from src.valuate import ValuationResult

GRADE_COLOURS = {"A": "#2a9d8f", "B": "#8ab17d", "C": "#e9c46a", "D": "#d1495b"}
BROWSER_CANDIDATES = [
    "msedge", "chrome", "google-chrome", "chromium",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]

log = logging.getLogger(__name__)


def inr(value: float) -> str:
    if value >= 1e7:
        return f"Rs {value / 1e7:,.2f} crore"
    return f"Rs {value / 1e5:,.1f} lakh"


def figure_png_base64(fig) -> str:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buffer.getvalue()).decode()


def map_html(contract: dict) -> str:
    request = contract["request"]
    fmap = folium.Map(location=[request["lat"], request["lon"]], zoom_start=14, tiles="OpenStreetMap")
    folium.Marker([request["lat"], request["lon"]], tooltip="Subject property",
                  icon=folium.Icon(color="red", icon="home")).add_to(fmap)
    for comp in contract["comparables"]:
        folium.CircleMarker([comp["lat"], comp["lon"]], radius=6, color="#264653", fill=True,
                            tooltip=f"{comp['id']}: Rs {comp['adj_price_per_sqft']:,}/sqft adj.").add_to(fmap)
    srcdoc = html.escape(fmap.get_root().render())
    return f'<iframe srcdoc="{srcdoc}" style="width:100%;height:300px;border:1px solid #ddd"></iframe>'


def render(result: ValuationResult) -> str:
    c = result.contract
    value, confidence = c["value"], c["confidence"]
    figure = waterfall_figure(result.steps, result.base_ppsf, "How the estimate is built (Rs/sqft)")
    waterfall = figure_png_base64(figure)
    comparables = pd.DataFrame(c["comparables"])[
        ["id", "locality", "distance_m", "area_sqft", "bhk", "listed_price_per_sqft", "adj_price_per_sqft", "similarity"]
    ].to_html(index=False, border=0, classes="table")
    factors = "".join(
        f"<li><b>{f['direction']}Rs {abs(f['effect_inr_per_sqft']):,}/sqft</b> ({f['effect_pct']:+.1f}%): "
        f"{html.escape(f['plain_text'])}</li>" for f in c["top_factors"]
    )
    reasons = "".join(f"<li>{html.escape(r)}</li>" for r in c["routing_reasons"])
    lineage = "".join(f"<li>{html.escape(l['source'])} ({l['licence']}), fetched {l['fetched_at']}</li>"
                      for l in c["data_lineage"])
    unused = (f"<p class='muted'>Inputs received but not used by this model version: {', '.join(c['inputs_not_used'])}</p>"
              if c["inputs_not_used"] else "")
    request = c["request"]
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Valuation report</title>
<style>
body {{ font-family: Segoe UI, Arial, sans-serif; color:#1d2327; max-width: 980px; margin: 24px auto; padding: 0 16px; font-size: 14px; }}
h1 {{ font-size: 20px; margin: 0; }} h2 {{ font-size: 15px; margin: 18px 0 6px; }}
.muted {{ color:#666; font-size: 12px; }}
.cards {{ display:grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 12px; }}
.card {{ border:1px solid #e3e3e3; border-radius:6px; padding:10px; }}
.card .big {{ font-size: 20px; font-weight: 600; }}
.grade {{ display:inline-block; color:#fff; border-radius:4px; padding:2px 10px; font-weight:700; background:{GRADE_COLOURS[confidence['grade']]}; }}
.two {{ display:grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.table {{ border-collapse: collapse; width:100%; font-size: 12px; }}
.table th, .table td {{ border-bottom:1px solid #eee; padding:4px 6px; text-align:right; }}
.table th:nth-child(-n+2), .table td:nth-child(-n+2) {{ text-align:left; }}
.disclaimer {{ background:#fff4e5; border:1px solid #f0c36d; padding:8px; border-radius:4px; font-size:12px; }}
img {{ max-width: 100%; }}
</style></head><body>
<h1>Property valuation report</h1>
<div class="muted">ID {c['valuation_id']} | model {c['model_version']} | {c['city']} | {request['bhk']} BHK apartment,
{request['area_sqft']:,.0f} sqft | ({request['lat']:.5f}, {request['lon']:.5f})</div>
<div class="cards">
 <div class="card"><div class="muted">Point estimate</div><div class="big">{inr(value['point_inr'])}</div>
   <div>Rs {value['per_sqft_inr']:,}/sqft</div></div>
 <div class="card"><div class="muted">{value['interval_level']:.0%} interval</div>
   <div class="big">{inr(value['low_inr'])} to {inr(value['high_inr'])}</div><div>width {confidence['interval_width_pct']}%</div></div>
 <div class="card"><div class="muted">Confidence</div><div class="big"><span class="grade">{confidence['grade']}</span></div>
   <div>score {confidence['score']:.2f}, {confidence['n_comparables']} listings within 1 km</div></div>
 <div class="card"><div class="muted">Routing</div><div class="big" style="font-size:15px">{c['routing'].replace('_', ' ')}</div>
   <div>max loan (tiered LTV) {inr(c['lending']['max_eligible_loan_inr'])}</div></div>
</div>
<h2>Why this routing</h2><ul>{reasons}</ul>
<div class="two">
 <div><h2>Value drivers</h2><img src="data:image/png;base64,{waterfall}" alt="waterfall of value drivers"></div>
 <div><h2>Top factors</h2><ul>{factors}</ul>
   <p class="muted">Effects come from TreeSHAP on log price/sqft, applied largest first and converted to Rs/sqft;
   they sum exactly to the estimate. Percentages are each factor's multiplicative effect.</p>{unused}</div>
</div>
<h2>Comparable listings (adjusted to the subject with the model)</h2>{comparables}
<h2>Location</h2>{map_html(c)}
<h2>Data lineage</h2><ul class="muted">{lineage}</ul>
<p class="disclaimer">{html.escape(c['disclaimer'])} Data freshness: the listing snapshot is
{confidence['data_freshness_days']} days old.</p>
</body></html>"""


def find_browser() -> str | None:
    for candidate in BROWSER_CANDIDATES:
        path = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if path:
            return path
    return None


def screenshot(html_path: Path, png_path: Path) -> bool:
    browser = find_browser()
    if browser is None:
        log.warning("no Chromium-based browser found; report screenshot skipped")
        return False
    subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--window-size=1000,1500",
                    "--virtual-time-budget=8000", f"--screenshot={png_path}", html_path.resolve().as_uri()],
                   check=True, timeout=120, capture_output=True)
    return png_path.exists()


def sample_request() -> dict:
    """A 2 BHK listing from the production calibration split (the point model never saw its price),
    chosen among those with the most training listings nearby, near the median price."""
    import joblib

    from src.features import FEATURES_PATH
    from src.train import ENGINE_PATH

    features = pd.read_parquet(FEATURES_PATH)
    engine = joblib.load(ENGINE_PATH)
    unseen = features[~features.listing_id.isin(set(engine.bank.listing_id)) & (features.bhk == 2)]
    support = engine.residual_knn.count_within(unseen.lat, unseen.lon, config.COMPARABLE_RADIUS_KM)
    well_supported = unseen.iloc[(-support).argsort()[:50]]
    row = well_supported.iloc[(well_supported.price_inr - well_supported.price_inr.median()).abs().argsort().iloc[0]]
    return {"lat": float(row.lat), "lon": float(row.lon), "area_sqft": float(row.area_sqft), "bhk": int(row.bhk),
            "resale": bool(row.resale), "floor": 4, "loan_amount_inr": 40_00_000,
            "_listing_id": row.listing_id, "_listed_price_inr": float(row.price_inr)}


def main() -> dict:
    from src.metrics import update_metrics
    from src.schemas import ValuationRequest
    from src.valuate import Valuer

    sample = sample_request()
    request = ValuationRequest(**{k: v for k, v in sample.items() if not k.startswith("_")})
    result = Valuer().valuate(request)
    config.FIGURES.mkdir(parents=True, exist_ok=True)
    html_path = config.FIGURES / "sample_report.html"
    html_path.write_text(render(result), encoding="utf-8")
    fig = waterfall_figure(result.steps, result.base_ppsf, "Sample valuation: value drivers (Rs/sqft)")
    fig.savefig(config.FIGURES / "shap_waterfall.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    rendered = screenshot(html_path, config.FIGURES / "sample_report.png")
    summary = {"listing_id": sample["_listing_id"], "listed_price_inr": sample["_listed_price_inr"],
               "point_inr": result.contract["value"]["point_inr"], "grade": result.contract["confidence"]["grade"],
               "routing": result.contract["routing"], "screenshot_rendered": rendered}
    update_metrics(sample_report=summary)
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
