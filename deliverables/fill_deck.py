"""Rebuild everything from the latest files: draw every visual asset, rebuild deck.pptx from
prototype/results/metrics.json and sample_report.html and run the layout QA. With --export-dir it also
exports a QA copy (deck.pdf and slideNN.png) there, never into deliverables/, and checks that at least
20% of every slide is whitespace.

Export uses LibreOffice (soffice) if it is on PATH, otherwise Microsoft PowerPoint on Windows.

Usage: python fill_deck.py [--export-dir DIR]
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

from build_deck import DEFAULT_OUT, build, report_build
from deck_data import BACKGROUND, DEFAULT_METRICS, DEFAULT_REPORT, FIGURES

MIN_WHITESPACE = 0.20

POWERPOINT_EXPORT = r"""
param([string]$Deck, [string]$Pdf, [string]$PngDir)
$app = New-Object -ComObject PowerPoint.Application
try {
    $pres = $app.Presentations.Open($Deck, $true, $false, $false)
    if ($Pdf) { $pres.SaveAs($Pdf, 32) }
    if ($PngDir) {
        New-Item -ItemType Directory -Force $PngDir | Out-Null
        Get-ChildItem $PngDir -Filter "slide*.png" | Remove-Item
        foreach ($slide in $pres.Slides) {
            $slide.Export((Join-Path $PngDir ("slide{0:D2}.png" -f $slide.SlideIndex)), "PNG", 1920, 1080)
        }
    }
    $pres.Close()
} finally { $app.Quit() }
"""


def draw_assets(metrics, report):
    subprocess.run([sys.executable, "-I", str(FIGURES / "draw_figs.py"), str(FIGURES), "--metrics", str(metrics),
                    "--report", str(report)], check=True)


def export_with_powerpoint(deck, pdf, png_dir):
    script = Path(deck).with_name("_export_deck.ps1")
    script.write_text(POWERPOINT_EXPORT, encoding="utf-8")
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                        "-Deck", str(deck), "-Pdf", str(pdf or ""), "-PngDir", str(png_dir or "")], check=True)
    finally:
        script.unlink(missing_ok=True)


def export_with_soffice(soffice, deck, pdf, png_dir):
    out_dir = Path(pdf).parent if pdf else Path(png_dir)
    subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(deck)], check=True)
    if png_dir:
        import fitz
        Path(png_dir).mkdir(parents=True, exist_ok=True)
        with fitz.open(out_dir / (Path(deck).stem + ".pdf")) as doc:
            for index, page in enumerate(doc, start=1):
                page.get_pixmap(dpi=144).save(Path(png_dir) / f"slide{index:02d}.png")


def whitespace_issues(png_dir):
    background = tuple(int(BACKGROUND[i:i + 2], 16) for i in (1, 3, 5))
    issues = []
    for path in sorted(Path(png_dir).glob("slide*.png")):
        image = Image.open(path).convert("RGB").resize((480, 270))
        pixels = list(image.getdata())
        blank = sum(1 for p in pixels if sum(abs(a - b) for a, b in zip(p, background)) < 24) / len(pixels)
        print(f"{path.name}: {blank:.0%} whitespace")
        if blank < MIN_WHITESPACE:
            issues.append(f"{path.name} has {blank:.0%} whitespace (min {MIN_WHITESPACE:.0%})")
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--metrics", default=DEFAULT_METRICS)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--export-dir", help="folder for the QA PDF and slide PNGs (outside deliverables/)")
    args = parser.parse_args()

    draw_assets(args.metrics, args.report)
    deck, *results = build(args.metrics, args.out, args.report)
    report_build(deck, *results)
    deck = deck.resolve()

    if not args.export_dir:
        return
    png_dir = Path(args.export_dir).resolve()
    if deck.parent == png_dir:
        sys.exit("Choose an export folder outside deliverables/.")
    png_dir.mkdir(parents=True, exist_ok=True)
    pdf = png_dir / "deck.pdf"
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        export_with_soffice(soffice, deck, pdf, png_dir)
    elif sys.platform == "win32":
        export_with_powerpoint(deck, pdf, png_dir)
    else:
        sys.exit("No soffice or PowerPoint found; deck.pptx was built but not exported.")
    print(f"Wrote QA export to {png_dir}")
    issues = whitespace_issues(png_dir)
    for issue in issues:
        print(f"QA FAIL: {issue}")
    if issues:
        raise SystemExit("Whitespace check failed.")
    print(f"Whitespace check passed (every slide at least {MIN_WHITESPACE:.0%}).")


if __name__ == "__main__":
    main()
