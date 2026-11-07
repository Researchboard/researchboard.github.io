"""
Plain checks that keep ResearchBoard's posts and cards honest.

OpenAlex is matched automatically, so a few numbers can mislead readers:
  * government parent bodies (e.g. "State Council of the People's Republic of China") collect the papers
    of every institute under them and look like a giant "institution";
  * one-day jumps happen when a big conference or a special issue publishes hundreds of papers at once
    (e.g. the ADIPEC energy conference in Abu Dhabi on Nov 2, 2026).
These helpers find such cases so the cards and posts can leave them out or add a short note.
"""
from __future__ import annotations

import re

SPIKE_NOTE = "an unusual one-day jump, which can happen when a big conference or special issue publishes many papers at once"

SPIKE_SHORT = "unusual one-day jump (e.g. a big conference or special issue)"


def usual_daily(days: dict, iid: str, back: int = 14) -> int | None:
    """An institution's typical papers per day over the last two weeks (an upper bound if it was
    below the daily top list)."""
    keys = sorted(days)[-back:]
    seen, floors = [], []
    for k in keys:
        lst = days[k].get("institutions") or []
        hit = next((x["count"] for x in lst if x.get("id") == iid), None)
        if hit is not None:
            seen.append(hit)
        elif lst:
            floors.append(min(x["count"] for x in lst))
    pool = seen if len(seen) >= len(keys) // 2 else (seen + floors)
    return sorted(pool)[len(pool) // 2] if pool else None


def sane_market_institutions(m: dict, inst_country: dict | None = None, days: dict | None = None) -> list[dict]:
    """Market institutions whose rise is believable: not bigger than their own country's rise (or, if the
    country is unknown, the biggest country's), nor a quarter of the world's change. Bigger jumps are
    OpenAlex re-crediting old papers, not new ones."""
    c_add = {c["code"]: c.get("added", 0) for c in m.get("countries") or []}
    top_c = max(c_add.values(), default=0)
    lim = min(top_c, 0.25 * max(m.get("papers_added", 0), 1))
    out = []
    for i in real_institutions(m.get("institutions")):
        cc = (inst_country or {}).get(i.get("id"))
        own = c_add.get(cc, min(c_add.values(), default=0)) if cc else lim
        usual = usual_daily(days, i.get("id")) if days else None
        cap = 10 * usual if usual else lim   # a day can bring in a backlog, but not 10x the usual daily output
        if 0 < i.get("added", 0) <= min(lim, own, cap):
            out.append(i)
    return out


GOVERNMENT_BODY = re.compile(
    r"^(State Council of|United States Department of|U\.?S\.? Department of|Department of |Ministry |"
    r"Ministère|Ministerio|Ministério|Office of Science$|Government of|National Health Service$|Federal Ministry)",
    re.I)


def is_government_body(name: str | None) -> bool:
    return bool(GOVERNMENT_BODY.search((name or "").strip()))


def real_institutions(rows: list[dict] | None) -> list[dict]:
    """Institution rows without government parent bodies."""
    return [r for r in rows or [] if not is_government_body(r.get("name"))]


def institution_spike(days: dict, day: str, iid: str, count: int, back: int = 14) -> bool:
    """True when an institution's papers on `day` are 3x (or more) its usual daily level."""
    keys = [k for k in sorted(days) if k < day][-back:]
    seen, floors = [], []
    for k in keys:
        lst = days[k].get("institutions") or []
        hit = next((x["count"] for x in lst if x.get("id") == iid), None)
        if hit is not None:
            seen.append(hit)
        elif lst:
            floors.append(min(x["count"] for x in lst))  # it wasn't in the list, so it had fewer than this
    if seen and len(seen) >= len(keys) // 2:
        usual = sorted(seen)[len(seen) // 2]
    elif floors:
        usual = sorted(floors)[len(floors) // 2]
    else:
        return False
    return count >= 100 and count >= 3 * max(usual, 20)


def country_spike(days: dict, keys: list[str], code: str) -> tuple[str, int] | None:
    """(day, papers) when one day of the week holds 3x (or more) the week's typical day for a country."""
    vals = [((days.get(k) or {}).get("countries") or {}).get(code, 0) for k in keys]
    if len(vals) < 4:
        return None
    med = sorted(vals)[len(vals) // 2]
    top = max(vals)
    if top >= 100 and top >= 3 * max(med, 10):
        return keys[vals.index(top)], top
    return None
