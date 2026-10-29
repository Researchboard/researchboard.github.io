#!/usr/bin/env python3
"""
Directory of every university in OpenAlex that has published at least one paper
(~30,000, type "education"). Refreshed once a week (about 150 API calls).

  data/universities/index.json   countries with university counts + world top 300
  data/universities/<CC>.json    every university in that country

Row format (kept short so country files stay small):
  [id, name, city, papers_this_year, papers_last_year, total_papers, citations, h_index, open_access_share,
   spike_flag, typical_year, website]   spike_flag = 1 when OpenAlex shows a sudden 4x jump (usually a bulk upload)
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from update_data import openalex  # noqa: E402  (shares the API key, rate limit and retries)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "universities"
REFRESH_DAYS = 6


def fresh() -> bool:
    try:
        meta = json.loads((OUT / "index.json").read_text(encoding="utf-8"))
        age = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(meta["generated"])
        return age.days < REFRESH_DAYS
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
        return False


def fetch_all() -> list[dict]:
    rows, cursor, pages = [], "*", 0
    sel = "id,display_name,country_code,geo,works_count,cited_by_count,summary_stats,counts_by_year,homepage_url"
    while cursor and pages < 400:
        data = openalex("institutions", filter="type:education,works_count:>0", per_page=200,
                        cursor=cursor, select=sel)
        rows += data.get("results", [])
        cursor = data.get("meta", {}).get("next_cursor")
        pages += 1
        if not data.get("results"):
            break
    print(f"universities: {len(rows):,} in {pages} pages", flush=True)
    return rows


def main() -> None:
    if fresh() and "--force" not in sys.argv:
        print("university directory is less than a week old, skipping")
        return
    year = dt.date.today().year
    raw = fetch_all()
    if len(raw) < 10000:      # something went wrong; keep last week's files
        print("WARN: too few universities returned, keeping the old directory")
        return
    by_cc: dict[str, list] = {}
    for r in raw:
        cc = (r.get("country_code") or "").upper()
        if len(cc) != 2:
            continue
        cby = {c["year"]: c for c in r.get("counts_by_year") or []}
        now, last = cby.get(year, {}), cby.get(year - 1, {})
        recent = sum(cby.get(y, {}).get("works_count", 0) for y in (year, year - 1))
        oa = sum(cby.get(y, {}).get("oa_works_count", 0) for y in (year, year - 1))
        prior = sorted(cby.get(y, {}).get("works_count", 0) for y in (year - 2, year - 3, year - 4))[1]
        last_n = last.get("works_count", 0)
        spike = 1 if prior and (last_n > 4 * prior or now.get("works_count", 0) > 4 * prior) else 0
        by_cc.setdefault(cc, []).append([
            r["id"].rsplit("/", 1)[-1], r.get("display_name") or "", (r.get("geo") or {}).get("city") or "",
            now.get("works_count", 0), last.get("works_count", 0), r.get("works_count", 0),
            r.get("cited_by_count", 0), (r.get("summary_stats") or {}).get("h_index", 0),
            round(oa / recent * 100) if recent else None, spike, prior, r.get("homepage_url") or ""])
    OUT.mkdir(parents=True, exist_ok=True)
    countries, world = [], []
    for cc, rows in by_cc.items():
        rows.sort(key=lambda x: (-(x[10] if x[9] else x[4]), -x[3], -x[5]))
        (OUT / f"{cc}.json").write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        countries.append([cc, len(rows), sum(x[10] if x[9] else x[4] for x in rows)])
        world += [[cc] + x for x in rows[:300]]
    world = [w for w in world if not w[10]]      # leave out records with a data spike
    world.sort(key=lambda x: (-x[5], -x[4]))
    countries.sort(key=lambda x: -x[2])
    index = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "year": year,
             "total": sum(c[1] for c in countries), "countries": countries, "world": world[:300]}
    names = [[x[0], x[1], cc] for cc, rows in by_cc.items() for x in rows]
    (OUT / "names.json").write_text(json.dumps(names, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {len(countries)} country files")


if __name__ == "__main__":
    main()
