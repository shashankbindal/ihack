"""Palette and data loaders shared by build_deck.py and figures/draw_figs.py."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DELIVERABLES = ROOT / "deliverables"
FIGURES = DELIVERABLES / "figures"
DECK_FIGURES = FIGURES / "deck"
DEFAULT_METRICS = ROOT / "prototype" / "results" / "metrics.json"
DEFAULT_REPORT = ROOT / "prototype" / "results" / "figures" / "sample_report.html"

BACKGROUND = "#F7F5F0"
INK = "#1A1A1A"
PRUSSIAN = "#1D3557"
TERRACOTTA = "#D95D39"
STONE = "#DCD6CD"
WHITE = "#FFFFFF"
PALETTE = (BACKGROUND, INK, PRUSSIAN, TERRACOTTA, STONE, WHITE)

HEADLINE_FONT = "Georgia"
BODY_FONT = "Segoe UI"

ROUTES = ("AUTO_ACCEPT", "DESKTOP_REVIEW", "PHYSICAL_VALUATION")
ROUTE_LABELS = {"AUTO_ACCEPT": "Auto-accept", "DESKTOP_REVIEW": "Desktop review",
                "PHYSICAL_VALUATION": "Physical valuation"}
LADDER = ("B0", "B1", "B2", "B3", "M", "M+")
LADDER_LABELS = {"B0": "B0 city median", "B1": "B1 hedonic", "B2": "B2 GBM, attributes",
                 "B3": "B3 + OSM access", "M": "M + imagery", "M+": "M+ spatial residual"}


class Metrics:
    def __init__(self, path=DEFAULT_METRICS):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        self.placeholders = []

    def get(self, *keys):
        node = self.data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return None
            node = node[key]
        return node

    def number(self, *keys):
        value = self.get(*keys)
        return value if isinstance(value, (int, float)) else None

    def placeholder(self, label, compact=False):
        self.placeholders.append(label)
        return "«from metrics.json»" if compact else f"«{label}: from metrics.json»"

    def fmt(self, *keys, label, pattern="{:.1f}%", compact=False):
        value = self.number(*keys)
        return self.placeholder(label, compact) if value is None else pattern.format(value)

    def cities(self):
        listed = self.get("cities")
        if isinstance(listed, list) and listed:
            return listed
        per_city = self.get("per_city")
        return list(per_city) if isinstance(per_city, dict) and per_city else []

    def not_run(self, key):
        return key in (self.get("not_run") or {})

    def cities_text(self):
        return ", ".join(self.cities()) or self.placeholder("cities")

    def n_test(self):
        value = self.number("n_test")
        return f"{int(value):,}" if value is not None else self.placeholder("n_test")

    def significance(self, other):
        sig = self.get("significance", f"M+_vs_{other}")
        return sig if isinstance(sig, dict) and "ci95" in sig else None

    def has_time_split(self):
        split = str(self.get("split") or "")
        return "time" in split and "no time split" not in split

    def routing_shares(self):
        shares = self.get("grades", "routing_share")
        if not isinstance(shares, dict) or not shares:
            return None
        result = {route: float(shares.get(route, 0.0)) for route in ROUTES}
        return result if abs(sum(result.values()) - 100) <= 0.5 else None


class SampleReport:
    """Values from the prototype's rendered sample valuation report."""

    def __init__(self, path=DEFAULT_REPORT):
        path = Path(path)
        html = path.read_text(encoding="utf-8") if path.exists() else ""
        html = re.sub(r"data:image[^\"']+", "", html)

        def grab(pattern):
            match = re.search(pattern, html, re.S)
            return match.group(1).strip() if match else None

        self.available = bool(html)
        self.point = grab(r'Point estimate</div><div class="big">([^<]+)<')
        self.per_sqft = grab(r'Point estimate</div><div class="big">[^<]+</div>\s*<div>([^<]+)<')
        interval = re.search(r'80% interval</div>\s*<div class="big">(Rs [^<]+?) to (Rs [^<]+?)</div>'
                             r'<div>width ([^<]+)<', html)
        self.low_text, self.high_text, self.width = interval.groups() if interval else (None, None, None)
        self.grade = grab(r'class="grade">([A-D])<')
        routing = grab(r'Routing</div><div class="big"[^>]*>([^<]+)<')
        self.routing = routing.replace(" ", "_") if routing else None
        self.city = grab(r"\| model [^|]+\|\s*([^|]+?)\s*\|")
        self.factors = [(float(f"{sign}{value.replace(',', '')}"), label.strip())
                        for sign, value, label in
                        re.findall(r"<li><b>([+-])Rs ([\d,]+)/sqft</b> \([^)]*\): ([^<]+)</li>", html)]
        why = re.search(r"Why this routing</h2><ul>(.*?)</ul>", html, re.S)
        self.reasons = re.findall(r"<li>([^<]+)</li>", why.group(1)) if why else []
        body = re.search(r"Comparable listings.*?<tbody>(.*?)</tbody>", html, re.S)
        self.n_comparables = len(re.findall(r"<tr", body.group(1))) if body else None

    @staticmethod
    def lakh(text):
        match = re.search(r"Rs ([\d.,]+) (lakh|crore)", text or "")
        if not match:
            return None
        value = float(match.group(1).replace(",", ""))
        return value * 100 if match.group(2) == "crore" else value


def short_factor(label):
    if "spatial residual" in label:
        return "Local price level"
    if "latitude" in label:
        return "Exact location in the city"
    return label if len(label) <= 34 else label[:32].rstrip() + '...'
