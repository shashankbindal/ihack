"""Draw every visual asset: the two document figures (architecture.png, lender_workflow.png) and the
transparent 300 dpi pictorial PNGs used by the deck (figures/deck/*.png).

Usage: python -I draw_figs.py OUT_DIR [--metrics PATH] [--report PATH]
"""
import argparse
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from deck_data import (BACKGROUND, BODY_FONT, DEFAULT_METRICS, DEFAULT_REPORT, HEADLINE_FONT, INK, LADDER,
                       LADDER_LABELS, PALETTE, PRUSSIAN, ROUTE_LABELS, ROUTES, STONE, TERRACOTTA, WHITE,
                       Metrics, SampleReport, short_factor)

plt.rcParams["font.family"] = BODY_FONT
plt.rcParams["svg.fonttype"] = "none"

MUTED = INK
RULE = STONE
BAND = WHITE
STATUS_GREEN = (WHITE, PRUSSIAN)
STATUS_AMBER = (BACKGROUND, INK)
STATUS_RED = (WHITE, TERRACOTTA)
C_OFF = (WHITE, PRUSSIAN)
C_ON = (BACKGROUND, PRUSSIAN)
C_GOV = (WHITE, INK)
C_EXT = (WHITE, INK)
SURFACE = BACKGROUND
NAVY = PRUSSIAN
STEEL = PRUSSIAN
TEAL_DARK = PRUSSIAN


def box(ax, x, y, w, h, title, body="", col=C_OFF, tsize=12, bsize=10, lw=1.4):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.8",
                                fc=col[0], ec=col[1], lw=lw, zorder=3))
    if body:
        ax.text(x + w / 2, y + h - 1.0, title, ha="center", va="top", fontsize=tsize,
                fontweight="bold", color=INK, zorder=4)
        ax.text(x + w / 2, y + h - 3.4, body, ha="center", va="top", fontsize=bsize,
                color=INK, zorder=4, linespacing=1.3)
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontsize=tsize,
                fontweight="bold", color=INK, zorder=4)
    return (x, y, w, h)


def arrow(ax, p, q, dashed=False, color=PRUSSIAN, lw=1.6):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=16, lw=lw, color=color,
                                 linestyle=(0, (4, 3)) if dashed else "-", zorder=2.5,
                                 shrinkA=1, shrinkB=1))


def poly(ax, pts, dashed=False, color=PRUSSIAN):
    xs, ys = zip(*pts[:-1])
    ax.plot(xs, ys, color=color, lw=1.6, linestyle=(0, (4, 3)) if dashed else "-", zorder=2.5)
    arrow(ax, pts[-2], pts[-1], dashed=dashed, color=color)


def note(ax, x, y, s, ha="center", size=9.5):
    ax.text(x, y, s, ha=ha, va="center", fontsize=size, color=MUTED, style="italic", zorder=5,
            bbox=dict(fc=BACKGROUND, ec="none", pad=0.8))


def mid_r(b): return (b[0] + b[2], b[1] + b[3] / 2)
def mid_l(b): return (b[0], b[1] + b[3] / 2)
def mid_t(b): return (b[0] + b[2] / 2, b[1] + b[3])
def mid_b(b): return (b[0] + b[2] / 2, b[1])


def strip(ax, y0, y1, label, col):
    ax.add_patch(FancyBboxPatch((2, y0), 4.2, y1 - y0, boxstyle="round,pad=0,rounding_size=0.8",
                                fc=col, ec="none", zorder=1))
    ax.text(4.1, (y0 + y1) / 2, label, rotation=90, ha="center", va="center", fontsize=11.5,
            fontweight="bold", color="white", zorder=2)
    ax.add_patch(FancyBboxPatch((6.6, y0), 151.0, y1 - y0, boxstyle="round,pad=0,rounding_size=0.8",
                                fc=BAND, ec=RULE, lw=1.0, zorder=0.5))


def new_fig(title, legend=None):
    fig = plt.figure(figsize=(16, 9), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 160)
    ax.set_ylim(0, 90)
    ax.axis("off")
    fig.patch.set_facecolor(BACKGROUND)
    ax.text(2, 88, title, fontsize=18, fontweight="bold", color=NAVY, va="top")
    if legend:
        ax.text(158, 87.5, legend, fontsize=10.5, color=MUTED, va="top", ha="right")
    return fig, ax


# ------------------------------------------------------------------ architecture
def architecture():
    fig, ax = new_fig("GharMoolya: system architecture",
                      "Solid: request and data flow     Dashed: feedback loop")

    # ---- offline band
    strip(ax, 63.5, 82, "OFFLINE", C_OFF[1])
    ax.text(9, 81.2, "batch pipeline, monthly retrain", fontsize=10, color=MUTED, style="italic", va="top")
    w, h, y = 22.2, 13.2, 65.2
    xs = [8.5 + i * (w + 2.9) for i in range(6)]
    src = box(ax, xs[0], y, w, h, "Data sources",
              "Lender valuations, collateral\nRERA, circle rates, registry\nOSM, Sentinel-2, footprints\nNHB RESIDEX, RBI HPI")
    ing = box(ax, xs[1], y, w, h, "Ingestion", "Airflow / Prefect DAGs\nper-record lineage:\nsource, date, licence")
    cln = box(ax, xs[2], y, w, h, "Clean and merge", "area basis, dedup, geocode\ntime-adjust to index\nH3 spatial join")
    lake = box(ax, xs[3], y, w, h, "Data lake", "Parquet + PostGIS\nversioned feature tables")
    trn = box(ax, xs[4], y, w, h, "Train and validate",
              "LightGBM + spatial residual\nhedonic shadow model\nconformal calibration\ntime + H3 block CV")
    reg = box(ax, xs[5], y, w, h, "Model registry", "MLflow, model cards\nchampion / challenger\nsign-off before release")
    for a_, b_ in [(src, ing), (ing, cln), (cln, lake), (lake, trn), (trn, reg)]:
        arrow(ax, mid_r(a_), mid_l(b_))

    # ---- between bands: LOS and feature store
    los = box(ax, 8.5, 53.3, 17, 7.4, "Loan origination\nsystem (LOS)", "", C_EXT, tsize=11)
    fs = box(ax, 44, 53.3, 52, 7.4, "Feature store",
             "precomputed per H3 cell: offline Parquet, online Redis", C_OFF, tsize=11.5, bsize=10)
    lx = lake[0] + lake[2] * 0.35
    arrow(ax, (lx, y), (lx, 60.7))

    # ---- online band
    strip(ax, 32, 51.5, "ONLINE", C_ON[1])
    ax.text(84, 50.7, "one valuation request, target p95 under 2 s", fontsize=10, color=MUTED,
            style="italic", va="top")
    w2, h2, y2 = 16.6, 12.2, 34.0
    labels = [
        ("Valuation API", "FastAPI, REST\nproperty attributes\nonly, no PII"),
        ("Validate", "schema checks,\ngeocode, geo-\nprecision flag"),
        ("Feature lookup", "H3 cell features\n+ point distances\nstale-data flag"),
        ("Model service", "M+ point value\nshadow hedonic\nagreement check"),
        ("Confidence", "conformal 80%\ninterval, OOD\nguard, grade A-D"),
        ("Explain", "TreeSHAP drivers\nin Rs/sqft\ncomparables"),
        ("Routing engine", "lender policy\nLTV caps\nloan-size rules"),
        ("Report", "JSON + PDF\nback to LOS and\nunderwriter"),
    ]
    on = []
    for i, (t, b) in enumerate(labels):
        x = 8.5 + i * (w2 + 2.3)
        on.append(box(ax, x, y2, w2, h2, t, b, C_EXT if t == "Report" else C_ON, tsize=11.5, bsize=10))
    for a_, b_ in zip(on[:-1], on[1:]):
        arrow(ax, mid_r(a_), mid_l(b_))
    api, val, feat, mod, conf, xai, rte, rep = on

    arrow(ax, mid_b(los), mid_t(api))
    fx = feat[0] + feat[2] / 2
    arrow(ax, (fx, 53.3), (fx, y2 + h2))
    rx = reg[0] + reg[2] / 2
    mx = mod[0] + mod[2] / 2
    poly(ax, [(rx, y), (rx, 52.2), (mx, 52.2), (mx, y2 + h2)])
    note(ax, rx - 1.5, 57, "deploy approved\nmodel version", ha="right")

    # ---- governance band
    strip(ax, 2, 29.5, "GOVERNANCE", C_GOV[1])
    w3, h3, y3 = 34.3, 12.5, 4
    gx = [8.5 + i * (w3 + 3.25) for i in range(4)]
    aud = box(ax, gx[0], y3, w3, h3, "Immutable audit log",
              "inputs, feature snapshot, model\nversion, SHAP, routing, overrides", C_GOV)
    mon = box(ax, gx[1], y3, w3, h3, "Monitoring",
              "PSI drift, rolling error vs new\nvaluations, coverage by city;\nalert, roll back, kill switch", C_GOV)
    bat = box(ax, gx[2], y3, w3, h3, "Portfolio revaluation",
              "quarterly batch over whole book\nLTV drift, early-warning flags\n(registry model + feature store)", C_GOV)
    hum = box(ax, gx[3], y3, w3, h3, "Valuer and underwriter",
              "desktop review, field visit,\noverride with logged reason", C_GOV)
    arrow(ax, mid_r(aud), mid_l(mon))
    arrow(ax, mid_l(bat), mid_r(mon))

    # routing -> audit
    rtx = rte[0] + rte[2] / 2
    adx = aud[0] + aud[2] / 2
    poly(ax, [(rtx, y2), (rtx, 23.5), (adx, 23.5), (adx, y3 + h3)])
    note(ax, (rtx + adx) / 2, 23.5, "every valuation and decision is logged")
    # report -> human
    rpx = rep[0] + rep[2] / 2
    arrow(ax, (rpx, y2), (rpx, y3 + h3))
    note(ax, rpx - 1.2, 25.5, "DESKTOP_REVIEW\nPHYSICAL_VALUATION", ha="right", size=9)
    # human -> data lake (labels), dashed along right edge
    hx = hum[0] + hum[2]
    lx2 = lake[0] + lake[2] * 0.75
    poly(ax, [(hx, y3 + 6), (158.8, y3 + 6), (158.8, 62.3), (lx2, 62.3), (lx2, y)], dashed=True)
    note(ax, 128, 62.3, "valuer outcomes and overrides become new training labels")

    fig.savefig(OUT / "architecture.png", dpi=200, facecolor=BACKGROUND)
    plt.close(fig)


# ------------------------------------------------------------------ lender workflow
def workflow():
    fig, ax = new_fig("Lender workflow: confidence-based routing and valuation-adjusted LTV")

    app = box(ax, 3, 52, 21, 10, "Application", "KYC and credit\nchecks done", C_EXT)
    gm = box(ax, 29, 50.5, 25, 13, "GharMoolya valuation",
             "value, 80% interval,\ngrade A-D, drivers,\ncomparables", C_ON)
    gate = box(ax, 59, 50.5, 26, 13, "Policy gate",
               "loan >= Rs 75 lakh?\nout-of-distribution?\nLAP / non-residential?", C_OFF)
    arrow(ax, mid_r(app), mid_l(gm))
    arrow(ax, mid_r(gm), mid_l(gate))

    rx, rw, rh = 95, 37, 11.5
    r1 = box(ax, rx, 68, rw, rh, "AUTO_ACCEPT",
             "grade A (B only if policy allows)\nloan below two-report threshold", STATUS_GREEN)
    r2 = box(ax, rx, 51.25, rw, rh, "DESKTOP_REVIEW",
             "grade B / C: valuer checks report,\ncomparables and documents", STATUS_AMBER)
    r3 = box(ax, rx, 34.5, rw, rh, "PHYSICAL_VALUATION",
             "grade D, sparse data, OOD, or loan\n>= Rs 75 lakh (two independent reports)", STATUS_RED)
    for r in (r1, r2, r3):
        arrow(ax, mid_r(gate), mid_l(r))
    ax.text(89.5, 72, "high\nconfidence", fontsize=9.5, color=MUTED, style="italic", ha="center")
    ax.text(87.5, 40, "low confidence\nor rule hit", fontsize=9.5, color=MUTED, style="italic", ha="center")

    ltv = box(ax, 137, 34.5, 21, 45, "LTV and sanction",
              "collateral value\nper rule below\n\nregulatory cap\n(HFC Directions\n2025, by loan size)\n\nup to Rs 30 L: 90%\nRs 30-75 L: 80%\nabove Rs 75 L: 75%",
              C_EXT, tsize=12, bsize=10.5)
    for r in (r1, r2, r3):
        arrow(ax, mid_r(r), (ltv[0], mid_r(r)[1]))

    ax.add_patch(FancyBboxPatch((3, 4), 129, 25, boxstyle="round,pad=0,rounding_size=1.0",
                                fc=SURFACE, ec=RULE, lw=1.0))
    ax.text(5, 27.3, "Valuation-adjusted LTV (illustrative; the lender's credit policy sets the parameters)",
            fontsize=12.5, fontweight="bold", color=MUTED, va="top")
    ax.text(5, 22.6,
            "Collateral value  AUTO_ACCEPT        : AVM lower bound of the 80% interval\n"
            "                  DESKTOP_REVIEW     : reviewed value, capped at AVM point unless justified\n"
            "                  PHYSICAL_VALUATION : valuer value (lower of two reports where required)\n"
            "Max loan        = collateral value x min( regulatory LTV cap, policy LTV for grade )",
            fontsize=11, color=INK, va="top", family="monospace", linespacing=1.6)
    ax.text(5, 6.3, "Uncertainty reduces the loan amount, not the lender's protection. Overrides are logged and fed back as labels.",
            fontsize=10.5, color=MUTED, style="italic", va="center")

    pd = box(ax, 137, 4, 21, 25, "After disbursal",
             "quarterly portfolio\nrevaluation\n\nLTV drift and\nearly-warning flags", C_GOV, tsize=11.5, bsize=10.5)
    arrow(ax, mid_b(ltv), mid_t(pd))

    fig.savefig(OUT / "lender_workflow.png", dpi=200, facecolor=BACKGROUND)
    plt.close(fig)


ZILLOW_ON_MARKET_PCT, ZILLOW_OFF_MARKET_PCT = 2, 7
METRO_COORDS = {"Mumbai": (72.88, 19.08), "Delhi NCR": (77.10, 28.60), "Bengaluru": (77.59, 12.97),
                "Hyderabad": (78.49, 17.39), "Chennai": (80.27, 13.08), "Kolkata": (88.36, 22.57),
                "Pune": (73.86, 18.52), "Ahmedabad": (72.57, 23.02)}
CITY_ALIASES = {"Bangalore": "Bengaluru", "Delhi": "Delhi NCR", "MMR": "Mumbai", "Mumbai (MMR)": "Mumbai"}
LABEL_OFFSETS = {"Mumbai": (-0.12, 0.06, "right"), "Pune": (0.14, -0.1, "left"), "Delhi NCR": (0.14, 0, "left"),
                 "Bengaluru": (-0.14, -0.05, "right"), "Hyderabad": (0.14, 0, "left"), "Chennai": (0.14, 0, "left"),
                 "Kolkata": (0.14, 0, "left"), "Ahmedabad": (0.1, 0.12, "left")}
INDIA_OUTLINE = [(68.2, 23.6), (70.0, 20.8), (72.8, 19.0), (73.8, 15.5), (75.0, 12.5), (76.3, 9.5), (77.5, 8.1),
                 (78.2, 9.0), (79.8, 10.3), (80.2, 13.1), (80.3, 15.7), (82.3, 17.0), (84.9, 19.3), (86.9, 21.2),
                 (88.2, 21.6), (89.0, 22.0), (89.0, 25.5), (89.9, 26.0), (92.0, 26.9), (96.0, 28.0), (97.3, 27.8),
                 (95.2, 26.6), (94.5, 25.2), (93.5, 24.0), (92.5, 22.9), (91.9, 24.4), (90.3, 25.4), (88.1, 26.4),
                 (85.0, 26.8), (84.0, 27.4), (81.0, 28.6), (80.1, 30.0), (78.8, 31.0), (77.8, 32.6), (78.5, 34.5),
                 (77.0, 35.5), (74.5, 35.0), (73.8, 34.0), (74.6, 32.5), (75.4, 32.2), (74.6, 31.0), (73.9, 30.1),
                 (72.7, 28.0), (70.8, 27.7), (69.6, 26.9), (70.2, 25.6), (71.0, 24.3), (68.8, 23.9)]


def canvas(width, height):
    fig = plt.figure(figsize=(width, height), dpi=300)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")
    fig.patch.set_alpha(0)
    return fig, ax


def save(fig, name):
    DECK.mkdir(parents=True, exist_ok=True)
    fig.savefig(DECK / name, dpi=300, transparent=True)
    plt.close(fig)


def label(ax, x, y, text, size=11, color=INK, weight="normal", ha="left", va="center", serif=False, style="normal"):
    ax.text(x, y, text, fontsize=size, color=color, fontweight=weight, ha=ha, va=va, style=style,
            family=HEADLINE_FONT if serif else BODY_FONT, linespacing=1.25)


def badge(ax, x, y, number, radius=0.15, fill=PRUSSIAN, size=10):
    ax.add_patch(Circle((x, y), radius, fc=fill, ec="none", zorder=5))
    ax.text(x, y, str(number), fontsize=size, color=WHITE, ha="center", va="center", fontweight="bold",
            family=BODY_FONT, zorder=6)


def rule(ax, x0, y0, x1, y1, color=INK, width=0.75, dashed=False, zorder=1):
    ax.plot([x0, x1], [y0, y1], color=color, lw=width, linestyle=(0, (3, 2)) if dashed else "-",
            solid_capstyle="butt", zorder=zorder)


def house(ax, x, y, width, face=WHITE, edge=PRUSSIAN, lw=0.9, door=True, zorder=3):
    wall = 0.6 * width
    ax.add_patch(Polygon([(x, y), (x + width, y), (x + width, y + wall), (x + width / 2, y + width),
                          (x, y + wall)], closed=True, fc=face, ec=edge, lw=lw, joinstyle="miter", zorder=zorder))
    if door:
        ax.add_patch(Rectangle((x + width * 0.42, y), width * 0.16, wall * 0.45, fc="none", ec=edge, lw=lw * 0.8,
                               zorder=zorder + 1))


def waffle(ax, x, y, size, percent, fill, empty=STONE):
    cells = round(percent)
    step = size / 10
    for index in range(100):
        row, col = divmod(index, 10)
        ax.add_patch(Rectangle((x + col * step + step * 0.08, y + (9 - row) * step + step * 0.08), step * 0.84,
                               step * 0.84, fc=fill if index < cells else empty, ec="none"))


def largest_remainder(shares, total=100):
    floors = {key: int(math.floor(value)) for key, value in shares.items()}
    remaining = total - sum(floors.values())
    for key in sorted(shares, key=lambda k: shares[k] - floors[k], reverse=True)[:remaining]:
        floors[key] += 1
    return floors


def s1_house():
    fig, ax = canvas(5.2, 5.1)
    rule(ax, 0.2, 0.9, 5.0, 0.9, color=STONE, width=1.0)
    ax.add_patch(Rectangle((0.45, 0.9), 4.3, 3.9, fc="none", ec=STONE, lw=0.9, linestyle=(0, (4, 3))))
    house(ax, 1.15, 0.9, 2.9, face="none", edge=PRUSSIAN, lw=1.6, door=False)
    for wx in (1.55, 3.05):
        ax.add_patch(Rectangle((wx, 1.75), 0.6, 0.5, fc="none", ec=PRUSSIAN, lw=1.1))
    ax.add_patch(Rectangle((2.35, 0.9), 0.5, 0.85, fc="none", ec=PRUSSIAN, lw=1.1))
    save(fig, "s1_house.png")


def s2_houses():
    fig, ax = canvas(7.3, 2.4)
    for i in range(10):
        x = 0.1 + i * 0.72
        house(ax, x, 0.55, 0.5)
        cx, cy = x + 0.5, 1.05
        ax.add_patch(Circle((cx, cy), 0.12, fc=TERRACOTTA, ec="none", zorder=6))
        rule(ax, cx, cy, cx, cy + 0.08, color=WHITE, width=0.9, zorder=7)
        rule(ax, cx, cy, cx + 0.06, cy, color=WHITE, width=0.9, zorder=7)
    label(ax, 0.1, 1.85, "Every file", size=26, serif=True, color=PRUSSIAN)
    label(ax, 2.35, 1.85, "waits for a physical valuation before sanction", size=12)
    label(ax, 0.1, 0.22, "House = one loan file.   Terracotta clock = a valuer visit.", size=10)
    save(fig, "s2_houses.png")


def s2_squares():
    fig, ax = canvas(4.2, 2.75)
    side_off = 1.5
    side_on = side_off * math.sqrt(ZILLOW_ON_MARKET_PCT / ZILLOW_OFF_MARKET_PCT)
    base = 0.75
    ax.add_patch(Rectangle((0.35, base), side_on, side_on, fc=PRUSSIAN, ec="none"))
    ax.add_patch(Rectangle((2.1, base), side_off, side_off, fc=TERRACOTTA, ec="none"))
    label(ax, 0.35, base + side_on + 0.22, f"~{ZILLOW_ON_MARKET_PCT}%", size=20, serif=True, color=PRUSSIAN)
    label(ax, 2.1, base + side_off + 0.22, f"~{ZILLOW_OFF_MARKET_PCT}%", size=20, serif=True, color=TERRACOTTA)
    label(ax, 0.35, base - 0.2, "on-market", size=10.5)
    label(ax, 2.1, base - 0.2, "off-market", size=10.5)
    label(ax, 0.35, 0.18, "Zillow median error, US homes. Area to scale.", size=10, style="italic")
    save(fig, "s2_squares.png")


def grade_reasons(report):
    short = [r.replace("80% interval ", "range ").replace(" training listings", " listings")
             for r in report.reasons[:2]]
    return "\n".join(short) or "see report"


def s3_anatomy(report):
    fig, ax = canvas(8.4, 5.0)
    card_x, card_y, card_w, card_h = 2.95, 1.25, 2.5, 2.6
    ax.add_patch(FancyBboxPatch((card_x, card_y), card_w, card_h, boxstyle="round,pad=0,rounding_size=0.08",
                                fc=WHITE, ec=PRUSSIAN, lw=1.0))
    house(ax, card_x + 0.85, card_y + 1.45, 0.8, face="none", lw=1.1)
    label(ax, card_x + card_w / 2, card_y + 1.05, report.point or "«value»", size=17, serif=True, ha="center",
          color=PRUSSIAN)
    label(ax, card_x + card_w / 2, card_y + 0.62, f"{report.city or '«city»'} sample listing", size=10, ha="center")
    label(ax, card_x + card_w / 2, card_y + 0.3, "indicative AVM output", size=9.5, ha="center", style="italic")
    factor_lines = "\n".join(f"{effect:+,.0f}  {short_factor(name)}" for effect, name in report.factors[:2])
    comparables = f"{report.n_comparables} nearby listings,\nmodel-adjusted" if report.n_comparables else "«comparables»"
    range_text = f"{report.low_text} to\n{report.high_text}" if report.low_text else "«range»"
    items = [("Value", f"{report.point or '«value»'}\n{report.per_sqft or ''}"), ("80% range", range_text),
             ("Grade", f"{report.grade or '«grade»'}: " + grade_reasons(report)),
             ("Top factors, Rs/sqft", factor_lines or "«factors»"), ("Comparables", comparables),
             ("Routing", ROUTE_LABELS.get(report.routing, "«route»"))]
    anchors = [(card_x, card_y + 2.2), (card_x, card_y + 1.3), (card_x, card_y + 0.4),
               (card_x + card_w, card_y + 2.2), (card_x + card_w, card_y + 1.3), (card_x + card_w, card_y + 0.4)]
    rows_y = [4.3, 2.55, 0.8]
    for i, ((head, body), anchor) in enumerate(zip(items, anchors)):
        left = i < 3
        y = rows_y[i % 3]
        bx = 2.55 if left else 5.85
        rule(ax, bx + (0.15 if left else -0.15), y, *anchor, color=INK, width=0.6)
        ax.add_patch(Circle(anchor, 0.035, fc=INK, ec="none", zorder=6))
        badge(ax, bx, y, i + 1, fill=TERRACOTTA if i == 5 else PRUSSIAN)
        tx = bx - 0.25 if left else bx + 0.25
        label(ax, tx, y + 0.18, head, size=11.5, weight="bold", ha="right" if left else "left", va="bottom")
        label(ax, tx, y + 0.12, body, size=10.5, ha="right" if left else "left", va="top")
    save(fig, "s3_anatomy.png")


def s4_timeline(metrics):
    fig, ax = canvas(7.3, 2.6)
    xs = [0.45, 2.25, 4.05, 5.85]
    line_y = 1.95
    rule(ax, xs[0], line_y, xs[1], line_y, color=PRUSSIAN, width=1.4)
    rule(ax, xs[1], line_y, 7.1, line_y, color=PRUSSIAN, width=1.0, dashed=True)
    names = metrics.cities()
    cities = ", ".join(names[:2]) + ",\n" + ", ".join(names[2:]) if len(names) > 2 else ", ".join(names)
    phases = [("Prototype", f"{cities or '«cities»'};\napartments; open\nlistings exist"),
              ("Top 8 metros", "houses, builder\nfloors; densest data,\nbest accuracy"),
              ("Lender footprint", "tier-2 and tier-3;\nplots; circle-rate\nanchored, wider ranges"),
              ("Pan-India", "commercial LAP;\nincome approach,\nseparate model")]
    for i, (x, (head, body)) in enumerate(zip(xs, phases)):
        badge(ax, x, line_y, i, radius=0.2, fill=TERRACOTTA if i == 0 else PRUSSIAN, size=12)
        label(ax, x - 0.2, 1.45, head, size=12, weight="bold")
        label(ax, x - 0.2, 1.2, body, size=10.5, va="top")
    label(ax, xs[0] - 0.2, 2.42, "built", size=10, style="italic", color=TERRACOTTA)
    label(ax, xs[1] - 0.2, 2.42, "planned", size=10, style="italic", color=PRUSSIAN)
    save(fig, "s4_timeline.png")


def s4_india(metrics):
    width, height = 4.5, 5.1
    fig, ax = canvas(width, height)
    lons = [p[0] for p in INDIA_OUTLINE]
    lats = [p[1] for p in INDIA_OUTLINE]
    lon0, lat0 = min(lons), min(lats)
    scale = min((width - 0.3) / (max(lons) - lon0), (height - 1.0) / (max(lats) - lat0))

    def project(lon, lat):
        return 0.15 + (lon - lon0) * scale, 0.85 + (lat - lat0) * scale

    outline = matplotlib.path.Path([project(*p) for p in INDIA_OUTLINE])
    step, lat = 0.75, lat0
    while lat <= max(lats):
        lon = lon0
        while lon <= max(lons):
            point = project(lon, lat)
            if outline.contains_point(point):
                ax.add_patch(Circle(point, 0.022, fc=STONE, ec="none"))
            lon += step
        lat += step
    prototype = {CITY_ALIASES.get(city, city) for city in metrics.cities()}
    for city, (lon, lat) in METRO_COORDS.items():
        point = project(lon, lat)
        is_prototype = city in prototype
        ax.add_patch(Circle(point, 0.09 if is_prototype else 0.06, fc=TERRACOTTA if is_prototype else PRUSSIAN,
                            ec="none", zorder=5))
        dx, dy, ha = LABEL_OFFSETS[city]
        label(ax, point[0] + dx, point[1] + dy, city, size=10, ha=ha, weight="bold" if is_prototype else "normal")
    legend = [(TERRACOTTA, 0.09, "0  prototype cities"), (PRUSSIAN, 0.06, "1  top 8 metros"),
              (STONE, 0.06, "2-3  lender footprint, then pan-India")]
    for i, (color, radius, text) in enumerate(legend):
        y = 0.55 - i * 0.22
        ax.add_patch(Circle((0.25, y), radius, fc=color, ec="none"))
        label(ax, 0.45, y, text, size=10)
    label(ax, width - 0.05, height - 0.1, "schematic, not to scale", size=9.5, ha="right", va="top", style="italic")
    save(fig, "s4_india.png")


def s5_sources():
    fig, ax = canvas(7.6, 3.4)
    groups = [("Structured", [("Lender\nvaluations", False), ("Registry,\ncircle rates", False),
                              ("RERA\nprojects", False), ("Listings", True), ("RESIDEX,\nRBI HPI", False),
                              ("Macro\nseries", False)], 3),
              ("Unstructured", [("Sentinel-2\nimagery", False), ("Street\nimagery", False),
                                ("Deeds, plans\n(OCR)", False)], 2),
              ("Alternative", [("OpenStreetMap", True), ("Building\nfootprints", False),
                               ("Infrastructure\npipeline", False)], 2)]
    cell, radius, x = 1.05, 0.28, 0.0
    for title, items, cols in groups:
        label(ax, x + 0.1, 3.2, title, size=13, serif=True, color=PRUSSIAN)
        rule(ax, x + 0.1, 3.0, x + cols * cell - 0.1, 3.0, color=STONE, width=0.75)
        for index, (name, used) in enumerate(items):
            row, col = divmod(index, cols)
            cx, cy = x + col * cell + cell / 2, 2.5 - row * 1.25
            ax.add_patch(Circle((cx, cy), radius, fc=TERRACOTTA if used else BACKGROUND,
                                ec=TERRACOTTA if used else STONE, lw=2.2))
            label(ax, cx, cy - radius - 0.08, name, size=10, ha="center", va="top")
        x += cols * cell + 0.15
    save(fig, "s5_sources.png")


def s6_lollipop(metrics):
    fig, ax = canvas(7.3, 3.5)
    label(ax, 0.0, 3.4, "Used in the prototype: property, location, OSM access.", size=9.5, style="italic")
    label(ax, 0.0, 3.2, "Designed for production: neighbourhood imagery, RERA, market and time, infrastructure, "
          "circle-rate anchors.", size=9.5, style="italic")
    x0, x1, vmax = 2.0, 6.7, 30

    def to_x(value):
        return x0 + (x1 - x0) * value / vmax

    for i, key in enumerate(LADDER):
        y = 2.95 - i * 0.42
        label(ax, x0 - 0.15, y, LADDER_LABELS[key], size=10.5, ha="right", weight="bold" if key == "M+" else "normal")
        value = metrics.number("models", key, "mdape")
        if value is None:
            if key == "M" and metrics.not_run("M_imagery_model"):
                label(ax, x0 + 0.05, y, "not run: no imagery in the prototype", size=10, style="italic")
            else:
                metrics.placeholder(f"{key} MdAPE")
                label(ax, x0 + 0.05, y, "«from metrics.json»", size=10, style="italic", color=TERRACOTTA)
            continue
        rule(ax, x0, y, x1, y, color=STONE, width=0.6)
        color = TERRACOTTA if key == "M+" else PRUSSIAN
        rule(ax, x0, y, to_x(value), y, color=color, width=1.4, zorder=3)
        ax.add_patch(Circle((to_x(value), y), 0.07, fc=color, ec="none", zorder=4))
        label(ax, to_x(value) + 0.13, y, f"{value:.1f}%", size=10.5, color=color, weight="bold")
        seen = metrics.number("seen_locality", "models", key, "mdape")
        if key == "M+" and seen is not None:
            ax.add_patch(Circle((to_x(seen), y), 0.07, fc=BACKGROUND, ec=TERRACOTTA, lw=1.2, zorder=5))
            label(ax, to_x(seen), y - 0.17, f"{seen:.1f}% if the locality was seen", size=9.5, ha="center",
                  va="top", color=TERRACOTTA)
    axis_y = 0.3
    rule(ax, x0, axis_y, x1, axis_y, color=INK, width=0.6)
    for tick in range(0, vmax + 1, 5):
        rule(ax, to_x(tick), axis_y, to_x(tick), axis_y - 0.05, color=INK, width=0.6)
        label(ax, to_x(tick), axis_y - 0.12, f"{tick}%", size=9.5, ha="center", va="top")
    label(ax, x0 - 0.15, axis_y, "MdAPE, unseen H3 cells", size=10, ha="right", style="italic")
    save(fig, "s6_lollipop.png")


def waffle_figure(name, percent, fill, caption):
    fig, ax = canvas(2.3, 2.75)
    if percent is None:
        label(ax, 1.15, 1.6, "«from metrics.json»", size=10, ha="center", style="italic")
    else:
        waffle(ax, 0.05, 0.6, 2.2, percent, fill)
    label(ax, 0.05, 0.3, caption, size=10.5)
    save(fig, name)


def s5_funnel(metrics):
    fig, ax = canvas(7.6, 0.8)
    counts = metrics.get("data", "row_counts_by_step") or {}
    steps = [("raw", "raw listings"), ("amenities_stated", "amenities stated"), ("deduplicated", "deduplicated"),
             ("geocoded", "geocoded, modelled")]
    width = 7.6 / len(steps)
    for i, (key, name) in enumerate(steps):
        total = (counts.get(key) or {}).get("total")
        x = i * width
        label(ax, x, 0.55, f"{total:,}" if total is not None else "«metrics»", size=16, serif=True,
              color=TERRACOTTA if key == "geocoded" else PRUSSIAN)
        label(ax, x, 0.18, name, size=10)
        if i:
            label(ax, x - 0.28, 0.55, "→", size=14, ha="center")
    save(fig, "s5_funnel.png")


def s6_iaao(metrics):
    fig, ax = canvas(4.4, 2.1)
    rows = [("COD", metrics.number("models", "M+", "cod"), 0, 50, (5, 15), "IAAO 5 to 15", "{:.1f}"),
            ("PRD", metrics.number("models", "M+", "prd"), 0.9, 1.2, (0.98, 1.03), "IAAO 0.98 to 1.03", "{:.3f}")]
    for i, (name, value, lo, hi, band, band_label, pattern) in enumerate(rows):
        y = 1.55 - i * 1.0
        label(ax, 0.0, y + 0.08, pattern.format(value) if value is not None else "«metrics»", size=22, serif=True,
              color=TERRACOTTA)
        label(ax, 0.0, y - 0.3, f"M+ {name}", size=10.5)
        bar_x0, bar_x1 = 1.5, 4.25

        def to_x(v):
            return bar_x0 + (bar_x1 - bar_x0) * (v - lo) / (hi - lo)

        rule(ax, bar_x0, y, bar_x1, y, color=INK, width=0.6)
        ax.add_patch(Rectangle((to_x(band[0]), y - 0.07), to_x(band[1]) - to_x(band[0]), 0.14, fc=STONE, ec="none"))
        label(ax, to_x(band[0]), y - 0.25, band_label, size=9.5)
        if value is not None:
            ax.add_patch(Circle((to_x(min(max(value, lo), hi)), y), 0.07, fc=TERRACOTTA, ec="none", zorder=4))
        label(ax, bar_x0, y + 0.22, f"{lo:g}", size=9, ha="center")
        label(ax, bar_x1, y + 0.22, f"{hi:g}", size=9, ha="center")
    save(fig, "s6_iaao.png")


def s7_drivers(report):
    fig, ax = canvas(6.4, 4.5)
    factors = report.factors[:5]
    if not factors:
        label(ax, 3.2, 2.2, "«drivers: from sample_report.html»", size=11, ha="center")
        save(fig, "s7_drivers.png")
        return
    one_sided = all(effect >= 0 for effect, _ in factors)
    zero, half = (2.9, 2.6) if one_sided else (4.5, 1.6)
    biggest = max(abs(effect) for effect, _ in factors)
    rule(ax, zero, 0.55, zero, 4.3, color=INK, width=0.75)
    for i, (effect, name) in enumerate(factors):
        y = 3.95 - i * 0.72
        length = half * effect / biggest
        color = TERRACOTTA if effect < 0 else PRUSSIAN
        ax.add_patch(Rectangle((zero + min(length, 0), y - 0.17), abs(length), 0.34, fc=color, ec="none"))
        label(ax, zero + length + (-0.08 if effect < 0 else 0.08), y, f"{effect:+,.0f}", size=11, color=color,
              weight="bold", ha="right" if effect < 0 else "left")
        label(ax, 0.0, y, short_factor(name), size=10.5)
    if not one_sided:
        label(ax, zero - 0.1, 0.3, "lowers value", size=10, ha="right", color=TERRACOTTA)
    label(ax, zero + 0.1, 0.3, "raises value", size=10, color=PRUSSIAN)
    save(fig, "s7_drivers.png")


def s7_grades():
    fig, ax = canvas(5.0, 1.55)
    grades = [("A", "±8%", "auto*", PRUSSIAN, PRUSSIAN, WHITE), ("B", "±12%", "auto*" + chr(10) + "or desk", WHITE, PRUSSIAN, PRUSSIAN),
              ("C", "±20%", "desk", STONE, STONE, INK), ("D", "wider", "field", WHITE, TERRACOTTA, TERRACOTTA)]
    for i, (grade, rule_text, route, face, edge, text_color) in enumerate(grades):
        cx = 0.45 + i * 1.25
        ax.add_patch(Circle((cx, 1.0), 0.32, fc=face, ec=edge, lw=1.4))
        label(ax, cx, 1.0, grade, size=16, serif=True, ha="center", color=text_color)
        label(ax, cx + 0.42, 1.12, rule_text, size=10.5, weight="bold")
        label(ax, cx + 0.42, 0.86, route, size=10.5)
    label(ax, 0.13, 0.25, "*auto only if Board policy allows and the loan is under Rs 75 lakh", size=9.5,
          style="italic")
    save(fig, "s7_grades.png")


def s8_architecture():
    fig, ax = canvas(8.6, 4.9)
    lanes = [("OFFLINE", 4.0, ["Data sources", "Clean + merge", "Train + validate", "Model registry"]),
             ("ONLINE", 2.45, ["Valuation API", "H3 features", "Model + range", "Explain", "Route", "Report"]),
             ("GOVERNANCE", 0.9, ["Audit log", "Monitoring", "Book revaluation", "Valuers"])]
    x0, x1, number, boxes = 1.15, 8.4, 1, {}
    for lane, y, names in lanes:
        label(ax, 0.0, y, lane, size=9.5, weight="bold", color=PRUSSIAN)
        rule(ax, 0.0, y - 0.55, 8.4, y - 0.55, color=STONE, width=0.6)
        gap = 0.18
        width = (x1 - x0 - gap * (len(names) - 1)) / len(names)
        for i, name in enumerate(names):
            bx = x0 + i * (width + gap)
            ax.add_patch(FancyBboxPatch((bx, y - 0.3), width, 0.6, boxstyle="round,pad=0,rounding_size=0.05",
                                        fc=WHITE, ec=PRUSSIAN, lw=0.8, zorder=2))
            badge(ax, bx, y + 0.3, number, radius=0.13, size=8.5,
                  fill=TERRACOTTA if name in ("Route", "Valuers") else PRUSSIAN)
            label(ax, bx + width / 2, y, name, size=10, ha="center")
            if i:
                rule(ax, bx - gap, y, bx, y, color=INK, width=0.75)
            boxes[name] = (bx, y, width)
            number += 1

    def centre(name, side):
        bx, y, width = boxes[name]
        return bx + width / 2, y + (0.3 if side == "top" else -0.3)

    for upper, lower in [("Clean + merge", "H3 features"), ("Model registry", "Model + range"),
                         ("Route", "Audit log"), ("Report", "Valuers")]:
        (ux, uy), (lx, ly) = centre(upper, "bottom"), centre(lower, "top")
        mid = (uy + ly) / 2 + 0.05
        rule(ax, ux, uy, ux, mid)
        rule(ax, ux, mid, lx, mid)
        rule(ax, lx, mid, lx, ly + 0.14)
    vx, vy = centre("Valuers", "bottom")
    sx, sy = centre("Data sources", "top")
    for segment in [(vx, vy, vx, 0.12), (vx, 0.12, 8.55, 0.12), (8.55, 0.12, 8.55, 4.6), (8.55, 4.6, sx, 4.6),
                    (sx, 4.6, sx, sy + 0.14)]:
        rule(ax, *segment, color=TERRACOTTA, width=0.9, dashed=True)
    label(ax, 4.6, 4.75, "valuer outcomes and overrides become training labels", size=9.5, ha="center",
          style="italic", color=TERRACOTTA)
    save(fig, "s8_architecture.png")


def s8_latency(metrics):
    fig, ax = canvas(3.2, 1.9)
    p95 = metrics.number("latency", "p95_ms")
    label(ax, 0.0, 1.5, f"{p95:.0f} ms" if p95 is not None else "«p95: metrics.json»", size=28, serif=True,
          color=PRUSSIAN)
    x0, x1, y, target = 0.05, 3.05, 0.75, 2000
    ax.add_patch(Rectangle((x0, y - 0.05), x1 - x0, 0.1, fc=STONE, ec="none"))
    if p95 is not None:
        ax.add_patch(Rectangle((x0, y - 0.05), (x1 - x0) * min(p95, target) / target, 0.1, fc=TERRACOTTA,
                               ec="none"))
    rule(ax, x1, y - 0.15, x1, y + 0.15, color=INK, width=0.9)
    label(ax, x0, y - 0.3, "p95 per valuation, prototype", size=10)
    label(ax, x1, y + 0.3, "2 s target", size=10, ha="right")
    save(fig, "s8_latency.png")


def s9_isotype(metrics):
    fig, ax = canvas(4.75, 3.5)
    shares = metrics.routing_shares()
    if not shares:
        label(ax, 2.1, 1.8, "«routing shares: from metrics.json»", size=11, ha="center")
        save(fig, "s9_isotype.png")
        return
    counts = largest_remainder(shares)
    colors = {"AUTO_ACCEPT": PRUSSIAN, "DESKTOP_REVIEW": STONE, "PHYSICAL_VALUATION": TERRACOTTA}
    sequence = [route for route in ROUTES for _ in range(counts[route])]
    cell = 0.25
    for index, route in enumerate(sequence):
        row, col = divmod(index, 10)
        house(ax, 0.08 + col * cell, 3.28 - (row + 1) * cell, cell * 0.78, face=colors[route],
              edge=colors[route], lw=0.3, door=False)
    label(ax, 2.7, 0.95, "1 house = 1% of held-out homes", size=9.5, style="italic")
    for i, route in enumerate(ROUTES):
        y = 0.62 - i * 0.24
        house(ax, 2.7, y - 0.08, 0.16, face=colors[route], edge=colors[route], lw=0.4, door=False)
        label(ax, 2.95, y, f"{shares[route]:.1f}%  {ROUTE_LABELS[route]}", size=10)
    save(fig, "s9_isotype.png")


def s9_workflow():
    fig, ax = canvas(12.1, 1.45)
    steps = [("Application", "KYC and bureau done"), ("Valuation", "value, range, grade"),
             ("Policy gate", "Rs 75 lakh+: two valuers"), ("Route", "auto, desk or field"),
             ("LTV", "lower bound, then cap"), ("Monitor", "quarterly book revaluation")]
    step = 12.1 / len(steps)
    y = 1.1
    rule(ax, 0.2, y, 0.2 + step * (len(steps) - 1), y)
    for i, (head, body) in enumerate(steps):
        x = 0.2 + i * step
        badge(ax, x, y, i + 1, radius=0.17, fill=TERRACOTTA if head == "Policy gate" else PRUSSIAN, size=11)
        label(ax, x - 0.17, 0.68, head, size=12, weight="bold")
        label(ax, x - 0.17, 0.38, body, size=10.5)
    save(fig, "s9_workflow.png")


def s10_gantt():
    fig, ax = canvas(7.6, 2.8)
    weeks, x0, x1 = 34, 2.3, 7.4

    def to_x(week):
        return x0 + (x1 - x0) * week / weeks

    phases = [("Onboard", 0, 6, "4-6 wk"), ("Shadow", 6, 18, "8-12 wk"), ("Assist", 18, 26, "8 wk"),
              ("Limited auto", 26, weeks, "ongoing")]
    for i, (name, start, end, duration) in enumerate(phases):
        y = 2.35 - i * 0.55
        color = TERRACOTTA if i == 3 else PRUSSIAN
        badge(ax, 0.2, y, i, radius=0.15, fill=color)
        label(ax, 0.45, y, name, size=11.5, weight="bold")
        ax.add_patch(Rectangle((to_x(start), y - 0.13), to_x(end) - to_x(start), 0.26, fc="none", ec=color, lw=1.1))
        label(ax, to_x(start) + 0.08, y, duration, size=10, color=color)
    rule(ax, x0, 0.45, x1, 0.45, width=0.6)
    for tick in range(0, weeks + 1, 6):
        rule(ax, to_x(tick), 0.38, to_x(tick), 0.45, width=0.6)
        label(ax, to_x(tick), 0.25, str(tick), size=9, ha="center")
    label(ax, x0, 0.05, "weeks, upper bound of each phase", size=9.5, style="italic")
    save(fig, "s10_gantt.png")


def s10_risks():
    fig, ax = canvas(4.1, 3.0)
    x0, y0, size = 0.4, 0.45, 2.45
    rule(ax, x0, y0, x0 + size, y0)
    rule(ax, x0, y0, x0, y0 + size)
    rule(ax, x0 + size / 2, y0, x0 + size / 2, y0 + size, color=STONE)
    rule(ax, x0, y0 + size / 2, x0 + size, y0 + size / 2, color=STONE)
    label(ax, x0 + size, y0 - 0.15, "likelihood", size=9.5, ha="right")
    ax.text(x0 - 0.17, y0 + size, "impact", fontsize=9.5, rotation=90, ha="center", va="top", family=BODY_FONT,
            color=INK)
    risks = [("Asking-price labels", 0.62, 0.88), ("Thin markets", 0.62, 0.66), ("Over-valuation", 0.06, 0.88),
             ("Inflated" + chr(10) + "attributes", 0.06, 0.3)]
    for name, lx, ly in risks:
        px, py = x0 + lx * size, y0 + ly * size
        ax.add_patch(Circle((px, py), 0.06, fc=TERRACOTTA, ec="none"))
        label(ax, px + 0.1, py, name, size=9.5)
    label(ax, x0, 0.1, "qualitative team assessment", size=9, style="italic", va="bottom")
    save(fig, "s10_risks.png")


def deck_assets(metrics, report):
    for draw in (s2_houses, s2_squares, s5_sources, s7_grades, s8_architecture, s9_workflow, s10_gantt, s10_risks):
        draw()
    s1_house()
    for draw in (s3_anatomy, s7_drivers):
        draw(report)
    for draw in (s4_timeline, s4_india, s5_funnel, s6_lollipop, s6_iaao, s8_latency, s9_isotype):
        draw(metrics)
    coverage = metrics.number("coverage_80", "overall", "coverage")
    waffle_figure("s7_waffle.png", coverage, PRUSSIAN,
                  f"{coverage:.1f}% inside the 80% range" if coverage is not None else "80% range coverage")


def palette_issues(tolerance=0.03):
    from PIL import Image
    targets = [tuple(int(color[i:i + 2], 16) for i in (1, 3, 5)) for color in PALETTE]
    issues = []
    for path in sorted(DECK.glob("*.png")):
        pixels = [p[:3] for p in Image.open(path).convert("RGBA").getdata() if p[3] >= 250]
        off = sum(1 for p in pixels if min(sum((a - b) ** 2 for a, b in zip(p, t)) for t in targets) > 40 ** 2)
        if pixels and off / len(pixels) > tolerance:
            issues.append(f"{path.name}: {off / len(pixels):.1%} of opaque pixels outside the palette")
    return issues


def main():
    global OUT, DECK
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out_dir", nargs="?", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--metrics", default=DEFAULT_METRICS)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    args = parser.parse_args()
    OUT = Path(args.out_dir)
    DECK = OUT / "deck"
    architecture()
    workflow()
    deck_assets(Metrics(args.metrics), SampleReport(args.report))
    issues = palette_issues()
    for issue in issues:
        print(f"PALETTE FAIL: {issue}")
    if issues:
        raise SystemExit(1)
    print(f"Drew figures in {OUT} and {DECK}; palette check passed")


if __name__ == "__main__":
    main()
