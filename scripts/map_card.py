#!/usr/bin/env python3
"""
Daily world-map preview picture (1200x630) for the map page, plus the map page
itself with that day's picture as its social preview.

    python scripts/map_card.py
      → posts/images/cards/map-<day>.png and map-latest.png
      → site_extra/map/index.html   (from map/index.html; the workflow publishes it)
"""
from __future__ import annotations

import datetime as dt
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import social_card as sc  # noqa: E402

ROOT, DATA = sc.ROOT, sc.DATA
W, H = 1200, 630
BG1, BG2 = (7, 16, 38), (13, 31, 69)
SHADES = [(58, 68, 92), (207, 226, 255), (164, 200, 255), (110, 168, 255), (61, 134, 245), (35, 102, 214), (26, 74, 168), (18, 48, 122)]
STEPS = [1, 10, 50, 100, 250, 500, 1000]
LABELS = ["1–9", "10–49", "50–99", "100–249", "250–499", "500–999", "1,000+"]


def shade(v: int) -> tuple:
    if not v:
        return SHADES[0]
    i = 0
    while i < len(STEPS) - 1 and v >= STEPS[i + 1]:
        i += 1
    return SHADES[i + 1]


def natural_earth(lon: float, lat: float) -> tuple[float, float]:
    l, p = math.radians(lon), math.radians(lat)
    p2 = p * p; p4 = p2 * p2
    x = l * (0.8707 - 0.131979 * p2 + p4 * (-0.013791 + p4 * (0.003971 * p2 - 0.001529 * p4)))
    y = p * (1.007226 + p2 * (0.015085 + p4 * (-0.044475 + 0.028874 * p2 - 0.005916 * p4)))
    return x, y


def load_world():
    topo = json.loads((ROOT / "assets" / "countries-110m.json").read_text(encoding="utf-8"))
    sx, sy = topo["transform"]["scale"]; tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0; pts = []
        for dx, dy in arc:
            x += dx; y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)

    def ring(idx):
        out = []
        for i in idx:
            pts = arcs[i] if i >= 0 else arcs[~i][::-1]
            out.extend(pts if not out else pts[1:])
        # rings that cross the date line: keep them on one side, flatten at the edge
        if any(abs(a[0] - b[0]) > 180 for a, b in zip(out, out[1:])):
            east = sum(1 for p in out if p[0] > 0) >= len(out) / 2
            out = [((min(180, p[0] + 360) if east and p[0] < 0 else max(-180, p[0] - 360) if not east and p[0] > 0 else p[0]), p[1]) for p in out]
        return out

    feats = []
    for g in topo["objects"]["countries"]["geometries"]:
        if g.get("id") == "010":            # Antarctica
            continue
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]] if g["type"] == "Polygon" else []
        feats.append((g.get("id"), (g.get("properties") or {}).get("name", ""), [[ring(r) for r in poly] for poly in polys]))
    return feats


def main() -> int:
    try:
        hist = json.loads((DATA / "history.json").read_text(encoding="utf-8"))
        latest = json.loads((DATA / "latest.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        print("map card: no data yet"); return 0
    day = latest.get("latest_day")
    rec = hist.get("days", {}).get(day)
    if not rec:
        return 0
    iso = json.loads((ROOT / "assets" / "iso.js").read_text(encoding="utf-8").split("=", 1)[1].strip().rstrip(";"))
    counts = rec.get("countries") or {}
    names = latest.get("country_names", {})
    feats = load_world()

    # fit the projection into the map area
    box = (40, 212, W - 40, H - 62)
    xs, ys = [], []
    for _, _, polys in feats:
        for poly in polys:
            for r in poly:
                for lon, lat in r:
                    x, y = natural_earth(lon, lat); xs.append(x); ys.append(y)
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    k = min((box[2] - box[0]) / (maxx - minx), (box[3] - box[1]) / (maxy - miny))
    ox = box[0] + ((box[2] - box[0]) - k * (maxx - minx)) / 2
    oy = box[1] + ((box[3] - box[1]) - k * (maxy - miny)) / 2
    P = lambda lon, lat: (ox + (natural_earth(lon, lat)[0] - minx) * k, oy + (maxy - natural_earth(lon, lat)[1]) * k)

    S = 2   # draw at 2x, then shrink, for smooth edges
    img = Image.new("RGB", (W * S, H * S), BG1)
    d = ImageDraw.Draw(img)
    for yy in range(H * S):
        t = yy / (H * S - 1)
        d.line([(0, yy), (W * S, yy)], fill=tuple(int(BG1[i] + (BG2[i] - BG1[i]) * (1 - abs(t - .4) * 1.4)) for i in range(3)))
    for fid, nm, polys in feats:
        col = shade(counts.get(iso.get(fid, ""), 0))
        for poly in polys:
            for j, r in enumerate(poly):
                pts = [(x * S, y * S) for x, y in (P(lon, lat) for lon, lat in r)]
                if len(pts) > 2:
                    d.polygon(pts, fill=col if j == 0 else BG1, outline=BG1)
    img = img.resize((W, H), Image.LANCZOS)
    d = ImageDraw.Draw(img, "RGBA")
    F = sc.font
    sc.logo(d, 40, 30, 46)
    d.text((96, 30), "Research", font=F("x", 28), fill=(255, 255, 255))
    w = d.textlength("Research", font=F("x", 28)); d.text((96 + w, 30), "Board", font=F("x", 28), fill=(124, 192, 255))
    d.text((W - 40, 40), "researchboard.net/map", font=F("b", 20), fill=(185, 205, 238), anchor="ra")
    d.text((W // 2, 104), "Where did today's research come from?", font=F("x", 42), fill=(255, 255, 255), anchor="mm")
    x = dt.date.fromisoformat(day)
    world = rec.get("papers") or sum(counts.values())
    d.text((W // 2, 146), f"{x:%A, %B} {x.day}, {x.year}  ·  {world:,} papers from {len(counts)} countries",
           font=F("b", 21), fill=(185, 205, 238), anchor="mm")
    # top 3 badges, centred under the subtitle
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:3]
    texts = [f"{i + 1}. {names.get(c, c)}  {v:,}" for i, (c, v) in enumerate(top)]
    widths = [d.textlength(t, font=F("b", 18)) + 24 for t in texts]
    bx = (W - (sum(widths) + 10 * (len(widths) - 1))) / 2
    for t, tw in zip(texts, widths):
        d.rounded_rectangle([bx, 170, bx + tw, 200], radius=15, fill=(255, 255, 255, 22), outline=(110, 168, 255, 170), width=1)
        d.text((bx + 12, 175), t, font=F("b", 18), fill=(255, 255, 255))
        bx += tw + 10
    # legend + call to action
    lx = 44
    for i, lab in enumerate(LABELS):
        d.rounded_rectangle([lx, H - 40, lx + 18, H - 30], radius=2, fill=SHADES[i + 1])
        d.text((lx + 22, H - 44), lab, font=F("r", 14), fill=(185, 205, 238))
        lx += 30 + d.textlength(lab, font=F("r", 14)) + 10
    cta = "Tap your country  →"
    tw = d.textlength(cta, font=F("x", 22))
    d.rounded_rectangle([W - 44 - tw - 36, H - 58, W - 44, H - 18], radius=20, fill=(110, 240, 170))
    d.text((W - 44 - tw - 18, H - 50), cta, font=F("x", 22), fill=(6, 40, 26))

    sc.CARDS.mkdir(parents=True, exist_ok=True)
    out = sc.CARDS / f"map-{day}.png"
    img.save(out, optimize=True)
    img.save(sc.CARDS / "map-latest.png", optimize=True)
    print("Map card written:", out.relative_to(ROOT))

    # the map page, with today's picture as its preview (a new file name each day, so social sites show the new map)
    tpl = ROOT / "map" / "index.html"
    if tpl.exists():
        page = tpl.read_text(encoding="utf-8").replace("cards/map-latest.png", f"cards/map-{day}.png")
        dst = ROOT / "site_extra" / "map"
        dst.mkdir(parents=True, exist_ok=True)
        (dst / "index.html").write_text(page, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
