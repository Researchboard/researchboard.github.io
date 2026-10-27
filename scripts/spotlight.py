#!/usr/bin/env python3
"""
"Spotlight" posts: three leaderboards a day (SPOTLIGHT_SLOT=0/1/2), cycling through seven themes:
  🌍 top countries this week · 🏛️ top universities · 🔥 most-cited papers · 📚 top journals this week
  🚀 fastest-rising countries · 🧪 research by field · 🏆 scientists

    python scripts/spotlight.py              card + message for today's theme
    python scripts/spotlight.py --all        all seven (preview)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

from PIL import ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import social_card as sc  # noqa: E402

ROOT = sc.ROOT
DATA = ROOT / "data"
SITE = os.environ.get("SITE_URL", "https://researchboard.net").rstrip("/")
THEMES = ["countries", "universities", "papers", "journals", "rising", "fields", "scientists"]


def load():
    hist = json.loads((DATA / "history.json").read_text(encoding="utf-8"))
    latest = json.loads((DATA / "latest.json").read_text(encoding="utf-8"))
    return hist, latest


def week(hist: dict, end: str, offset: int = 0) -> list[str]:
    keys = [k for k in sorted(hist.get("days", {})) if k <= end]
    return keys[len(keys) - 7 - offset: len(keys) - offset] if len(keys) >= 7 + offset else []


def span_label(keys: list[str]) -> str:
    a, b = dt.date.fromisoformat(keys[0]), dt.date.fromisoformat(keys[-1])
    return f"{a:%b} {a.day} – {b:%b} {b.day}, {b.year}" if a.month != b.month else f"{a:%b} {a.day}–{b.day}, {b.year}"


def latin(text: str) -> bool:
    return all(ord(ch) < 0x0250 or 0x2000 <= ord(ch) < 0x2070 for ch in text)


def tag(name: str) -> str:
    return "#" + re.sub(r"[^A-Za-z0-9]", "", name.title()) if name else ""


# --------------------------------------------------------------------------- themes → data

def build(theme: str, hist: dict, latest: dict) -> dict | None:
    """Returns {kicker, title, sub, rows:[(badge, name, value_str, bar_value)], intro, url, tags, unit} or None."""
    days = hist.get("days", {})
    day = latest.get("latest_day")
    if not day or day not in days:
        return None
    names = latest.get("country_names", {})
    d = dt.date.fromisoformat(day)
    dl = f"{d:%A}, {d:%B} {d.day}, {d.year}"
    ic = latest.get("inst_country") or {}

    if theme in ("countries", "rising"):
        wk, prev = week(hist, day), week(hist, day, 7)
        if not wk:
            return None
        tot, old = {}, {}
        for k in wk:
            for c, n in (days[k].get("countries") or {}).items():
                tot[c] = tot.get(c, 0) + n
        for k in prev:
            for c, n in (days[k].get("countries") or {}).items():
                old[c] = old.get(c, 0) + n
        if theme == "countries":
            top = sorted(tot.items(), key=lambda kv: -kv[1])[:10]
            rows = [(c, names.get(c, c), f"{n:,}", n, "") for c, n in top]
            return dict(kicker="WEEKLY LEADERBOARD · COUNTRIES", title="Top 10 research countries this week",
                        sub=f"Papers published · {span_label(wk)}", rows=rows, url=f"{SITE}/country/",
                        intro=f"🌍 Which countries published the most research this week? ({span_label(wk)})",
                        unit="papers", tags=[tag(names.get(c, c)) for c, *_ in top[:4]])
        if not prev:
            return None
        T, O = sum(tot.values()) or 1, sum(old.values()) or 1
        cand = [(c, n, (n / T) / (old[c] / O) - 1) for c, n in tot.items() if old.get(c, 0) >= 150 and n >= 150]
        cand.sort(key=lambda x: -x[2])
        rows = [(c, names.get(c, c), f"▲ {g * 100:.0f}%", g, f"{n:,} papers") for c, n, g in cand[:10] if g > 0]
        if len(rows) < 3:
            return None
        return dict(kicker="RISING COUNTRIES · WEEK ON WEEK", title="Fastest-growing research countries",
                    sub=f"Growth in share of world papers · {span_label(wk)} vs the week before (150+ papers)", rows=rows,
                    url=f"{SITE}/country/", unit="growth",
                    intro=f"🚀 Which countries grew their share of world research the most this week? ({span_label(wk)} vs the previous 7 days)",
                    tags=[tag(r[1]) for r in rows[:4]])

    if theme == "universities":
        inst = (days[day].get("institutions") or [])[:10]
        if not inst:
            return None
        rows = [(ic.get(x["id"]) or "", x["name"], f"{x['count']:,}", x["count"], "") for x in inst]
        return dict(kicker="DAILY LEADERBOARD · UNIVERSITIES", title="Top 10 most active universities",
                    sub=f"Papers with at least one author from each institution · {dl}", rows=rows,
                    url=f"{SITE}/universities/", unit="papers",
                    intro=f"🏛️ The 10 most active universities and research institutions on {d:%B} {d.day}:",
                    tags=["#University", "#HigherEducation", "#Academia"])

    if theme == "journals":
        wk = week(hist, day)
        tot, nm = {}, {}
        for k in wk:
            for x in days[k].get("journals") or []:
                tot[x["id"]] = tot.get(x["id"], 0) + x["count"]; nm[x["id"]] = x["name"]
        top = [kv for kv in sorted(tot.items(), key=lambda kv: -kv[1]) if latin(nm[kv[0]])][:10]
        if not top:
            return None
        rows = [("", nm[i], f"{n:,}", n, "") for i, n in top]
        return dict(kicker="WEEKLY LEADERBOARD · JOURNALS", title="Top 10 journals this week",
                    sub=f"Papers published · {span_label(wk)}", rows=rows, url=f"{SITE}/journals/", unit="papers",
                    intro=f"📚 Which journals published the most papers this week? ({span_label(wk)})",
                    tags=["#Journals", "#Publishing", "#AcademicPublishing"])

    if theme == "fields":
        f_ = days[day].get("fields") or []
        tot = sum(x["count"] for x in f_) or 1
        rows = [("", x["name"], f"{x['count'] / tot * 100:.1f}%", x["count"], f"{x['count']:,}") for x in f_[:10]]
        if not rows:
            return None
        return dict(kicker="RESEARCH BY FIELD", title="Where science is happening",
                    sub=f"Share of the day's papers by main field · {dl}", rows=rows, url=f"{SITE}/fields/", unit="share",
                    intro=f"🧪 What did the world research on {d:%B} {d.day}? Share of new papers by field:",
                    tags=[tag(r[1]) for r in rows[:3]])

    if theme == "papers":
        g = latest.get("paper_gainers") or []
        if g:
            rows = [("", p["title"], f"+{p['gain']:,}", p["gain"], p.get("venue") or "") for p in g[:5]]
            return dict(kicker="CITATIONS · BIGGEST DAILY GAINS", title="Papers gaining the most citations",
                        sub="New citations since the previous day", rows=rows, url=f"{SITE}/papers/", unit="citations", wide=True,
                        intro="🔥 These papers gained the most citations since yesterday:", tags=["#Citations", "#ResearchImpact"])
        hp = (latest.get("hot_papers") or [])[:5]
        if not hp:
            return None
        rows = [("", p["title"], f"{p['citations']:,}", p["citations"], f"{p.get('venue') or ''} · {p.get('year') or ''}") for p in hp]
        return dict(kicker="CITATIONS · LAST 2 YEARS", title="Most-cited new papers",
                    sub="Papers published in the last two years, by total citations", rows=rows, url=f"{SITE}/papers/",
                    unit="citations", wide=True, intro="🔥 The most-cited papers of the last two years:",
                    tags=["#Citations", "#ResearchImpact", "#MostCited"])

    if theme == "scientists":
        g = latest.get("gainers") or []
        src, gain = (g, True) if g else ((latest.get("top_authors") or []), False)
        if not src:
            return None
        rows = [(a.get("country") or "", a["name"], f"+{a['gain']:,}" if gain else f"{a['citations']:,}",
                 a["gain"] if gain else a["citations"], a.get("institution") or "") for a in src[:10]]
        return dict(kicker="SCIENTISTS · " + ("DAILY CITATION GAINS" if gain else "ALL-TIME CITATIONS"),
                    title="Scientists gaining the most citations" if gain else "The most-cited scientists in the world",
                    sub="New citations since the previous day" if gain else "Total citations, all time (OpenAlex)",
                    rows=rows, url=f"{SITE}/scientists/", unit="citations",
                    intro="🏆 " + ("Scientists who gained the most citations since yesterday:" if gain else "The most-cited scientists in the world, all time:"),
                    tags=["#Scientists", "#Citations", "#Academia"])
    return None


# --------------------------------------------------------------------------- card

def card(info: dict, theme: str, when: dt.date, site: str, slot: int = 0) -> Path:
    sc.use_theme(dt.date.fromordinal(when.toordinal() + 3 * slot + 1))
    img = sc.background()
    d = ImageDraw.Draw(img, "RGBA")
    sc.header(d, site)
    F = sc.font
    d.text((64, 150), info["kicker"], font=F("b", 19), fill=sc.ACCENT)
    d.text((64, 176), info["title"], font=F("x", 42), fill=sc.WHITE)
    d.text((64, 230), info["sub"], font=F("r", 19), fill=sc.MUTED)
    rows = info["rows"]
    top = max((r[3] for r in rows), default=1) or 1

    def fit(text, fnt, width):
        if d.textlength(text, font=fnt) <= width:
            return text
        while text and d.textlength(text + "…", font=fnt) > width:
            text = text[:-1]
        return text.rstrip() + "…"

    if info.get("wide"):  # five long rows (paper titles)
        y = 270
        for i, (badge, name, val, bar, extra) in enumerate(rows[:5], 1):
            d.rounded_rectangle([64, y, W_ - 64, y + 56], radius=12, fill=(0, 0, 0, 40), outline=sc.THEME["box"], width=1)
            d.text((84, y + 13), str(i), font=F("x", 26), fill=sc.ACCENT)
            d.text((124, y + 7), fit(name, F("b", 21), 780), font=F("b", 21), fill=sc.WHITE)
            d.text((124, y + 32), fit(extra, F("r", 16), 780), font=F("r", 16), fill=sc.MUTED)
            d.text((W_ - 84, y + 14), val, font=F("x", 26), fill=sc.VIOLET, anchor="ra")
            y += 62
    else:  # two columns of five, with bars
        for i, (badge, name, val, bar, extra) in enumerate(rows[:10]):
            col, row = divmod(i, 5)
            x, y = 64 + col * 548, 276 + row * 64
            d.text((x, y + 4), f"{i + 1}", font=F("x", 24), fill=sc.ACCENT)
            nx = x + 40
            if badge:
                d.rounded_rectangle([nx, y + 4, nx + 44, y + 30], radius=6, fill=(255, 255, 255, 40))
                d.text((nx + 22, y + 17), badge, font=F("x", 15), fill=sc.WHITE, anchor="mm")
                nx += 54
            d.text((nx, y + 3), fit(name, F("b", 22), 510 - (nx - x) - d.textlength(val, font=F("x", 22)) - 14), font=F("b", 22), fill=sc.WHITE)
            d.text((x + 510, y + 3), val, font=F("x", 22), fill=sc.VIOLET if i else sc.GREEN, anchor="ra")
            bw = max(6, int(bar / top * 470))
            d.rounded_rectangle([x + 40, y + 36, x + 40 + 470, y + 44], radius=4, fill=(0, 0, 0, 50))
            d.rounded_rectangle([x + 40, y + 36, x + 40 + bw * 1.0 * 470 / 470, y + 44], radius=4, fill=sc.ACCENT)
            if extra and info["unit"] in ("papers",):
                d.text((x + 510, y + 26), extra, font=F("b", 14), fill=sc.MUTED, anchor="ra")
    d.text((64, 590), f"Full rankings → {info['url'].split('://', 1)[-1]}", font=F("b", 19), fill=sc.MUTED)
    sc.CARDS.mkdir(parents=True, exist_ok=True)
    out = sc.CARDS / f"spotlight-{when.isoformat()}-{theme}.png"
    img.save(out, optimize=True)
    return out


W_ = sc.W


# --------------------------------------------------------------------------- message

def compose_spotlight(when: dt.date | None = None, theme: str | None = None) -> dict | None:
    if when is None and dt.datetime.now(dt.timezone.utc) < dt.datetime(2026, 10, 27, 4, tzinfo=dt.timezone.utc):
        return None                                               # first Spotlight: 05:07 UTC Oct 27
    when = when or dt.datetime.now(dt.timezone.utc).date()
    slot = int(os.environ.get("SPOTLIGHT_SLOT") or 0)          # 0, 1, 2 = three posts a day
    theme = theme or THEMES[(when.toordinal() * 3 + slot) % len(THEMES)]
    hist, latest = load()
    info = build(theme, hist, latest)
    if not info and theme == "rising":
        theme, info = "countries", build("countries", hist, latest)
    if not info:
        return None
    site = SITE.split("://", 1)[-1]
    path = card(info, theme, when, site, slot)
    medals = ["🥇", "🥈", "🥉"] + [f"{i}." for i in range(4, 11)]
    lines = [info["intro"], ""]
    for i, (badge, name, val, bar, extra) in enumerate(info["rows"][:10]):
        unit = " papers" if info["unit"] == "papers" else (" citations" if info["unit"] == "citations" and not val.startswith("+") else "")
        more = f" ({extra})" if extra and info["unit"] == "growth" else ""
        lines.append(f"{medals[i]} {name} — {val}{unit}{more}")
    lines += ["", f"See the full rankings and search any country or university 👉 {info['url']}", "",
              " ".join(["#Research", "#Science"] + [t for t in info["tags"] if t] + ["#ResearchBoard"])]
    short = [info["intro"][:110]]
    for i, (badge, name, val, *_r) in enumerate(info["rows"][:3]):
        short.append(f"{medals[i]} {name if len(name) <= 42 else name[:40].rsplit(' ', 1)[0] + '…'} — {val}")
    short += [f"More: {info['url'].split('://', 1)[-1]}", "#Science #Research"]
    sh = "\n".join(short)
    while len(sh) > 295 and len(short) > 3:
        short.pop(-3); sh = "\n".join(short)
    rel = path.relative_to(ROOT / "posts" / "images")
    return {"day": f"{when.isoformat()}-{theme}", "text": "\n".join(lines), "short": sh, "url": info["url"],
            "title": info["title"], "card_path": path, "card_url": f"{SITE}/blog/images/{rel.as_posix()}"}


if __name__ == "__main__":
    if "--all" in sys.argv:
        base = dt.date(2026, 10, 26)
        for i, t in enumerate(THEMES):
            m = compose_spotlight(base + dt.timedelta(days=i), t)
            print("=" * 20, t, "\n" + (m["text"] if m else "(skipped)") + ("\n--- short (%d) ---\n%s" % (len(m["short"]), m["short"]) if m else ""))
    else:
        m = compose_spotlight()
        print(m["text"] if m else "nothing")
        if m:
            print("Card written:", m["card_path"].relative_to(ROOT))
