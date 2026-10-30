#!/usr/bin/env python3
"""
US universities that award master's or PhD degrees, for the US university map (homepage + /us-universities/).

Sources (all official US government data, IPEDS = Integrated Postsecondary Education Data System):
  Urban Institute Education Data API (IPEDS tables): directory, tuition, fall enrollment of international
      ("nonresident") students, degrees awarded by field, admissions, student-faculty ratio
  NCES IPEDS "IC" complete data file: application fees (undergraduate and graduate), room and board

  data/us-unis.json      one row per university (see KEYS)

Runs monthly; the source data changes once a year.
"""
from __future__ import annotations

import csv
import functools
import datetime as dt
import io
import json
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

print = functools.partial(print, flush=True)  # noqa: A001  (show progress in the Actions log)
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "us-unis.json"
API = "https://educationdata.urban.org/api/v1/college-university/"
NCES = "https://nces.ed.gov/ipeds/datacenter/data/"
UA = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBoard/1.0; +https://researchboard.net)"}
REFRESH_DAYS = 25
STATES = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR "
             "PA RI SC SD TN TX UT VT VA WA WV WI WY".split())

KEYS = ["id", "n", "alias", "city", "st", "lat", "lon", "ctl", "cc", "hbcu", "lg", "loc", "web", "app", "aid", "np",
        "gtu", "utu", "afg", "afu", "rb", "ge", "gi", "ue", "ui", "ms", "phd", "prof", "mf", "pf", "ar", "sfr", "toefl"]


def get(url: str, binary: bool = False, timeout: int = 120, tries: int = 4):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                b = r.read()
                return b if binary else json.loads(b.decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            if attempt == tries - 1:
                raise
            print("retry", url[:110], e)
            time.sleep(3 * (attempt + 1))


def rows(path: str, _tries: int = 4, **params) -> list[dict]:
    """All result rows of one Urban Institute endpoint, following the 'next' pages."""
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    out, pages = [], 0
    while url and pages < 60:
        j = get(url, tries=_tries if not out else 4)
        out += j.get("results", [])
        url = j.get("next")
        pages += 1
    print(f"  {path} {params or ''}: {len(out)} rows")
    return out


def first_year(path_fmt: str, years, **params) -> tuple[int, list[dict]]:
    for y in years:
        try:
            r = rows(path_fmt.format(y=y), _tries=2, **params)
        except Exception as e:  # noqa: BLE001
            print("no data", path_fmt.format(y=y), e)
            continue
        if r:
            return y, r
    return 0, []


def num(v):
    try:
        f = float(v)
        return None if f < 0 else f
    except (TypeError, ValueError):
        return None


def ic_fees(years) -> tuple[int, dict]:
    """Application fees and room/board from the IPEDS IC complete data file (newest year available)."""
    for y in years:
        try:
            z = zipfile.ZipFile(io.BytesIO(get(f"{NCES}IC{y}.zip", binary=True, timeout=60, tries=2)))
        except Exception as e:  # noqa: BLE001
            print("no IC file for", y, e)
            continue
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        text = z.read(name).decode("utf-8-sig", "replace")
        if "APPLFEEG" not in text.split("\n", 1)[0].upper():
            print(f"IC{y}: no application fee columns yet (provisional file), trying an older year")
            continue
        out = {}
        for r in csv.DictReader(io.StringIO(text)):
            r = {k.strip().lstrip("\ufeff").upper(): v for k, v in r.items() if k}
            rb = num(r.get("RMBRDAMT"))
            if rb is None and num(r.get("ROOMAMT")) is not None:
                rb = (num(r.get("ROOMAMT")) or 0) + (num(r.get("BOARDAMT")) or 0)
            out[int(r["UNITID"])] = {"afu": num(r.get("APPLFEEU")), "afg": num(r.get("APPLFEEG")), "rb": rb}
        print(f"IC{y}: application fees for {len(out)} institutions")
        return y, out
    # NCES download not reachable: use the copy saved in the repository (data/ipeds-fees.csv: UNITID,APPLFEEU,APPLFEEG,RB,YEAR)
    try:
        out, y = {}, 0
        for r in csv.DictReader(io.StringIO((ROOT / "data" / "ipeds-fees.csv").read_text(encoding="utf-8"))):
            out[int(r["UNITID"])] = {"afu": num(r["APPLFEEU"]), "afg": num(r["APPLFEEG"]), "rb": num(r["RB"])}
            y = int(r["YEAR"])
        print(f"fees from saved copy ({y}): {len(out)} institutions")
        return y, out
    except Exception as e:  # noqa: BLE001
        print("no saved fees copy", e)
    return 0, {}


def main() -> None:
    try:
        old = json.loads(OUT.read_text(encoding="utf-8"))
        age = (dt.date.today() - dt.date.fromisoformat(old["updated"])).days
        if age < REFRESH_DAYS and "--force" not in sys.argv:
            print(f"US universities are {age} days old, skipping")
            return
    except Exception:  # noqa: BLE001
        pass
    t0 = time.time()
    this = dt.date.today().year
    years = list(range(this - 1, this - 6, -1))

    dy, d = first_year("ipeds/directory/{y}/", years, offering_grad=1)
    print(f"directory {dy}: {len(d)} institutions offering graduate study")
    unis = {}
    for x in d:
        if x.get("currently_active_ipeds") != 1 or x.get("degree_granting") != 1 or x.get("state_abbr") not in STATES:
            continue
        if x.get("offering_highest_degree") not in (11, 12, 13, 14, 20) or x.get("latitude") in (None, -2) or x.get("longitude") in (None, -2):
            continue
        unis[x["unitid"]] = {
            "id": x["unitid"], "n": x["inst_name"], "alias": (x.get("inst_alias") or "")[:80], "city": x.get("city"), "st": x["state_abbr"],
            "lat": round(x["latitude"], 4), "lon": round(x["longitude"], 4), "ctl": x.get("inst_control"),
            "cc": x.get("cc_basic_2021") if (x.get("cc_basic_2021") or 0) > 0 else None,
            "hbcu": 1 if x.get("hbcu") == 1 else 0, "lg": 1 if x.get("land_grant") == 1 else 0, "loc": x.get("urban_centric_locale"),
            "web": x.get("url_school") or "", "app": x.get("url_application") or "", "aid": x.get("url_fin_aid") or "", "np": x.get("url_netprice") or ""}
    ids = set(unis)

    ty, tu = first_year("ipeds/academic-year-tuition/{y}/", years)
    best = {}
    for r in tu:
        if r["unitid"] in ids and r.get("tuition_type") in (3, 4) and num(r.get("tuition_fees_ft")):
            k = (r["unitid"], r["level_of_study"])
            if r["tuition_type"] == 4 or k not in best:      # out-of-state (= what international students pay at public universities)
                best[k] = num(r["tuition_fees_ft"])
    for (u, lvl), v in best.items():
        unis[u]["gtu" if lvl == 2 else "utu"] = int(v)
    print(f"tuition {ty}: {len(best)} values")

    for lvl, (tot, intl) in (("graduate", ("ge", "gi")), ("undergraduate", ("ue", "ui"))):
        er = []
        for race in (8, 99):                                   # 8 = nonresident (international), 99 = all students
            ey, part = first_year("ipeds/fall-enrollment/{y}/" + lvl + "/race/sex/", years, sex=99, ftpt=99, race=race)
            er += part
        for r in er:
            if r["unitid"] in ids and r.get("degree_seeking") == 99 and r.get("class_level") == 99 and r.get("race") in (8, 99):
                v = num(r.get("enrollment_fall"))
                if v is not None:
                    unis[r["unitid"]][intl if r["race"] == 8 else tot] = int(v)
        print(f"{lvl} enrollment {ey}: {len(er)} rows")

    for lvl, key, fk in ((9, "ms", "mf"), (22, "phd", "pf"), (23, "prof", None)):
        cy, cr = first_year("ipeds/completions-cip-2/{y}/", years, race=99, sex=99, majornum=1, award_level=lvl)
        fields: dict[int, list] = {}
        for r in cr:
            u, n = r["unitid"], num(r.get("awards"))
            if u not in ids or not n:
                continue
            cip = int(r.get("cipcode") or 0)
            if cip in (99, 990000):                            # "all fields" total row
                unis[u][key] = int(n)
            elif cip >= 10000 and cip % 10000 == 0:            # 2-digit field family
                fields.setdefault(u, []).append([cip // 10000, int(n)])
        for u, f in fields.items():
            unis[u].setdefault(key, sum(n for _, n in f))
            if fk:
                unis[u][fk] = sorted(f, key=lambda x: -x[1])[:6]
        print(f"completions level {lvl} ({cy}): {len(cr)} rows")

    ay, ad = first_year("ipeds/admissions-enrollment/{y}/", years, sex=99)
    for r in ad:
        if r["unitid"] in ids and num(r.get("number_applied")) and num(r.get("number_admitted")) is not None:
            unis[r["unitid"]]["ar"] = round(num(r["number_admitted"]) / num(r["number_applied"]), 3)
    _, rq = first_year("ipeds/admissions-requirements/{y}/", years)
    for r in rq:
        if r["unitid"] in ids and r.get("reqt_toefl") not in (None, -1, -2):
            unis[r["unitid"]]["toefl"] = r["reqt_toefl"]
    _, sf = first_year("ipeds/student-faculty-ratio/{y}/", years)
    for r in sf:
        if r["unitid"] in ids and num(r.get("student_faculty_ratio")):
            unis[r["unitid"]]["sfr"] = int(num(r["student_faculty_ratio"]))

    fy, fees = ic_fees([this - 1, this - 2, this - 3, this - 4])
    for u, f in fees.items():
        if u in unis:
            for k, v in f.items():
                if v is not None:
                    unis[u][k] = int(v)

    # keep universities that actually award master's or research doctorates
    keep = [x for x in unis.values() if (x.get("ms") or 0) + (x.get("phd") or 0) > 0]
    if len(keep) < 500:
        sys.exit(f"Only {len(keep)} universities found — something is wrong with the source data, keeping the old file")
    keep.sort(key=lambda x: -((x.get("gi") or 0) * 3 + (x.get("ge") or 0)))
    data = [[x.get(k) for k in KEYS] for x in keep]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"updated": dt.date.today().isoformat(), "years": {"directory": dy, "tuition": ty, "fees": fy},
                               "keys": KEYS, "rows": data}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"US universities: {len(keep)} with master's or PhD programs, {round(time.time() - t0)}s, "
          f"{OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
