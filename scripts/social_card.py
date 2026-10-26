#!/usr/bin/env python3
"""
Draws the 1200x630 "Today in Research" image card used on social media and as
the preview picture of each daily blog post. Needs Pillow.

    python scripts/social_card.py              card for the latest complete day
    python scripts/social_card.py --default    the site's general preview image
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = Path(__file__).resolve().parent / "fonts"
DATA = ROOT / "data"
CARDS = ROOT / "posts" / "images" / "cards"
W, H = 1200, 630

NAVY_1, NAVY_2 = (11, 27, 54), (24, 52, 99)
WHITE, MUTED, ACCENT, GREEN, VIOLET = (255, 255, 255), (169, 186, 214), (79, 155, 255), (126, 240, 181), (165, 151, 255)

# Eight colour themes; the daily card rotates through them (one per day, in order).
THEMES = [
    dict(name="Royal Blue",   c1=(12, 38, 120), c2=(36, 96, 226),  line=(70, 124, 236), acc=(150, 205, 255), muted=(205, 222, 255), v2=(255, 220, 110), v3=(140, 255, 190), box=(110, 150, 240)),
    dict(name="Teal",         c1=(0, 78, 88),   c2=(0, 150, 150),  line=(40, 170, 170), acc=(150, 255, 235), muted=(196, 240, 236), v2=(255, 226, 120), v3=(255, 255, 255), box=(80, 190, 190)),
    dict(name="Purple",       c1=(58, 18, 130), c2=(126, 52, 214), line=(150, 92, 226), acc=(225, 195, 255), muted=(226, 212, 255), v2=(255, 200, 235), v3=(150, 240, 255), box=(170, 120, 236)),
    dict(name="Green",        c1=(6, 86, 46),   c2=(18, 156, 84),  line=(60, 180, 116), acc=(190, 255, 200), muted=(206, 242, 214), v2=(255, 240, 120), v3=(255, 255, 255), box=(90, 196, 136)),
    dict(name="Crimson",      c1=(122, 12, 40), c2=(212, 38, 78),  line=(226, 90, 120), acc=(255, 200, 210), muted=(255, 218, 226), v2=(255, 236, 140), v3=(190, 240, 255), box=(236, 120, 148)),
    dict(name="Orange",       c1=(150, 56, 0),  c2=(238, 122, 18), line=(246, 156, 70), acc=(255, 232, 170), muted=(255, 230, 204), v2=(255, 255, 255), v3=(255, 248, 160), box=(250, 170, 96)),
    dict(name="Sky Blue",     c1=(0, 88, 164),  c2=(0, 162, 226),  line=(60, 186, 236), acc=(200, 240, 255), muted=(214, 238, 255), v2=(255, 236, 130), v3=(170, 255, 210), box=(90, 196, 244)),
    dict(name="Magenta",      c1=(124, 16, 104),c2=(214, 46, 156), line=(228, 100, 186), acc=(255, 205, 238), muted=(255, 220, 242), v2=(255, 240, 150), v3=(170, 240, 255), box=(236, 130, 200)),
]
THEME = THEMES[0]


def use_theme(day: dt.date | None) -> dict:
    """Pick the colour theme for a day (rotates through all eight) and make it current."""
    global THEME, NAVY_1, NAVY_2, ACCENT, MUTED, VIOLET, GREEN
    THEME = THEMES[(day.toordinal() if day else 0) % len(THEMES)]
    NAVY_1, NAVY_2, ACCENT, MUTED = THEME["c1"], THEME["c2"], THEME["acc"], THEME["muted"]
    VIOLET, GREEN = THEME["v2"], THEME["v3"]
    return THEME


def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    name = {"x": "Inter-ExtraBold.otf", "b": "Inter-SemiBold.otf", "r": "Inter-Regular.otf"}[weight]
    try:
        return ImageFont.truetype(str(FONTS / name), size)
    except OSError:
        return ImageFont.load_default(size=size)


def background() -> Image.Image:
    img = Image.new("RGB", (W, H), NAVY_1)
    d = ImageDraw.Draw(img)
    for x in range(W):  # horizontal gradient
        t = x / (W - 1)
        d.line([(x, 0), (x, H)], fill=tuple(int(NAVY_1[i] + (NAVY_2[i] - NAVY_1[i]) * t) for i in range(3)))
    # faint globe lines on the right
    cx, cy, r = 1050, 520, 360
    for k in range(0, 5):
        d.ellipse([cx - r + k * 70, cy - r, cx + r - k * 70, cy + r], outline=THEME["line"], width=2)
    for k in range(-3, 4):
        y = cy + k * 90
        d.line([(cx - r, y), (cx + r, y)], fill=THEME["line"], width=2)
    return img


def logo(d: ImageDraw.ImageDraw, x: int, y: int, s: int = 56) -> None:
    d.ellipse([x, y, x + s, y + s], fill=(42, 120, 214))
    pts = [(x + s * .2, y + s * .64), (x + s * .35, y + s * .52), (x + s * .46, y + s * .6),
           (x + s * .6, y + s * .42), (x + s * .7, y + s * .48), (x + s * .82, y + s * .32)]
    d.line(pts, fill=WHITE, width=max(3, s // 12), joint="curve")
    d.ellipse([x + s * .76, y + s * .26, x + s * .9, y + s * .4], fill=GREEN)


def header(d: ImageDraw.ImageDraw, site: str) -> None:
    logo(d, 64, 52)
    d.text((136, 50), "ResearchBoard", font=font("x", 34), fill=WHITE)
    d.text((137, 92), "Every Paper. Every Citation. Every Discovery.", font=font("r", 18), fill=MUTED)
    d.text((W - 64, 66), site, font=font("b", 22), fill=MUTED, anchor="ra")


def stat(d: ImageDraw.ImageDraw, x: int, y: int, value: str, label: str, color) -> None:
    d.rounded_rectangle([x, y, x + 252, y + 150], radius=18, fill=(0, 0, 0, 46), outline=THEME["box"], width=2)
    d.text((x + 22, y + 22), label.upper(), font=font("b", 16), fill=MUTED)
    size = 52 if len(value) <= 6 else 46 if len(value) <= 7 else 37 if len(value) <= 9 else 30
    d.text((x + 22, y + 56), value, font=font("x", size), fill=color)


def fmt(n) -> str:
    return "—" if n is None else f"{n:,}"


def make_daily_card(site: str = "researchboard.net") -> Path | None:
    hist = json.loads((DATA / "history.json").read_text(encoding="utf-8"))
    latest = json.loads((DATA / "latest.json").read_text(encoding="utf-8"))
    day = latest.get("latest_day")
    rec = hist.get("days", {}).get(day)
    if not rec:
        return None
    names = latest.get("country_names", {})
    d_ = dt.date.fromisoformat(day)
    use_theme(d_)

    img = background()
    d = ImageDraw.Draw(img, "RGBA")
    header(d, site)
    d.text((64, 162), "TODAY IN RESEARCH", font=font("b", 20), fill=ACCENT)
    d.text((64, 190), f"{d_:%A}, {d_:%B} {d_.day}, {d_.year}", font=font("x", 44), fill=WHITE)

    stats = [(fmt(rec.get("papers")), "New papers", WHITE),
             (fmt(rec.get("pubmed_added")), "Added to PubMed", WHITE),
             (fmt(rec.get("citations_made")), "Citations made", VIOLET),
             (fmt(rec.get("countries_active")), "Countries", GREEN)]
    for i, (v, label, c) in enumerate(stats):
        stat(d, 64 + i * 272, 272, v, label, c)

    top = list((rec.get("countries") or {}).items())[:3]
    if top:
        d.text((64, 470), "TOP COUNTRIES", font=font("b", 16), fill=MUTED)
        x = 64
        for i, (code, n) in enumerate(top, 1):
            txt = f"{i}. {names.get(code, code)}  {n:,}"
            d.text((x, 496), txt, font=font("b", 26), fill=WHITE)
            x += int(d.textlength(txt, font=font("b", 26))) + 44
    inst = (rec.get("institutions") or [])[:1]
    if inst:
        d.text((64, 548), f"Most active institution: {inst[0]['name']} ({inst[0]['count']:,} papers)",
               font=font("r", 21), fill=MUTED)

    CARDS.mkdir(parents=True, exist_ok=True)
    out = CARDS / f"daily-{day}.png"
    img.save(out, optimize=True)
    print("Card written:", out.relative_to(ROOT))
    return out


def make_default_card(site: str = "researchboard.net") -> Path:
    img = background()
    d = ImageDraw.Draw(img, "RGBA")
    header(d, site)
    d.text((64, 210), "The daily market board", font=font("x", 64), fill=WHITE)
    d.text((64, 290), "for global science", font=font("x", 64), fill=ACCENT)
    d.text((64, 400), "Papers  ·  PubMed  ·  Citations  ·  Countries  ·  Universities  ·  Journals",
           font=font("b", 26), fill=MUTED)
    d.text((64, 520), "Updated every day with open data from OpenAlex and PubMed", font=font("r", 22), fill=MUTED)
    out = ROOT / "assets" / "og-card.png"
    img.save(out, optimize=True)
    print("Default card written:", out.relative_to(ROOT))
    return out


def make_market_card(site: str = "researchboard.net") -> Path | None:
    """Stock-ticker style card for the last-24-hours change."""
    latest = json.loads((DATA / "latest.json").read_text(encoding="utf-8"))
    m = latest.get("market")
    if not m or m.get("flagged"):
        return None
    names = latest.get("country_names", {})
    t0 = dt.datetime.fromisoformat(m["from"]); t1 = dt.datetime.fromisoformat(m["to"])
    up, down = (52, 220, 120), (255, 92, 92)
    bg1, bg2, grid = (8, 12, 20), (18, 26, 40), (30, 42, 60)

    img = Image.new("RGB", (W, H), bg1)
    d = ImageDraw.Draw(img, "RGBA")
    for x in range(W):
        t = x / (W - 1)
        d.line([(x, 0), (x, H)], fill=tuple(int(bg1[i] + (bg2[i] - bg1[i]) * t) for i in range(3)))
    for y in range(140, H, 40):
        d.line([(0, y), (W, y)], fill=grid, width=1)
    # faint rising chart line
    pts, v = [], 470
    import random
    rnd = random.Random(t1.toordinal())
    for i, x in enumerate(range(560, W + 20, 40)):
        v -= rnd.randint(-14, 30)
        pts.append((x, max(170, min(540, v))))
    d.line(pts, fill=(52, 220, 120, 70), width=4)

    logo(d, 64, 52)
    d.text((136, 50), "ResearchBoard", font=font("x", 34), fill=WHITE)
    d.text((137, 92), "Every Paper. Every Citation. Every Discovery.", font=font("r", 18), fill=(150, 162, 184))
    d.text((W - 64, 66), site, font=font("b", 22), fill=(150, 162, 184), anchor="ra")

    d.text((64, 156), "RESEARCH MARKET  ·  LAST 24 HOURS", font=font("b", 20), fill=up)
    d.text((64, 184), f"{t0:%b} {t0.day}, {t0:%H:%M}  →  {t1:%b} {t1.day}, {t1:%H:%M} UTC",
           font=font("x", 34), fill=WHITE)

    # headline number
    d.text((64, 248), "▲", font=font("x", 54), fill=up)
    d.text((128, 238), f"+{m['papers_added']:,}", font=font("x", 76), fill=up)
    d.text((64, 330), "new papers added to the global research record", font=font("b", 22), fill=(190, 200, 216))
    y = 372
    if m.get("pubmed_yesterday"):
        d.text((64, y), f"+{m['pubmed_yesterday']:,}", font=font("x", 34), fill=WHITE)
        d.text((64 + d.textlength(f"+{m['pubmed_yesterday']:,}", font=font("x", 34)) + 12, y + 9),
               "records added to PubMed", font=font("r", 21), fill=(150, 162, 184))
        y += 52
    d.text((64, y), f"{m.get('countries_active', 0):,}", font=font("x", 34), fill=WHITE)
    d.text((64 + d.textlength(f"{m.get('countries_active', 0):,}", font=font("x", 34)) + 12, y + 9),
           "countries contributed", font=font("r", 21), fill=(150, 162, 184))

    # movers board
    x0, yb = 700, 248
    d.rounded_rectangle([x0, yb - 12, W - 64, 560], radius=16, fill=(255, 255, 255, 10), outline=grid, width=2)
    d.text((x0 + 24, yb), "TOP MOVERS", font=font("b", 16), fill=(150, 162, 184))
    for i, c in enumerate(m.get("countries", [])[:5]):
        yy = yb + 34 + i * 50
        name = names.get(c["code"], c["code"])
        d.text((x0 + 24, yy), c["code"], font=font("x", 22), fill=(150, 162, 184))
        d.text((x0 + 70, yy), name[:20], font=font("b", 22), fill=WHITE)
        d.text((W - 88, yy), f"▲ +{c['added']:,}", font=font("x", 22), fill=up, anchor="ra")
    inst = (m.get("institutions") or [])[:1]
    if inst:
        d.text((64, 568), f"Top institution: {inst[0]['name']}  ▲ +{inst[0]['added']:,}",
               font=font("r", 20), fill=(150, 162, 184))

    CARDS.mkdir(parents=True, exist_ok=True)
    out = CARDS / f"market-{t1.date().isoformat()}.png"
    img.save(out, optimize=True)
    print("Market card written:", out.relative_to(ROOT))
    return out


if __name__ == "__main__":
    import os
    site = os.environ.get("SITE_URL", "https://researchboard.net").split("://", 1)[-1].rstrip("/")
    if "--default" in sys.argv:
        make_default_card(site)
    elif "--market" in sys.argv:
        make_market_card(site)
    else:
        make_daily_card(site)
