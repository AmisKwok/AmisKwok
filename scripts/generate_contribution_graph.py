#!/usr/bin/env python3
"""Generate a GitHub activity-graph style SVG from public contribution data.

Data source: https://github-contributions.vercel.app/api/v1/<user>  (no token needed)
Output: images/contribution-graph.svg  (referenced from README via jsDelivr)

Usage:  python scripts/generate_contribution_graph.py
"""
import json
import os
import sys
import urllib.request
from datetime import datetime

USER = "AmisKwok"
API_URL = f"https://github-contributions.vercel.app/api/v1/{USER}"
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "images", "contribution-graph.svg")

# Theme (kept consistent with the previous activity-graph params)
BG_COLOR = "1a1b27"
LINE_COLOR = "ffa500"   # line stroke
AREA_COLOR = "ff6470"   # area gradient top
POINT_COLOR = "f9f871"  # dots

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fetch_data():
    req = urllib.request.Request(API_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def catmull_rom_to_bezier(pts):
    """Return an SVG path string using smooth C (cubic bezier) segments."""
    if len(pts) < 2:
        return ""
    path = f"M {pts[0][0]:.1f},{pts[0][1]:.1f}"
    n = len(pts)
    for i in range(1, n):
        p0 = pts[i - 2] if i - 2 >= 0 else pts[i - 1]
        p1 = pts[i - 1]
        p2 = pts[i]
        p3 = pts[i + 1] if i + 1 < n else pts[i]
        cp1x = p1[0] + (p2[0] - p0[0]) / 6.0
        cp1y = p1[1] + (p2[1] - p0[1]) / 6.0
        cp2x = p2[0] - (p3[0] - p1[0]) / 6.0
        cp2y = p2[1] - (p3[1] - p1[1]) / 6.0
        path += f" C {cp1x:.1f},{cp1y:.1f} {cp2x:.1f},{cp2y:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return path


def build_svg(days):
    days = sorted(days, key=lambda d: d["date"])
    days = days[-371:]  # ~53 weeks
    counts = [max(0, int(d.get("count", 0))) for d in days]
    n = len(counts)
    maxc = max(counts) if max(counts) > 0 else 1

    W, H = 820, 260
    pad_l, pad_r = 10, 10
    pad_top, pad_bottom = 25, 35
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_top - pad_bottom

    def xpos(i):
        return pad_l + (plot_w * i / (n - 1)) if n > 1 else pad_l + plot_w / 2

    def ypos(c):
        return pad_top + plot_h * (1 - c / maxc)

    pts = [(xpos(i), ypos(c)) for i, c in enumerate(counts)]

    line_path = catmull_rom_to_bezier(pts)
    area_path = (line_path +
                 f" L {pts[-1][0]:.1f},{pad_top + plot_h:.1f}"
                 f" L {pts[0][0]:.1f},{pad_top + plot_h:.1f} Z")

    # Month labels: place a label when the month changes
    month_labels = []
    last_month = None
    for i, d in enumerate(days):
        dt = datetime.strptime(d["date"], "%Y-%m-%d")
        if dt.month != last_month:
            if last_month is not None:  # skip the very first partial segment
                month_labels.append((xpos(i), MONTHS[dt.month - 1]))
            last_month = dt.month
    # ensure the last month is labelled if room
    if month_labels and month_labels[-1][0] < W - 40:
        last_dt = datetime.strptime(days[-1]["date"], "%Y-%m-%d")
        month_labels.append((xpos(n - 1), MONTHS[last_dt.month - 1]))

    month_svg = "\n".join(
        f'<text x="{x:.1f}" y="{H - 12}" fill="#8b949e" font-size="12" '
        f'font-family="Verdana, sans-serif">{m}</text>'
        for x, m in month_labels
    )

    # Weekday labels (Mon / Wed / Fri) based on the first day's weekday
    first_dt = datetime.strptime(days[0]["date"], "%Y-%m-%d")
    first_wd = first_dt.weekday()  # 0=Mon
    wd_positions = []
    for wd, label in [(0, "Mon"), (2, "Wed"), (4, "Fri")]:
        idx = (wd - first_wd) % 7
        if idx < n:
            wd_positions.append((ypos(counts[idx]), label))
    wd_svg = "\n".join(
        f'<text x="2" y="{y + 4:.1f}" fill="#8b949e" font-size="11" '
        f'font-family="Verdana, sans-serif">{label}</text>'
        for y, label in wd_positions
    )

    dots = "\n".join(
        f'<circle cx="{px:.1f}" cy="{py:.1f}" r="1.8" fill="#{POINT_COLOR}" '
        f'opacity="0.75" />'
        for px, py in pts
    )

    total = sum(counts)

    title = f"{USER} - {total} contributions in the last year"
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 {W} {H}" preserveAspectRatio="none" role="img" aria-label="GitHub contribution graph for {USER}">
  <defs>
    <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#{AREA_COLOR}" stop-opacity="0.55" />
      <stop offset="100%" stop-color="#{AREA_COLOR}" stop-opacity="0.02" />
    </linearGradient>
  </defs>
  <rect width="{W}" height="{H}" fill="#{BG_COLOR}" rx="6" />
  <text x="{W / 2:.0f}" y="16" fill="#c9d1d9" font-size="13" text-anchor="middle" font-family="Verdana, sans-serif">{title}</text>
{month_svg}
{wd_svg}
  <path d="{area_path}" fill="url(#area)" stroke="none" />
  <path d="{line_path}" fill="none" stroke="#{LINE_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
{dots}
</svg>
'''
    return svg


def main():
    try:
        data = fetch_data()
    except Exception as e:  # keep previous SVG on failure
        print(f"[skip] failed to fetch contribution data: {e}", file=sys.stderr)
        sys.exit(1)

    days = data.get("contributions", [])
    if not days:
        print("[skip] empty contribution data", file=sys.stderr)
        sys.exit(1)

    svg = build_svg(days)
    out_abs = os.path.abspath(OUT_PATH)
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)
    with open(out_abs, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"[ok] wrote {out_abs} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()
