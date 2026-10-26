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
    dict(name="Navy",          c1=(11, 27, 54), c2=(24, 52, 99),   line=(40, 72, 125),  acc=(79, 155, 255),  muted=(169, 186, 214), v2=(165, 151, 255), v3=(126, 240, 181), box=(60, 92, 145)),
    dict(name="Ocean Teal",    c1=(4, 40, 48),  c2=(9, 84, 92),    line=(24, 104, 112), acc=(64, 224, 208),  muted=(160, 210, 212), v2=(120, 236, 255), v3=(255, 214, 120), box=(40, 120, 128)),
    dict(name="Royal Purple",  c1=(30, 16, 60), c2=(64, 36, 116),  line=(84, 60, 140),  acc=(190, 150, 255), muted=(196, 184, 228), v2=(255, 160, 220), v3=(140, 230, 255), box=(98, 74, 160)),
    dict(name="Forest Green",  c1=(8, 38, 26),  c2=(18, 76, 52),   line=(34, 96, 68),   acc=(110, 230, 150), muted=(170, 214, 190), v2=(220, 240, 120), v3=(140, 220, 255), box=(48, 112, 82)),
    dict(name="Burgundy",      c1=(52, 12, 26), c2=(102, 26, 48),  line=(122, 46, 68),  acc=(255, 130, 150), muted=(226, 180, 190), v2=(255, 200, 120), v3=(150, 220, 255), box=(138, 62, 84)),
    dict(name="Charcoal Gold", c1=(18, 20, 26), c2=(42, 46, 56),   line=(58, 62, 74),   acc=(244, 190, 80),  muted=(184, 188, 198), v2=(244, 190, 80),  v3=(126, 240, 181), box=(78, 82, 96)),
    dict(name="Bright Blue",   c1=(6, 50, 112), c2=(22, 104, 196), line=(44, 124, 212), acc=(150, 215, 255), muted=(196, 222, 248), v2=(255, 220, 120), v3=(140, 255, 200), box=(70, 140, 220)),
    dict(name="Sunset Copper", c1=(58, 24, 10), c2=(118, 54, 22),  line=(136, 74, 40),  acc=(255, 176, 96),  muted=(232, 198, 170), v2=(255, 226, 140), v3=(150, 226, 255), box=(150, 90, 56)),
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
    d.rounded_rectangle([x, y, x + 252, y + 150], radius=18, fill=(255, 255, 255, 18), outline=THEME["box"], width=2)
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


if __name__ == "__main__":
    import os
    site = os.environ.get("SITE_URL", "https://researchboard.net").split("://", 1)[-1].rstrip("/")
    if "--default" in sys.argv:
        make_default_card(site)
    else:
        make_daily_card(site)
