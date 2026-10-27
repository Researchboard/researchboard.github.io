#!/usr/bin/env python3
"""
Country Watch (Bangladesh by default): what one country added to the research
record in the last 24 hours. Runs once a day (03:37 UTC = 9:37 am in Dhaka):

    python scripts/country_watch.py     save today's snapshot, compare with yesterday's,
                                        draw the card (posts/images/cards/bd-<date>.png)

The Facebook post is sent by post_social.py (SOCIAL_MODE=bd) using compose().
Country: FOCUS_COUNTRY (default BD).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import update_data as ud  # noqa: E402
import social_card as sc  # noqa: E402

ROOT = ud.ROOT
DATA = ud.DATA
CC = (os.environ.get("FOCUS_COUNTRY") or "BD").upper()
SNAP = DATA / f"{CC.lower()}_snapshot.json"
HIST = DATA / f"{CC.lower()}_history.json"
SITE = os.environ.get("SITE_URL", "https://researchboard.net").rstrip("/")
NAMES = {"BD": ("Bangladesh", "")}


def snapshot(today: dt.date) -> dict:
    flt = f"publication_year:>{today.year - 2},{ud.PAPER_TYPES},authorships.countries:{CC}"
    groups = ud.openalex("works", filter=flt, group_by="authorships.institutions.lineage")
    total = int(groups.get("meta", {}).get("count") or 0)
    articles = int(ud.openalex("works", filter=flt.replace(ud.PAPER_TYPES, "type:article"), per_page=1,
                               select="id")["meta"]["count"])
    inst = {ud.short_id(g["key"]): [g.get("key_display_name") or "Unknown", g["count"]]
            for g in groups.get("group_by", []) if g.get("key")}
    # keep only this country's own institutions (co-authors abroad appear in the groups too)
    store = ud.load_json(ud.INST_FILE, {"days": {}, "names": {}, "country": {}})
    known = store.setdefault("country", {})
    ud.institution_countries(list(inst), known)
    ud.save_json(ud.INST_FILE, store)
    inst = {i: v for i, v in inst.items() if known.get(i) == CC}
    return {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "filter": flt,
            "total": total, "articles": articles, "institutions": inst}


def compare(now: dict, prev: dict, usual: list[int]) -> dict | None:
    if not prev or prev.get("filter") != now["filter"]:
        return None
    t0, t1 = dt.datetime.fromisoformat(prev["at"]), dt.datetime.fromisoformat(now["at"])
    hours = (t1 - t0).total_seconds() / 3600
    if not 12 <= hours <= 36:
        return None
    added = now["total"] - prev["total"]
    med = sorted(usual)[len(usual) // 2] if len(usual) >= 3 else None
    flagged = ""
    if added <= 0:
        flagged = "no growth (database update pending)"
    elif med and (added > 4 * med or added < med / 4):
        flagged = f"unusual jump ({added:,} vs usual {med:,})"
    rows = []
    for iid, (name, n) in now["institutions"].items():
        if iid in prev["institutions"]:
            d = n - prev["institutions"][iid][1]
            if d > 0:
                rows.append({"id": iid, "name": name, "added": d})
    rows.sort(key=lambda r: -r["added"])
    return {"from": prev["at"], "to": now["at"], "hours": round(hours, 1), "papers_added": added,
            "articles_added": now["articles"] - prev.get("articles", now["articles"]),
            "institutions_added": len(rows), "institutions": rows[:10], "flagged": flagged}


# --------------------------------------------------------------------------- card

GREEN, GREEN2, RED = (0, 82, 60), (0, 128, 92), (244, 42, 65)


def card(m: dict) -> Path:
    W, H = sc.W, sc.H
    img = Image.new("RGB", (W, H), GREEN)
    d = ImageDraw.Draw(img, "RGBA")
    for x in range(W):
        t = x / (W - 1)
        d.line([(x, 0), (x, H)], fill=tuple(int(GREEN[i] + (GREEN2[i] - GREEN[i]) * t) for i in range(3)))
    d.ellipse([930, 330, 1330, 730], fill=RED + (200,))          # the flag's red sun
    F, WHITE, MUTED, GOLD = sc.font, (255, 255, 255), (196, 236, 216), (255, 224, 120)
    sc.logo(d, 64, 52)
    d.text((136, 50), "ResearchBoard", font=F("x", 34), fill=WHITE)
    d.text((137, 92), "Every Paper. Every Citation. Every Discovery.", font=F("r", 18), fill=MUTED)
    d.text((W - 64, 66), SITE.split("://", 1)[-1], font=F("b", 22), fill=MUTED, anchor="ra")
    name = NAMES.get(CC, (CC, ""))[0]
    t0, t1 = dt.datetime.fromisoformat(m["from"]), dt.datetime.fromisoformat(m["to"])
    bd = dt.timezone(dt.timedelta(hours=6))
    a, b = t0.astimezone(bd), t1.astimezone(bd)
    d.text((64, 152), f"{name.upper()} RESEARCH  ·  LAST 24 HOURS", font=F("b", 20), fill=GOLD)
    d.text((64, 180), f"{a:%b} {a.day}, {a:%I:%M %p} → {b:%b} {b.day}, {b:%I:%M %p} (Dhaka time)",
           font=F("x", 30), fill=WHITE)
    d.text((64, 236), f"+{m['papers_added']:,}", font=F("x", 84), fill=WHITE)
    w = d.textlength(f"+{m['papers_added']:,}", font=F("x", 84))
    d.text((64 + w + 18, 262), "new papers", font=F("b", 30), fill=MUTED)
    d.text((64, 336), f"{m['articles_added']:,} journal articles  ·  {m['institutions_added']:,} institutions contributed",
           font=F("b", 24), fill=GOLD)
    d.text((64, 392), "MOST ACTIVE INSTITUTIONS", font=F("b", 16), fill=MUTED)
    for i, r in enumerate(m["institutions"][:5]):
        y = 420 + i * 38
        nm = r["name"] if len(r["name"]) <= 46 else r["name"][:45] + "…"
        d.text((64, y), f"{i + 1}. {nm}", font=F("b", 23), fill=WHITE)
        d.text((800, y), f"+{r['added']:,}", font=F("x", 23), fill=GOLD, anchor="ra")
    sc.CARDS.mkdir(parents=True, exist_ok=True)
    out = sc.CARDS / f"{CC.lower()}-{b.date().isoformat()}.png"
    img.save(out, optimize=True)
    return out


# --------------------------------------------------------------------------- post text

def compose() -> dict | None:
    hist = ud.load_json(HIST, {"days": []})
    m = hist["days"][-1] if hist.get("days") else None
    if not m or m.get("flagged"):
        return None
    t1 = dt.datetime.fromisoformat(m["to"])
    if (dt.datetime.now(dt.timezone.utc) - t1).total_seconds() > 6 * 3600:
        return None                                   # stale: only post right after a fresh comparison
    name, local = NAMES.get(CC, (CC, ""))
    bd = dt.timezone(dt.timedelta(hours=6))
    a, b = dt.datetime.fromisoformat(m["from"]).astimezone(bd), t1.astimezone(bd)
    slug = name.lower().replace(" ", "-")
    lines = [f"{'🇧🇩 ' if CC == 'BD' else ''}{name} research — last 24 hours",
             f"⏱️ {a:%b} {a.day}, {a:%I:%M %p} → {b:%b} {b.day}, {b:%I:%M %p} (Dhaka time)", "",
             f"📄 +{m['papers_added']:,} new papers with {name}-based authors",
             f"📰 {m['articles_added']:,} of them journal articles",
             f"🏛️ {m['institutions_added']:,} {name} institutions contributed"]
    if m["institutions"]:
        lines += ["", "Most active institutions:"]
        medals = ["🥇", "🥈", "🥉", "4.", "5.", "6.", "7.", "8.", "9.", "10."]
        lines += [f"{medals[i]} {r['name']} +{r['added']:,}" for i, r in enumerate(m["institutions"][:10])]
    url = f"{SITE}/country/{slug}.html"
    lines += ["", f"{name} papers day by day 👉 {url}", "",
              f"#{name.replace(' ', '')} #{name.replace(' ', '')}Research #Research #Science #ResearchBoard"]
    day = b.date().isoformat()
    path = sc.CARDS / f"{CC.lower()}-{day}.png"
    rel = path.relative_to(ROOT / "posts" / "images")
    return {"day": day, "text": "\n".join(lines), "short": "\n".join(lines[:6]), "url": url,
            "title": f"{name} research — last 24 hours", "card_path": path if path.exists() else None,
            "card_url": f"{SITE}/blog/images/{rel.as_posix()}" if path.exists() else None}


def main() -> int:
    today = dt.datetime.now(dt.timezone.utc).date()
    now = ud.safe(f"{CC} snapshot", lambda: snapshot(today))
    if not now:
        return 1
    prev = ud.load_json(SNAP, {})
    hist = ud.load_json(HIST, {"days": []})
    usual = [x["papers_added"] for x in hist["days"] if not x.get("flagged")][-30:]
    m = compare(now, prev, usual)
    ud.save_json(SNAP, now)
    print(f"{CC} snapshot: {now['total']:,} papers, {now['articles']:,} articles, {len(now['institutions'])} institutions")
    if not m:
        print("No comparison yet (first run, or the previous snapshot is not ~24 hours old).")
        return 0
    hist["days"] = (hist["days"] + [m])[-120:]
    ud.save_json(HIST, hist)
    print(f"Last {m['hours']} h: +{m['papers_added']:,} papers, {m['institutions_added']} institutions"
          + (f"  [FLAGGED: {m['flagged']}]" if m["flagged"] else ""))
    if not m["flagged"]:
        print("Card written:", card(m).relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
