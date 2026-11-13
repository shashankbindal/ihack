"""Evaluation figures, all read from results/metrics.json."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src import config
from src.metrics import load_metrics

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
MUTED = "#8a8f98"
INK = "#52514e"
MODEL_ORDER = ["B0", "B1", "B2", "B3", "M+"]

plt.rcParams.update({
    "font.size": 9, "axes.edgecolor": INK, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e6e3",
    "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False,
})


def save(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(config.FIGURES / name, dpi=160, bbox_inches="tight")
    plt.close(fig)


def ablation(metrics: dict) -> None:
    protocols = [("Unseen H3 cell (spatial-block CV, primary)", metrics["models"], SERIES[0]),
                 ("Seen locality, unseen project", metrics["seen_locality"]["models"], SERIES[1])]
    x = np.arange(len(MODEL_ORDER))
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    for offset, (label, models, color) in zip([-0.2, 0.2], protocols):
        values = [models[m]["mdape"] for m in MODEL_ORDER]
        bars = ax.bar(x + offset, values, 0.38, color=color, label=label)
        for bar, model in zip(bars, MODEL_ORDER):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3, f"{models[model]['mdape']:.1f}",
                    ha="center", fontsize=8, color=INK)
    ax.set_xticks(x, MODEL_ORDER)
    ax.set_ylabel("MdAPE vs asking price (%)")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title("Ablation: median absolute % error by model and validation protocol", loc="left", fontsize=10)
    save(fig, "ablation.png")


def error_by_city(metrics: dict) -> None:
    cities = sorted(metrics["per_city"])
    x = np.arange(len(cities))
    width = 0.16
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), gridspec_kw={"width_ratios": [1.1, 1]})
    ax = axes[0]
    for i, model in enumerate(MODEL_ORDER):
        values = [metrics["per_city"][c][model]["mdape"] for c in cities]
        ax.bar(x + (i - 2) * width, values, width * 0.9, color=SERIES[i], label=model)
    ax.set_xticks(x, [f"{c}\n(n={metrics['per_city'][c]['M+']['n']:,})" for c in cities])
    ax.set_ylabel("MdAPE (%)")
    ax.grid(axis="x", visible=False)
    ax.legend(ncol=5, loc="upper left", bbox_to_anchor=(0, 1.12), fontsize=8)
    ax.set_title("By city", loc="left", fontsize=10, pad=22)

    ax = axes[1]
    bands = sorted(metrics["per_price_band"])
    edges = metrics["price_band_edges_inr"]
    labels = [f"{b}\n{edges[i] / 1e5:,.0f}-{edges[i + 1] / 1e5:,.0f}L" for i, b in enumerate(bands)]
    for i, model in [(0, "B0"), (2, "B2"), (4, "M+")]:
        values = [metrics["per_price_band"][b][model]["mdape"] for b in bands]
        ax.plot(labels, values, marker="o", markersize=5, linewidth=2, color=SERIES[i], label=model)
        ax.annotate(model, (len(bands) - 1, values[-1]), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=8, color=INK)
    ax.set_ylabel("MdAPE (%)")
    ax.legend(loc="upper center", fontsize=8)
    ax.set_title("By asking-price quintile (all cities)", loc="left", fontsize=10, pad=22)
    save(fig, "error_by_city.png")


def coverage_by_city(metrics: dict) -> None:
    coverage = metrics["coverage_80"]
    groups = ["overall"] + sorted(coverage["per_city"]) + sorted(coverage["per_price_band"])

    def pick(block: dict, group: str) -> dict:
        if group == "overall":
            return block["overall"]
        return block["per_city"].get(group) or block["per_price_band"][group]

    mondrian = [pick(coverage, g)["coverage"] for g in groups]
    pooled = [pick(coverage["pooled_conformal_for_contrast"], g)["coverage"] for g in groups]
    widths = [pick(coverage, g)["median_width_pct"] for g in groups]
    x = np.arange(len(groups))
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.bar(x - 0.2, pooled, 0.38, color=MUTED, label="pooled conformal")
    ax.bar(x + 0.2, mondrian, 0.38, color=SERIES[0], label="Mondrian by city (used)")
    ax.axhline(config.INTERVAL_LEVEL * 100, color=SERIES[1], linewidth=1.5, linestyle="--")
    ax.text(-0.45, config.INTERVAL_LEVEL * 100 - 5, "80% target", color=INK, fontsize=8, ha="left")
    for xi, cov, width in zip(x, mondrian, widths):
        ax.text(xi + 0.2, cov + 1.5, f"w {width:.0f}%", ha="center", fontsize=7, color=INK)
    ax.set_xticks(x, groups)
    ax.set_ylim(0, 105)
    ax.set_ylabel("Share of true values inside interval (%)")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="lower left", fontsize=8)
    ax.set_title("80% interval coverage on held-out cells; w = median interval width (% of value)", loc="left", fontsize=10)
    save(fig, "coverage_by_city.png")


def routing_tradeoff(metrics: dict) -> None:
    curves = [("Unseen H3 cell (primary, deployed engine)", metrics["routing_curve"], SERIES[0]),
              ("Seen locality, unseen project", metrics["routing_curve_seen_locality"], SERIES[1])]
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    for label, curve, color in curves:
        points = [p for p in curve["points"] if "mdape_auto" in p]
        ax.plot([p["auto_rate"] for p in points], [p["mdape_auto"] for p in points], color=color, linewidth=2,
                marker="o", markersize=4, label=label)
        selected = curve["selected"]
        if selected.get("found"):
            ax.scatter([selected["auto_rate"]], [selected["mdape_auto"]], s=90, color=color, edgecolor="white",
                       linewidth=2, zorder=5)
            ax.annotate(f"operating point: half-width <= {selected['grade_threshold']:.0f}%\n"
                        f"auto {selected['auto_rate']:.1f}%, MdAPE {selected['mdape_auto']:.1f}%, "
                        f">20% over {selected['overval20_auto']:.1f}%",
                        (selected["auto_rate"], selected["mdape_auto"]), xytext=(20, -38), textcoords="offset points",
                        fontsize=8, color=INK, arrowprops={"arrowstyle": "-", "color": INK})
    ax.axhline(config.AUTO_ACCEPT_MAX_MDAPE, color=MUTED, linestyle="--", linewidth=1)
    ax.text(ax.get_xlim()[1], config.AUTO_ACCEPT_MAX_MDAPE + 0.3, "MdAPE rule", ha="right", fontsize=8, color=INK)
    ax.set_xlabel("Auto-accepted share of valuations (%)")
    ax.set_ylabel("MdAPE among auto-accepted (%)")
    ax.set_ylim(bottom=0)
    ax.legend(loc="lower right", fontsize=8)
    ax.set_title("Routing trade-off: auto-accept share vs error of the accepted cases", loc="left", fontsize=10)
    save(fig, "routing_curve.png")


def main() -> None:
    config.FIGURES.mkdir(parents=True, exist_ok=True)
    metrics = load_metrics()
    ablation(metrics)
    error_by_city(metrics)
    coverage_by_city(metrics)
    routing_tradeoff(metrics)


if __name__ == "__main__":
    main()
