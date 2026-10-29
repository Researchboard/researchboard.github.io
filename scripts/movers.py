#!/usr/bin/env python3
"""
Research trends = "weekly movers": this week vs last week, from our own daily counts.

Each window is 7 fully counted days (the newest days are still being counted by
the journals, and the 1st of the month is skipped because many journals date
papers only by month). A mover is ranked by the change in its SHARE of world
papers, so a quiet week for everyone does not show as a fall for everyone.
"""
from __future__ import annotations

import datetime as dt
import re

MIN = {"countries": 250, "universities": 60, "fields": 0}
CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")


def _windows(days: dict, latest_day: str | None):
    keys = [k for k in sorted(days) if (not latest_day or k <= latest_day) and not k.endswith("-01")]
    if len(keys) < 14:
        return None, None
    return keys[-7:], keys[-14:-7]


def _sum(days, keys, getter):
    out = {}
    for k in keys:
        for key, name, n in getter(days[k]):
            if key not in out:
                out[key] = [name, 0, 0]
            out[key][1] += n
            out[key][2] += 1
    return out


def _countries(day):
    return [(c, c, n) for c, n in (day.get("countries") or {}).items()]


def _fields(day):
    return [(f["name"], f["name"], f["count"]) for f in day.get("fields") or []]


def _insts_hist(day):
    return [(i["id"], i["name"], i["count"]) for i in day.get("institutions") or []]


def _rank(a, b, ta, tb, ndays, minimum, every_day):
    rows = []
    for key, (name, n, seen) in a.items():
        if key not in b:
            continue
        pn, pseen = b[key][1], b[key][2]
        if every_day and (seen < ndays or pseen < ndays):
            continue  # only listed on some days: the gap would look like a fall
        if n < minimum or pn < minimum:
            continue
        sa, sb = n / ta, pn / tb
        rows.append({"id": key, "name": name, "now": n, "prev": pn,
                     "share": round(sa * 100, 3), "pct": round((sa / sb - 1) * 100, 1)})
    up = sorted([r for r in rows if r["pct"] > 0], key=lambda r: -r["pct"])
    down = sorted([r for r in rows if r["pct"] < 0], key=lambda r: r["pct"])
    return up, down


def compute(history: dict, latest: dict | None, inst_file: dict | None = None) -> dict | None:
    days = history.get("days", {})
    a, b = _windows(days, (latest or {}).get("latest_day"))
    if not a:
        return None
    ta = sum(days[k].get("papers") or 0 for k in a)
    tb = sum(days[k].get("papers") or 0 for k in b)
    out = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "week": [a[0], a[-1]], "prev_week": [b[0], b[-1]],
           "world": {"now": ta, "prev": tb, "pct": round((ta / tb - 1) * 100, 1) if tb else None},
           "daily": [[k, days[k].get("papers") or 0] for k in b + a]}
    names = (latest or {}).get("country_names", {})

    ca, cb = _sum(days, a, _countries), _sum(days, b, _countries)
    up, down = _rank(ca, cb, ta, tb, 7, MIN["countries"], False)
    for r in up + down:
        r["name"] = names.get(r["id"], r["id"])
    out["countries"] = {"up": up[:15], "down": down[:15]}

    fa, fb = _sum(days, a, _fields), _sum(days, b, _fields)
    fta, ftb = sum(v[1] for v in fa.values()), sum(v[1] for v in fb.values())
    up, down = _rank(fa, fb, fta, ftb, 7, 0, False)
    out["fields"] = {"up": up, "down": down}

    # universities: prefer the top-200-per-day file once it covers both weeks
    idays = (inst_file or {}).get("days", {})
    if all(k in idays for k in a + b):
        inames = inst_file.get("names", {})
        get = lambda k: [(i, inames.get(i, i), n) for i, n in idays[k].items()]
        ia = {}; ib = {}
        for keys, dst in ((a, ia), (b, ib)):
            for k in keys:
                for key, name, n in get(k):
                    dst.setdefault(key, [name, 0, 0]); dst[key][1] += n; dst[key][2] += 1
        up, down = _rank(ia, ib, ta, tb, 7, MIN["universities"], False)
    else:
        ia, ib = _sum({k: days[k] for k in a}, a, _insts_hist), _sum({k: days[k] for k in b}, b, _insts_hist)
        up, down = _rank(ia, ib, ta, tb, 7, MIN["universities"], True)
    out["universities"] = {"up": up[:15], "down": down[:15]}
    return out


def ticker_text(m: dict, n: int = 3) -> list[str]:
    """Short lines for a social post."""
    def fmt(r):
        return f'{"▲" if r["pct"] > 0 else "▼"} {r["name"]} {r["pct"]:+.0f}%'
    lines = []
    if m["countries"]["up"]:
        lines.append("Rising countries: " + ", ".join(fmt(r) for r in m["countries"]["up"][:n]))
    if m["fields"]["up"]:
        lines.append("Rising fields: " + ", ".join(fmt(r) for r in m["fields"]["up"][:n]))
    if m["universities"]["up"]:
        lines.append("Rising universities: " + ", ".join(fmt(r) for r in m["universities"]["up"][:n]))
    return lines
