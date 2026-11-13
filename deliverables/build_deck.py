"""Build the GharMoolya pitch deck (10 slides, editorial print style) from the pictorial assets in
figures/deck/, prototype/results/metrics.json and the prototype's sample_report.html.

Every result number is read from those files at build time; a missing value shows as a visible
«... from metrics.json» placeholder. The build fails if the layout QA finds a problem.
Run figures/draw_figs.py first (fill_deck.py does both).

Usage: python build_deck.py [--metrics PATH] [--report PATH] [--out PATH]
"""
import argparse
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from lxml import etree
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

from deck_data import (BACKGROUND, BODY_FONT, DECK_FIGURES, DEFAULT_METRICS, DEFAULT_REPORT, DELIVERABLES,
                       HEADLINE_FONT, INK, PALETTE, PRUSSIAN, STONE, TERRACOTTA, WHITE, Metrics, SampleReport)

DEFAULT_OUT = DELIVERABLES / "deck.pptx"
SLIDE_W, SLIDE_H = 13.333, 7.5
MARGIN = 0.6
CONTENT_W = SLIDE_W - 2 * MARGIN
KICKER_Y, HEADER_RULE_Y = 0.3, 0.66
TITLE_Y, TITLE_H = 0.78, 0.72
CONTENT_TOP, CONTENT_BOTTOM = 1.6, 6.88
FOOTER_RULE_Y, FOOTER_Y, FOOTER_H = 6.98, 7.03, 0.3
TOTAL_SLIDES = 10
FOOTER_LABEL = "Hero Housing Fintech Challenge 2026 · PS1"
REPO_URL, REPO_LABEL = "https://github.com/shashankbindal/ihack", "github.com/shashankbindal/ihack"
DEMO_URL, DEMO_LABEL = "https://ihack.shashankbindal.me", "ihack.shashankbindal.me"
MAX_WORDS, MIN_WORDS = 110, 50
MIN_PT = {"title": 12, "content": 12, "chrome": 9, "source": 9}
COUNTED_ROLES = ("title", "content")


def rgb(hex_color):
    return RGBColor.from_string(hex_color.lstrip("#"))


C_BG, C_INK, C_BLUE, C_TERRA, C_STONE, C_WHITE = (rgb(c) for c in (BACKGROUND, INK, PRUSSIAN, TERRACOTTA,
                                                                    STONE, WHITE))
ALLOWED_COLORS = {c.lstrip("#").upper() for c in PALETTE}


def name_shape(shape, role):
    shape.name = f"{role}:{shape.shape_id}"
    return shape


def text(slide, x, y, w, h, paragraphs, size=13, color=C_INK, serif=False, italic=False, bold=False,
         align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.1, space_after=4, role="content", small_caps=False):
    """paragraphs: str or list of str / list of runs; a run is (text, {"bold", "color", "size", "serif", "italic"})."""
    box = name_shape(slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)), role)
    frame = box.text_frame
    frame.word_wrap = True
    frame.vertical_anchor = anchor
    frame.margin_left = frame.margin_right = Inches(0)
    frame.margin_top = frame.margin_bottom = Inches(0.02)
    for index, para in enumerate([paragraphs] if isinstance(paragraphs, str) else paragraphs):
        p = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        p.space_after = Pt(space_after)
        for run_text, style in ([(para, {})] if isinstance(para, str) else para):
            run = p.add_run()
            run.text = run_text
            run.font.name = HEADLINE_FONT if style.get("serif", serif) else BODY_FONT
            run.font.size = Pt(style.get("size", size))
            run.font.bold = style.get("bold", bold)
            run.font.italic = style.get("italic", italic)
            run.font.color.rgb = style.get("color", color)
            if style.get("link"):
                run.hyperlink.address = style["link"]
                run.font.underline = True
            if small_caps:
                run.font._rPr.set("cap", "small")
                run.font._rPr.set("spc", "120")
    return box


def hairline(slide, x0, y0, x1, y1, color=C_STONE, role="chrome"):
    line = name_shape(slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x0), Inches(y0), Inches(x1),
                                                 Inches(y1)), role)
    line.line.color.rgb = color
    line.line.width = Pt(0.75)
    style = line._element.find(qn("p:style"))
    if style is not None:
        line._element.remove(style)
    return line


def picture(slide, name, x, y, w, h):
    path = DECK_FIGURES / name
    if not path.exists():
        return text(slide, x, y, w, h, f"«figure missing: {name}»", size=12, color=C_TERRA,
                    align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    img_w, img_h = Image.open(path).size
    scale = min(w / img_w, h / img_h)
    pic_w, pic_h = img_w * scale, img_h * scale
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y + (h - pic_h) / 2), Inches(pic_w), Inches(pic_h))
    return name_shape(pic, "image")


def new_slide(prs, number, kicker, title=None, source=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = C_BG
    text(slide, MARGIN, KICKER_Y, 8.5, 0.3, kicker, size=10, color=C_BLUE, bold=True, role="chrome",
         small_caps=True, anchor=MSO_ANCHOR.MIDDLE)
    text(slide, SLIDE_W - MARGIN - 3, KICKER_Y, 3, 0.3, "GharMoolya", size=12, color=C_TERRA, serif=True,
         italic=True, align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE, role="chrome")
    hairline(slide, MARGIN, HEADER_RULE_Y, SLIDE_W - MARGIN, HEADER_RULE_Y)
    if title:
        text(slide, MARGIN, TITLE_Y, CONTENT_W, TITLE_H, title, size=28, serif=True, anchor=MSO_ANCHOR.MIDDLE,
             role="title")
    hairline(slide, MARGIN, FOOTER_RULE_Y, SLIDE_W - MARGIN, FOOTER_RULE_Y)
    text(slide, MARGIN, FOOTER_Y, 3.0, FOOTER_H, FOOTER_LABEL, size=9, role="chrome")
    if source:
        text(slide, MARGIN + 3.1, FOOTER_Y, 7.4, FOOTER_H, source, size=9, italic=True, align=PP_ALIGN.CENTER,
             role="source")
    text(slide, SLIDE_W - MARGIN - 1.0, FOOTER_Y, 1.0, FOOTER_H, f"{number} / {TOTAL_SLIDES}", size=9,
         align=PP_ALIGN.RIGHT, role="chrome")
    return slide


def set_link_colours(prs):
    theme = prs.slide_masters[0].part.part_related_by(RT.THEME)
    root = etree.fromstring(theme.blob)
    namespace = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
    for tag in ("hlink", "folHlink"):
        for node in root.xpath(f"//a:clrScheme/a:{tag}", namespaces=namespace):
            for child in list(node):
                node.remove(child)
            etree.SubElement(node, f"{{{namespace['a']}}}srgbClr", val=PRUSSIAN.lstrip("#"))
    theme._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def set_notes(slide, notes):
    slide.notes_slide.notes_text_frame.text = " ".join(notes.split())


def link_runs(url, label):
    return [("↗ ", {"color": C_TERRA, "bold": True}), (label, {"color": C_BLUE, "link": url})]


def points(slide, x, y, w, h, items, heading=None, size=12, space_after=7):
    paragraphs = [[(heading, {"serif": True, "size": 15, "color": C_BLUE})]] if heading else []
    paragraphs += [[(lead + " ", {"bold": True, "color": C_BLUE}), (body, {})] for lead, body in items]
    return text(slide, x, y, w, h, paragraphs, size=size, space_after=space_after)


def panel(slide, x, y, w, h, accent=C_TERRA):
    box = name_shape(slide.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(h)), "panel")
    box.shadow.inherit = False
    box.fill.solid()
    box.fill.fore_color.rgb = C_WHITE
    box.line.color.rgb = C_STONE
    box.line.width = Pt(0.75)
    hairline(slide, x, y, x, y + h, color=accent, role="panel")
    return box


def pct(value, digits=1):
    return f"{value:.{digits}f}%"


def number_or_placeholder(m, *keys, label, pattern="{:.1f}%"):
    return m.fmt(*keys, label=label, pattern=pattern)


def sig_text(m, other):
    sig = m.significance(other)
    if not sig:
        return m.placeholder(f"M+ vs {other}")
    low, high = sig["ci95"]
    return f"{sig['delta_mdape']:+.2f} pts (95% CI {low:.2f} to {high:.2f})"


def per_city_text(m):
    rows = [(c, m.number("per_city", c, "M+", "mdape")) for c in m.cities()]
    rows = sorted([r for r in rows if r[1] is not None], key=lambda r: r[1])
    if not rows:
        return m.placeholder("per-city MdAPE")
    return ", ".join(f"{c} {v:.1f}%" for c, v in rows)


def coverage_by_city(m):
    rows = [(c, m.number("coverage_80", "per_city", c, "coverage")) for c in m.cities()]
    rows = sorted([r for r in rows if r[1] is not None], key=lambda r: -r[1])
    return ", ".join(f"{c} {v:.1f}%" for c, v in rows) or m.placeholder("coverage by city")


def amenity_spread_ratio(m):
    evidence = m.get("data", "amenity_missing_evidence") or {}
    ratios = [v["log_ppsf_spread_all_missing"] / v["log_ppsf_spread_complete"] for v in evidence.values()
              if v.get("log_ppsf_spread_complete")]
    return f"{min(ratios):.1f} to {max(ratios):.1f} times" if ratios else m.placeholder("amenity spread ratio")


def routing_numbers(m):
    shares = m.routing_shares() or {}
    seen = m.get("routing_curve_seen_locality", "selected") or {}
    unseen = m.get("routing_curve", "selected") or {}
    return shares, seen, unseen


def slide_title(prs, m, report):
    slide = new_slide(prs, 1, "Hero Housing Fintech Challenge 2026 · Problem Statement 1")
    text(slide, MARGIN, 1.75, 6.7, 1.2, "GharMoolya", size=60, serif=True, color=C_BLUE, role="title",
         anchor=MSO_ANCHOR.MIDDLE)
    text(slide, MARGIN, 2.95, 6.7, 0.75, "AI-Powered Digital Property Valuation Engine for India", size=19,
         serif=True, italic=True)
    text(slide, MARGIN, 3.85, 6.3, 1.2, "A value, a measured range and a routing decision in seconds, built to "
         "work inside RBI's valuation rules.", size=18, spacing=1.15)
    hairline(slide, MARGIN, 5.25, MARGIN + 1.0, 5.25, color=C_TERRA, role="content")
    text(slide, MARGIN, 5.4, 6.3, 0.4, "Team Neural Knights", size=16, serif=True, color=C_BLUE)
    text(slide, MARGIN, 5.85, 6.3, 0.4, "Shashank · Yatin Allan S · Nimit Jain", size=14)
    text(slide, MARGIN, 6.3, 6.6, 0.4, [link_runs(REPO_URL, REPO_LABEL) + [("     ", {})]
                                        + link_runs(DEMO_URL, DEMO_LABEL)], size=12)
    picture(slide, "s1_house.png", 7.53, 1.7, 5.2, 5.1)
    set_notes(slide, """
        Good morning. We are Team Neural Knights: Shashank, Yatin Allan S and Nimit Jain. We are presenting
        GharMoolya for Problem Statement 1, a digital property valuation engine for Indian home loans and LAP.
        For every loan file it returns a value, an eighty percent range whose hit rate we measure, a confidence
        grade from A to D, the main value drivers, nearby comparables and a routing decision, in seconds. It is
        designed to sit inside Hero Housing's Board-approved valuation policy and RBI's HFC Directions, not
        around them. The next nine slides follow the six points in the brief, in order, and end with a pilot plan.
        Every result number comes from our prototype's metrics file, built on four cities of open listing data,
        and we will be explicit about what that data can and cannot prove.""")


def slide_problem(prs, m, report):
    slide = new_slide(prs, 2, "Problem and opportunity", "Every loan file waits for a site visit",
                      "[R12] Zillow, Oct 2026. [R14] RBI HFC Directions 2025, Annex V. House row is illustrative.")
    picture(slide, "s2_houses.png", MARGIN, 1.6, 7.3, 2.4)
    picture(slide, "s2_squares.png", MARGIN, 4.1, 4.2, 2.75)
    panel(slide, 5.05, 4.3, 2.85, 1.75)
    text(slide, 5.25, 4.4, 2.55, 1.6, [[("The opportunity", {"serif": True, "size": 15, "color": C_BLUE})],
                                     "Triage every file in seconds, send only uncertain cases to a valuer, and "
                                     "revalue the whole book each quarter."], size=12, space_after=6)
    points(slide, 8.3, 1.65, 4.43, 5.2, [
        ("Cost.", "A valuer fee on nearly every home loan and LAP file; we take Hero Housing's own fee as input."),
        ("Delay.", "The visit and report sit between login and sanction."),
        ("Variance.", "Two valuers can disagree on one flat. From Rs 75 lakh, RBI requires two reports and the lower "
                      "value sets the loan [R14]."),
        ("India gaps.", "No open national transaction data; listings mix carpet, built-up and super built-up area; "
                        "asking prices sit above registered values.")], heading="Why it hurts")
    set_notes(slide, """
        Collateral value drives the loan amount through LTV caps, the risk grade and later the provisioning view.
        Today nearly every file waits for an empanelled valuer, which costs a fee, adds days between login and
        sanction, and produces numbers that vary between valuers. RBI already recognises that variance: from Rs 75
        lakh the HFC Directions require two independent reports and the lower value is used. We deliberately do
        not quote a fee or a turnaround figure; our economics calculator takes Hero Housing's own numbers.
        Automated valuation works in the US, where Zillow reports about two percent median error on-market and
        seven percent off-market, drawn to scale here, but that rests on dense public records. India has no open
        transaction database, mixes three area definitions and publishes asking prices above registered values.
        The opportunity is triage: answer most files in seconds, send only the uncertain ones to a valuer, and
        revalue the whole book every quarter.""")


def slide_solution(prs, m, report):
    slide = new_slide(prs, 3, "Solution at a glance", "Anatomy of a valuation",
                      "Values from the prototype's sample_report.html, trained on asking prices. Not a statutory "
                      "valuation.")
    picture(slide, "s3_anatomy.png", MARGIN, 1.6, 8.0, 4.76)
    city, grade = report.city or "sample", report.grade or "a low grade"
    text(slide, MARGIN, 6.42, 8.0, 0.4, f"Hard case: the engine grades this {city} listing {grade} and sends it "
         "to a valuer.", size=12, italic=True, color=C_TERRA)
    points(slide, 8.85, 1.65, 3.88, 3.0, [
        ("Value", "point estimate in Rs and Rs/sqft"), ("80% range", "conformal interval, hit rate measured"),
        ("Grade A-D", "range width, comparables, data quality"), ("Top factors", "TreeSHAP drivers in Rs/sqft"),
        ("Comparables", "nearby listings, model-adjusted"), ("Routing", "auto-accept, desk review or field visit")],
        heading="Six outputs per call", space_after=4)
    points(slide, 8.85, 4.75, 3.88, 2.1, [
        ("Underwriter", "value, range and route inside the LOS"), ("Risk", "audit trail and drift monitoring"),
        ("Operations", "fewer valuer assignments"), ("Customer", "faster in-principle approval")],
        heading="Who uses it", space_after=4)
    set_notes(slide, f"""
        This is the product in one picture. The loan origination system sends a geo-pin and a few property
        attributes; no borrower data. The engine returns six things, numbered on the drawing: a point value, an
        eighty percent range, a grade from A to D, the main factors in rupees per square foot, model-adjusted
        comparables, and a routing decision. We kept an honest example on purpose. This {city} listing is a hard
        case: the estimate is far from the asking price, the range is wide, there are no training listings within a
        kilometre and the hedonic shadow model disagrees, so the engine grades it {grade} and routes it to a valuer
        instead of pretending to know. Four groups use the output: underwriters see value, range and route in the
        LOS; risk gets the audit trail; operations books fewer valuers; customers get faster in-principle approval.""")


def slide_scope(prs, m, report):
    slide = new_slide(prs, 4, "Point 1 · Scope the market", "Start where data is dense, earn the rest",
                      "[R17] NHB RESIDEX; [R18] RBI HPI; [R30] city-specific models beat a pooled one across five "
                      "Indian cities.")
    picture(slide, "s4_timeline.png", MARGIN, 1.6, 7.3, 2.6)
    cells = [("Hierarchical model.", "Micro-markets shrink toward the city and the city toward the national "
                                     "level, so a new city starts from shared knowledge [R30]."),
             ("City packs.", "OSM extract, imagery tiles, index mapping, circle-rate table and a calibration set: "
                             "configuration, not new code."),
             ("Abstention.", "Few comparables or a wide range returns a referral, not a confident number; valuer "
                             "outcomes return as labels."),
             ("Anchors.", "Circle rates as a floor reference; NHB RESIDEX [R17] and RBI HPI [R18] for time "
                          "trends in thin markets.")]
    for i, cell in enumerate(cells):
        col, row = i % 2, i // 2
        points(slide, MARGIN + col * 3.75, 4.35 + row * 1.25, 3.55, 1.2, [cell])
    picture(slide, "s4_india.png", 8.2, 1.65, 4.5, 5.1)
    set_notes(slide, f"""
        Point one, scope the market. The product is residential collateral valuation for home loans and LAP.
        Phase zero is the prototype: apartments in {m.cities_text()}, where open listing data exists. Phase one
        covers the top eight metros and adds independent houses and builder floors, because that is where data is
        densest and accuracy will be best. Phase two moves into the tier-2 and tier-3 cities in Hero Housing's
        lending footprint, with plotted land, anchored to circle rates and with wider ranges. Phase three is
        pan-India, including commercial and mixed-use LAP collateral through a separate income-approach model, rent
        times a capitalisation rate. Four mechanisms extend coverage honestly: a hierarchical model, city packs that
        are configuration rather than code, abstention when data is thin, and anchors such as circle rates, NHB
        RESIDEX and RBI house price indices. The map is schematic.""")


def slide_data(prs, m, report):
    total = (m.get("data", "row_counts_by_step", "geocoded") or {}).get("total")
    slide = new_slide(prs, 5, "Point 2 · Combine data sources", "Twelve sources, one H3-keyed feature table",
                      "[R21] Kaggle listings, CC0, 2020 asking-price snapshot; [R23] Open Buildings. No restricted-portal "
                      "scraping.")
    picture(slide, "s5_sources.png", MARGIN, 1.6, 7.6, 3.4)
    picture(slide, "s5_funnel.png", MARGIN, 5.05, 7.6, 0.8)
    points(slide, MARGIN, 5.95, 7.6, 0.9, [
        ("Lineage.", "Every record carries source, fetch date, licence and a quality flag. Terracotta marks what the "
                     "prototype uses; its labels are asking prices, a proxy.")])
    points(slide, 8.55, 1.65, 4.18, 5.2, [
        ("Prices.", "Lakh and crore parsed; area and BHK bounds; robust-z outliers on log price per city."),
        ("Amenity filter.", f"All-missing listings show {amenity_spread_ratio(m)} the price spread, so they go."),
        ("Dedup and geocode.", "Repeat listings removed before any split; locality-level geocodes only."),
        ("Area basis.", "Designed, not applied: the dataset states no carpet or built-up basis."),
        ("Merge.", "Joined on H3 cells, res 8 to 10, precomputed per cell.")],
        heading="Cleaning and merging", space_after=6)
    set_notes(slide, f"""
        Point two, combine data sources. India has no open national transaction dataset, so we separate what a
        lender can use in production from what we could use legally for the prototype. Twelve sources sit in three
        groups: structured records such as Hero Housing's own valuation reports, registry and circle rates, RERA,
        listings and price indices; unstructured imagery and scanned deeds; and alternative geospatial data. The
        prototype uses two of them, the terracotta circles: a CC0 Kaggle snapshot of 2020 asking prices and
        OpenStreetMap. Of 21,458 raw listings, {total or 'the final set of'} survive cleaning across four cities.
        The biggest cut is listings with every amenity missing; their price spread is several times wider, which
        points to unreliable rows. Area-basis normalisation is designed but could not be applied because the
        dataset never states the area type. In production the labels become Hero Housing's own valuation reports.""")


def slide_model(prs, m, report):
    slide = new_slide(prs, 6, "Point 3 · Build the AI/ML model", "A model ladder, scored on unseen neighbourhoods",
                      f"Prototype: {m.n_test()} listings, H3 spatial-block CV; errors vs asking prices. [R13] IAAO "
                      "2013 ranges.")
    picture(slide, "s6_lollipop.png", MARGIN, 1.6, 7.3, 3.5)
    b3 = m.significance("B3")
    b3_text = "matches B3 within noise" if b3 and not b3["ci_excludes_zero"] else "differs from B3"
    points(slide, MARGIN, 5.2, 3.55, 1.65, [
        ("Honest read.", f"M+ {b3_text}: the spatial residual adds nothing. Location and OSM access carry the "
                         "gain."),
        ("Not run.", "Imagery model; time split, as listings carry no dates.")], space_after=5)
    points(slide, MARGIN + 3.75, 5.2, 3.55, 1.65, [
        ("Protocol.", "Dedup first, hold out whole H3 cells, separate calibration split, paired cluster bootstrap."),
        ("Pilot bar.", "1,000+ lender files, MdAPE 15% below the incumbent.")], space_after=5)
    mplus = number_or_placeholder(m, "models", "M+", "mdape", label="M+ MdAPE")
    b0 = number_or_placeholder(m, "models", "B0", "mdape", label="B0 MdAPE")
    b2 = m.significance("B2")
    cut = f", a {b2['relative_reduction_pct']:.1f}% cut" if b2 else ""
    panel(slide, 8.3, 1.6, 4.43, 1.1)
    text(slide, 8.5, 1.63, 4.13, 1.04, [[("Result. ", {"bold": True, "color": C_BLUE}),
                                       (f"M+ MdAPE {mplus} vs {b0} for the city median; {sig_text(m, 'B2')} vs our "
                                        f"own attribute-only GBM{cut}. Not an incumbent AVM.", {})]], size=12)
    picture(slide, "s6_iaao.png", 8.3, 3.0, 4.4, 2.1)
    points(slide, 8.3, 5.3, 4.43, 1.1, [("By city.", f"{per_city_text(m)}; Mumbai is the worst subgroup.")])
    seen = m.fmt("seen_locality", "models", "M+", "mdape", label="seen-locality MdAPE")
    set_notes(slide, f"""
        Point three, the model and how we measure it. Features come in eight groups; the prototype has property,
        location and OpenStreetMap access. We climb a ladder: city median, hedonic regression, gradient-boosted
        trees on attributes, then location and OSM, then M+ with a spatial residual. On unseen H3 cells across four
        cities, M+ reaches {mplus} median error against {b0} for the city median, and beats our own attribute-only
        GBM by {sig_text(m, 'B2')}{cut}. That is against our own baseline, not an incumbent AVM. Honestly, M+ equals
        B3: the residual layer adds nothing, and location features carry the gain. If the locality was seen in
        training, error falls to {seen}. COD of {m.fmt('models', 'M+', 'cod', label='COD', pattern='{:.1f}')} and PRD
        of {m.fmt('models', 'M+', 'prd', label='PRD', pattern='{:.3f}')} sit outside the IAAO bands, and Mumbai is
        the worst city. The real test is the pre-registered pilot on Hero Housing's files.""")


def slide_explain(prs, m, report):
    slide = new_slide(prs, 7, "Point 4 · Make it explainable", "Every value comes with its reasons and its doubt",
                      "[R25] TreeSHAP; [R27] CQR with Mondrian per-city calibration [R10]; [R3] shadow model. FREE-AI "
                      "Sutra 6 [R16].")
    picture(slide, "s7_drivers.png", MARGIN, 1.6, 6.1, 4.3)
    points(slide, MARGIN, 6.0, 6.1, 0.85, [
        ("Also on every report.", "City-level SHAP summary, a hedonic shadow model that lowers the grade when it "
                                  "disagrees, comparables, and an out-of-distribution guard.")])
    picture(slide, "s7_waffle.png", 7.0, 1.6, 2.3, 2.75)
    width = m.fmt("coverage_80", "overall", "median_width_pct", label="median width", pattern="{:.0f}%")
    points(slide, 9.5, 1.65, 3.23, 2.7, [
        ("CQR, Mondrian by city.", f"{m.fmt('coverage_80', 'overall', 'coverage', label='coverage')} of held-out "
                                   f"homes inside the 80% range; median width {width}."),
        ("By city.", coverage_by_city(m) + ".")], space_after=6)
    picture(slide, "s7_grades.png", 7.0, 4.45, 5.0, 1.55)
    points(slide, 7.0, 6.05, 5.73, 0.8, [
        ("Audit.", "Each valuation logs inputs, features, model version, SHAP, route and overrides; every release "
                   "ships a model card.")])
    set_notes(slide, f"""
        Point four, explainability. Every valuation answers four questions. Why this value: TreeSHAP splits the
        estimate into drivers in rupees per square foot, shown for the sample property, with a city-level summary
        checked month on month. Is it plausible: a hedonic shadow model runs alongside, and the grade drops when
        they disagree; comparables show what is listed nearby; an out-of-distribution guard catches unusual inputs.
        How sure: conformalised quantile regression, calibrated per city. Overall, {m.fmt('coverage_80', 'overall',
        'coverage', label='coverage')} of held-out homes fell inside the eighty percent range, with a median width of
        {width}. Bangalore undercovers at {m.fmt('coverage_80', 'per_city', 'Bangalore', 'coverage',
        label='Bangalore coverage')}, so its calibration needs more data. Grades A to D map interval width to a
        route. Finally, an immutable audit log and a model card per release let risk re-run any valuation.""")


def slide_scale(prs, m, report):
    slide = new_slide(prs, 8, "Point 5 · Automate and scale", "Seconds per file, the whole book every quarter",
                      "Latency: prototype, one laptop worker. Orchestration and book-scale batch: designed, not built.")
    picture(slide, "s8_architecture.png", MARGIN, 1.75, 8.6, 4.9)
    picture(slide, "s8_latency.png", 9.45, 1.6, 3.2, 1.9)
    panel(slide, 9.45, 3.58, 3.28, 0.66)
    text(slide, 9.62, 3.62, 3.05, 0.58, [[("Try it live  ", {"bold": True, "color": C_BLUE})]
                                         + link_runs(DEMO_URL, DEMO_LABEL)], size=12, anchor=MSO_ANCHOR.MIDDLE)
    points(slide, 9.45, 4.34, 3.28, 2.51, [
        ("Stack.", "Airflow ingestion, Parquet and PostGIS, H3 feature store, FastAPI on Kubernetes."),
        ("Monitoring.", "PSI drift, rolling error against new valuer reports, champion-challenger, kill switch."),
        ("New city.", "Load a city pack; it starts conservative and earns automation."),
        ("Privacy.", "Property data only; borrower data stays in the LOS [R19].")], space_after=5)
    hardware = str(m.get("latency", "hardware") or "unrecorded hardware").split(";")[0]
    set_notes(slide, f"""
        Point five, automation and scale. The top lane is the offline pipeline with a monthly retrain. The middle
        lane is one request, numbered five to ten: the API call, precomputed H3 features, the model and its range,
        the explanation, routing rules and the report. The bottom lane is governance: audit log, monitoring,
        quarterly revaluation of the whole book, and valuers, whose outcomes flow back as training labels. People
        touch only desk reviews and field visits. The prototype measured a p95 of
        {m.fmt('latency', 'p95_ms', label='p95 latency', pattern='{:.0f} milliseconds')} on {hardware}, including SHAP
        and comparables, against a two-second target. Monitoring tracks PSI drift and rolling error against new
        valuer reports, with champion-challenger releases, roll-back and a kill switch. Encryption, role-based access
        and property-only inputs keep borrower data inside the LOS under the DPDP Act.""")


def slide_lending(prs, m, report):
    slide = new_slide(prs, 9, "Point 6 · Enable lending decisions", "Fewer site visits, only where the rules allow",
                      "Shares from metrics.json, unseen H3 cells. [R14] HFC Directions 2025, para 58, Annex V; [R16]; "
                      "[R19]; [R22].")
    picture(slide, "s9_workflow.png", MARGIN, 1.6, 12.1, 1.45)
    picture(slide, "s9_isotype.png", MARGIN, 3.2, 4.75, 3.5)
    shares, seen, unseen = routing_numbers(m)
    route = (f"{shares['AUTO_ACCEPT']:.1f}% auto, {shares['DESKTOP_REVIEW']:.1f}% desk, "
             f"{shares['PHYSICAL_VALUATION']:.1f}% valuer by default") if shares else m.placeholder("routing")
    gate = "Unseen cells meet no auto-accept bar" if unseen and not unseen.get("found") else "Unseen cells"
    seen_text = (f"{seen['auto_rate']:.1f}% clear the bar at {seen['mdape_auto']:.1f}% MdAPE; the gate opens as "
                 "lender data arrives." if seen.get("found") else m.placeholder("seen-locality operating point"))
    points(slide, 5.55, 3.25, 3.45, 3.6, [
        ("Routing today.", f"{gate}: {route}."),
        ("Known localities.", seen_text),
        ("LTV.", "Lower bound of the range, then the caps; weak files stop before booking a valuer."),
        ("Book and LAP.", "Quarterly revaluation flags LTV drift; LAP and mixed-use go to a valuer.")],
        space_after=6)
    rows = [("RBI HFC Directions 2025", "LTV caps 90/80/75% by loan size; two valuers from Rs 75 lakh [R14]"),
            ("FREE-AI", "aligned; advisory only [R16]"),
            ("Model risk, draft", "inventory, validation, challenger [R22]"),
            ("DPDP", "no borrower data in the model [R19]")]
    text(slide, 9.25, 3.25, 3.48, 0.4, "Regulatory fit", size=15, serif=True, color=C_BLUE)
    for i, (law, position) in enumerate(rows):
        y = 3.7 + i * 0.78
        hairline(slide, 9.25, y, 12.73, y, role="panel")
        text(slide, 9.25, y + 0.04, 3.48, 0.72, [[(law, {"bold": True, "color": C_BLUE})], position], size=12,
             space_after=0, spacing=1.0)
    set_notes(slide, f"""
        Point six, lending decisions and regulatory fit. Valuation runs at login, after KYC and bureau checks. A
        policy gate comes first: loans of Rs 75 lakh and above always get the two independent valuer reports the HFC
        Directions require, with the lower value used. Below that, the grade sets the route. At default thresholds,
        {route} on unseen neighbourhoods, and no threshold meets our quality bar there, so we would not switch
        auto-accept on today. In localities the model has seen, {seen_text} For auto-accepted files, LTV applies to
        the lower bound of the range, then the 90, 80 and 75 percent caps by loan size; files whose upper bound cannot
        support the loan stop before a valuer is booked. A quarterly batch flags LTV drift across the book, and LAP on
        mixed-use property defaults to a valuer. We align with FREE-AI, which is advisory, design to RBI's draft model
        risk guidance, and keep borrower data out of the model under DPDP.""")


def slide_pilot(prs, m, report):
    slide = new_slide(prs, 10, "Pilot plan, risks and next steps", "Prove it on Hero Housing's own files",
                      "[R14] HFC Directions · [R16] FREE-AI · [R22] draft MRM · [R27] CQR, Romano 2019 · [R25] SHAP")
    picture(slide, "s10_gantt.png", MARGIN, 1.6, 7.6, 2.8)
    points(slide, MARGIN, 4.5, 3.7, 2.35, [
        ("Onboard:", "data-quality report signed off."), ("Shadow:", "pre-registered bar met on 1,000+ files."),
        ("Assist:", "reviewers agree; turnaround falls."), ("Limited auto:", "overrides and loss within appetite.")],
        heading="Exit criteria", space_after=3)
    points(slide, MARGIN + 3.9, 4.5, 3.7, 2.35, [
        ("Days 0-45:", "data-sharing agreement; load 3 to 5 years of reports for two metros; retrain."),
        ("Days 45-90:", "shadow mode on every new file; weekly error report to credit risk.")],
        heading="Next 90 days", space_after=4)
    picture(slide, "s10_risks.png", 8.6, 1.6, 4.1, 3.0)
    points(slide, 8.6, 4.65, 4.13, 0.85, [
        ("Mitigations.", "Lender labels replace asking prices; LTV on the lower bound; abstention in thin markets; "
                         "OCR checks on deeds.")])
    text(slide, 8.6, 5.55, 4.13, 1.3, [[("Team Neural Knights", {"bold": True, "color": C_BLUE})],
                                      "Shashank, Yatin Allan S, Nimit Jain",
                                      [("Links  ", {"bold": True, "color": C_BLUE})] + link_runs(REPO_URL, REPO_LABEL),
                                      [("Live  ", {"bold": True, "color": C_BLUE})] + link_runs(DEMO_URL, DEMO_LABEL)],
         size=12, space_after=2)
    set_notes(slide, """
        To close, a pilot that lets Hero Housing judge us on its own data. Phase zero, four to six weeks, loads three
        to five years of valuation reports for two metros and ends when the data-quality report is signed off. Phase
        one is shadow mode for eight to twelve weeks: the engine runs on every new file, no decision uses it, and it
        must pass a pre-registered bar on at least a thousand properties, fifteen percent lower median error than
        the incumbent with a bootstrap interval excluding zero and no worse over-valuation tail. Phase two shows the
        report to desktop reviewers. Only then comes limited auto-accept for grade A loans under Rs 75 lakh, under
        Board policy. The top risks are asking-price labels, thin markets, over-valuation and inflated attributes,
        each with a mitigation. Each phase has a credit-risk owner and can be rolled back. Thank you from Team Neural
        Knights.""")


def estimated_lines(frame, width_in):
    usable = max(width_in, 0.1) * 72
    lines = []
    for p in frame.paragraphs:
        content = "".join(r.text for r in p.runs)
        size = max([r.font.size.pt for r in p.runs if r.font.size] or [12])
        chars_per_line = max(1, int(usable / (size * 0.52)))
        count, line_len = 1, 0
        for word in content.split():
            if line_len and line_len + 1 + len(word) > chars_per_line:
                count, line_len = count + 1, len(word)
            else:
                line_len += len(word) + (1 if line_len else 0)
        lines.append((count, size, p))
    return lines


def estimated_height(frame, width_in):
    total = 0.0
    for count, size, p in estimated_lines(frame, width_in):
        spacing = p.line_spacing if isinstance(p.line_spacing, float) else 1.0
        total += count * size * 1.2 * spacing / 72 + (p.space_after.pt if p.space_after else 0) / 72
    return total + 0.04


def shape_colors(shape):
    colors = []
    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
        return colors
    try:
        if shape.fill.type == 1:
            colors.append(str(shape.fill.fore_color.rgb))
    except (AttributeError, TypeError):
        pass
    try:
        if shape.line.fill.type == 1:
            colors.append(str(shape.line.color.rgb))
    except (AttributeError, TypeError):
        pass
    if shape.has_text_frame:
        colors += [str(r.font.color.rgb) for p in shape.text_frame.paragraphs for r in p.runs
                   if r.font.color and r.font.color.type is not None]
    return colors


def layout_issues(prs):
    issues, word_counts = [], []
    to_in = lambda emu: Emu(emu).inches
    for number, slide in enumerate(prs.slides, start=1):
        if abs(prs.slide_width / prs.slide_height - 16 / 9) > 0.01:
            issues.append("deck is not 16:9 landscape")
        background = str(slide.background.fill.fore_color.rgb)
        if background not in ALLOWED_COLORS:
            issues.append(f"slide {number} background {background} outside the palette")
        boxes, words = [], 0
        for shape in slide.shapes:
            role = shape.name.split(":")[0] if ":" in shape.name else "content"
            left, top, width, height = (to_in(v) for v in (shape.left, shape.top, shape.width, shape.height))
            right, bottom = left + width, top + height
            where = f"slide {number} '{shape.name}'"
            if left < -0.01 or top < -0.01 or right > SLIDE_W + 0.01 or bottom > SLIDE_H + 0.01:
                issues.append(f"{where} extends past the slide bounds")
            if role in ("content", "image", "panel") and (left < MARGIN - 0.01 or right > SLIDE_W - MARGIN + 0.01
                                                 or top < CONTENT_TOP - 0.01 or bottom > CONTENT_BOTTOM + 0.01):
                issues.append(f"{where} leaves the content area ({left:.2f}, {top:.2f}, {right:.2f}, {bottom:.2f})")
            for color in shape_colors(shape):
                if color.upper() not in ALLOWED_COLORS:
                    issues.append(f"{where} uses colour #{color} outside the palette")
            if shape.has_text_frame and shape.text_frame.text.strip():
                frame = shape.text_frame
                for p in frame.paragraphs:
                    for run in p.runs:
                        if run.text.strip() and run.font.size and run.font.size.pt < MIN_PT.get(role, 12):
                            issues.append(f"{where} font {run.font.size.pt}pt below {MIN_PT.get(role, 12)}pt")
                if estimated_height(frame, width) > height + 0.06:
                    issues.append(f"{where} text likely overflows: '{frame.text[:40]}'")
                if top >= FOOTER_RULE_Y and sum(c for c, _, _ in estimated_lines(frame, width)) > 1:
                    issues.append(f"{where} footer text runs past one line: '{frame.text[:40]}'")
                if role in COUNTED_ROLES:
                    words += len(frame.text.split())
            if role in ("content", "image"):
                boxes.append((where, left, top, right, bottom))
        word_counts.append(words)
        if words > MAX_WORDS:
            issues.append(f"slide {number} has {words} words (max {MAX_WORDS})")
        if number > 1 and words < MIN_WORDS:
            issues.append(f"slide {number} has {words} words (min {MIN_WORDS} on content slides)")
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                if min(a[3], b[3]) - max(a[1], b[1]) > 0.02 and min(a[4], b[4]) - max(a[2], b[2]) > 0.02:
                    issues.append(f"{a[0]} overlaps {b[0]}")
    return issues, word_counts


def build(metrics_path=DEFAULT_METRICS, out_path=DEFAULT_OUT, report_path=DEFAULT_REPORT):
    metrics = Metrics(metrics_path)
    report = SampleReport(report_path)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(SLIDE_W), Inches(SLIDE_H)
    set_link_colours(prs)
    for make_slide in (slide_title, slide_problem, slide_solution, slide_scope, slide_data, slide_model,
                       slide_explain, slide_scale, slide_lending, slide_pilot):
        make_slide(prs, metrics, report)
    issues, word_counts = layout_issues(prs)
    out_path = Path(out_path)
    prs.save(out_path)
    return out_path, metrics, issues, word_counts


def report_build(out_path, metrics, issues, word_counts):
    print(f"Wrote {out_path}")
    if not metrics.data:
        print(f"metrics.json not found at {metrics.path}; all result numbers are placeholders.")
    for label in dict.fromkeys(metrics.placeholders):
        print(f"Placeholder: {label}")
    print("Words per slide (title + body): " + ", ".join(f"{i}:{n}" for i, n in enumerate(word_counts, 1)))
    for issue in issues:
        print(f"QA FAIL: {issue}")
    if issues:
        raise SystemExit(f"Layout QA failed with {len(issues)} issue(s).")
    print("Layout QA passed: 16:9, bounds, content area, fonts, overflow, one-line footer, overlaps, "
          f"{MIN_WORDS}-{MAX_WORDS} words on content slides, palette.")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--metrics", default=DEFAULT_METRICS)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()
    report_build(*build(args.metrics, args.out, args.report))


if __name__ == "__main__":
    main()
