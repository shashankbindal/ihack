"""Streamlit UI. Run from the prototype folder: streamlit run app/streamlit_app.py"""

import json
import sys
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit_folium import st_folium

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config  # noqa: E402
from src.geocode import LOCALITIES_PATH  # noqa: E402
from src.metrics import load_metrics  # noqa: E402
from src.report import render  # noqa: E402
from src.schemas import ValuationRequest  # noqa: E402
from src.valuate import OutOfCoverage, Valuer  # noqa: E402

ASSUMPTION = "Placeholder assumption, not a sourced figure. Replace with the lender's own number."

st.set_page_config(page_title="Property valuation prototype", layout="wide")


@st.cache_resource
def valuer() -> Valuer:
    return Valuer()


@st.cache_data
def localities() -> pd.DataFrame:
    frame = pd.read_parquet(LOCALITIES_PATH)
    known = set(valuer().engine.bank.locality)
    return frame[(frame.geo_precision == "locality") & frame.locality.isin(known)].sort_values("locality")


def pick_location() -> tuple[str, float, float]:
    city = st.selectbox("City", list(config.CITIES))
    options = localities()[localities().city == city]
    name = st.selectbox("Locality (geocoded centroid)", options.locality)
    chosen = options[options.locality == name].iloc[0]
    lat, lon = chosen.lat, chosen.lon
    st.caption("Or click the map to value a specific point.")
    fmap = folium.Map(location=[lat, lon], zoom_start=13)
    folium.Marker([lat, lon], tooltip=name).add_to(fmap)
    clicked = st_folium(fmap, height=320, width=None, key=f"map-{city}-{name}").get("last_clicked")
    if clicked:
        lat, lon = clicked["lat"], clicked["lng"]
        st.caption(f"Using clicked point ({lat:.5f}, {lon:.5f})")
    return city, lat, lon


def valuation_tab() -> None:
    left, right = st.columns([1, 2])
    with left:
        _, lat, lon = pick_location()
        area = st.number_input("Area (sqft, as listed)", 200, 10_000, 1100, step=50)
        bhk = st.selectbox("BHK", [1, 2, 3, 4, 5, 6], index=1)
        resale = st.radio("Sale type", ["Resale", "New"], horizontal=True) == "Resale"
        amenity_names = [a[5:] for a in valuer().amenities]
        stated = st.multiselect("Amenities present (others treated as not stated)", amenity_names)
        floor = st.number_input("Floor (recorded, not used by this model)", 0, 80, 0)
        loan = st.number_input("Requested loan (Rs, optional; drives the policy gate)", 0, 50_00_00_000, 0,
                               step=1_00_000)
        go = st.button("Value property", type="primary")
    with right:
        if not go:
            st.info("Choose a location and attributes, then press Value property.")
            return
        request = ValuationRequest(lat=lat, lon=lon, area_sqft=area, bhk=bhk, resale=resale,
                                   amenities={a: True for a in stated}, floor=floor or None,
                                   loan_amount_inr=loan or None)
        try:
            result = valuer().valuate(request)
        except OutOfCoverage as error:
            st.error(str(error))
            return
        components.html(render(result), height=1500, scrolling=True)
        with st.expander("API JSON"):
            st.json(result.contract)


def routing_tab() -> None:
    metrics = load_metrics()
    curve = pd.DataFrame([p for p in metrics["routing_curve"]["points"] if "mdape_auto" in p])
    st.markdown("Each point auto-accepts every in-distribution valuation whose 80% interval half-width is under "
                "the threshold. Measured on held-out H3 cells (spatial-block CV) against **listing asking prices**.")
    threshold = st.select_slider("Auto-accept if interval half-width <= (%)",
                                 options=curve.threshold_half_width_pct.round(0).tolist(),
                                 value=round(metrics["routing_curve"]["selected"].get("grade_threshold",
                                                                                   curve.threshold_half_width_pct.iloc[0])))
    point = curve.loc[(curve.threshold_half_width_pct.round(0) - threshold).abs().idxmin()]
    cols = st.columns(4)
    cols[0].metric("Auto-accepted share", f"{point.auto_rate:.1f}%")
    cols[1].metric("MdAPE of auto-accepted", f"{point.mdape_auto:.1f}%")
    cols[2].metric("Within +/-10%", f"{point.ppe10_auto:.0f}%")
    cols[3].metric(">20% over-valued", f"{point.overval20_auto:.1f}%")
    st.line_chart(curve.set_index("auto_rate")[["mdape_auto"]], x_label="auto-accepted share (%)",
                  y_label="MdAPE among auto-accepted (%)")
    st.caption(f"Selection rule in metrics.json: {metrics['routing_curve']['selected']['rule']}")
    st.subheader("Grades at default thresholds")
    st.dataframe(pd.DataFrame(metrics["grades"]["by_grade"]).T)
    st.session_state["auto_rate"] = float(point.auto_rate)


def economics_tab() -> None:
    st.markdown("All inputs below are **assumptions** for illustration. Only the auto-accept share comes from "
                "the measured trade-off curve (Routing tab).")
    auto_rate = st.session_state.get("auto_rate", load_metrics()["routing_curve"]["selected"].get("auto_rate", 0.0))
    c1, c2 = st.columns(2)
    with c1:
        volume = st.slider("Valuations per month", 100, 50_000, 1_000, step=100, help=ASSUMPTION)
        physical_cost = st.slider("Cost per physical valuation (Rs)", 0, 20_000, 3_000, step=250, help=ASSUMPTION)
        desktop_cost = st.slider("Cost per desktop review (Rs)", 0, 10_000, 500, step=100, help=ASSUMPTION)
        large_loans = st.slider("Share of loans >= Rs 75 lakh (always physical, two valuers)", 0, 100, 10,
                                help=ASSUMPTION) / 100
    with c2:
        physical_days = st.slider("Physical valuation turnaround (days)", 0.0, 15.0, 5.0, step=0.5, help=ASSUMPTION)
        desktop_days = st.slider("Desktop review turnaround (days)", 0.0, 5.0, 1.0, step=0.5, help=ASSUMPTION)
        desktop_share = st.slider("Of the non-auto cases, share closed by desktop review (%)", 0, 100, 50,
                                  help=ASSUMPTION) / 100
        auto = st.slider("Auto-accept share (%) from the trade-off curve", 0.0, 100.0, float(round(auto_rate, 1)),
                         step=0.5) / 100

    eligible = volume * (1 - large_loans)
    n_auto = eligible * auto
    n_desktop = (eligible - n_auto) * desktop_share
    n_physical = volume - n_auto - n_desktop
    baseline_cost = volume * physical_cost + volume * large_loans * physical_cost
    engine_cost = n_desktop * desktop_cost + n_physical * physical_cost + volume * large_loans * physical_cost
    baseline_days = physical_days
    engine_days = (n_desktop * desktop_days + n_physical * physical_days) / volume

    cols = st.columns(4)
    cols[0].metric("Physical visits avoided / month", f"{volume - n_physical:,.0f}")
    cols[1].metric("Valuation cost saved / month", f"Rs {baseline_cost - engine_cost:,.0f}")
    cols[2].metric("Avg. turnaround", f"{engine_days:.1f} days", f"{engine_days - baseline_days:+.1f} vs all-physical")
    cols[3].metric("Auto-accepted / month", f"{n_auto:,.0f}")
    st.caption("Baseline assumes every case gets one physical valuation, and two for loans >= Rs 75 lakh. "
               "The engine scenario keeps the two-valuer rule and adds no cost per AVM call.")


def main() -> None:
    st.title("AI property valuation prototype")
    st.warning("Trained and evaluated on listing **asking prices** (open Kaggle data, 2020 snapshot), a proxy "
               "for transaction values. Indicative only, not a statutory valuation.")
    tabs = st.tabs(["Valuate", "Routing trade-off", "Economics calculator", "Metrics"])
    with tabs[0]:
        valuation_tab()
    with tabs[1]:
        routing_tab()
    with tabs[2]:
        economics_tab()
    with tabs[3]:
        st.json(json.loads(config.METRICS_PATH.read_text()), expanded=1)


main()
