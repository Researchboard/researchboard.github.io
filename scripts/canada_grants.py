#!/usr/bin/env python3
"""
Active research grants in Canada, for the Study Abroad › Canada active grants tab.

  NSERC (science and engineering)  NSERC Awards Database, latest fiscal year, one search per topic.
                                  Each award page gives the institution and the instalment ("2 of 5"),
                                  which tells us until when the grant runs. Pages are cached.
  CIHR  (health)                  CIHR "Grants and Awards" open data (quarterly spreadsheet),
                                  all grants whose end date is still in the future.

  data/grants/ca-index.json            topics, counts, featured grants, refresh date
  data/grants/ca-nserc-<slug>.json     up to 60 active NSERC grants per topic
  data/grants/ca-cihr.json             active CIHR grants (searched in the browser)
  data/grants/ca-nserc-cache.json      award-page details already fetched

Runs weekly and stops after a time budget so the daily job stays short; unfinished topics continue next run.
"""
from __future__ import annotations

import datetime as dt
import html
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "grants"
NSERC = "https://nserc-crsng.canada.ca/en/awards-database"
CIHR_PKG = "https://open.canada.ca/data/api/action/package_show?id=49edb1d7-5cb4-4fa7-897c-515d1aad5da3"
UA = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBoard/1.0; +https://researchboard.net)"}
REFRESH_DAYS = 6
BUDGET_S = 420            # at most 7 minutes per run
KEEP = 40

TOPICS = ["machine learning", "artificial intelligence", "robotics", "computer vision", "cybersecurity", "data science",
          "quantum", "photonics", "semiconductors", "wireless communication", "solar cells", "batteries", "hydrogen",
          "renewable energy", "catalysis", "polymers", "nanomaterials", "climate change", "water treatment",
          "environmental chemistry", "ecology", "fisheries", "forestry", "agriculture", "food science", "microbiology",
          "genomics", "neuroscience", "biomedical engineering", "structural engineering", "transportation",
          "mining", "remote sensing", "mathematics", "statistics", "astrophysics"]

# programmes run by a professor that can pay graduate students; scholarships and supplements are left out
KEEP_PROG = re.compile(r"Discovery Grants|Discovery Horizons|Alliance|Canada Research Chair|CREATE|Collaborative Research and Development|"
                       r"Strategic|Synergy|Subatomic|Industrial Research Chair|Chairs|Research Partnerships|Idea to Innovation|"
                       r"Network|Ship Time|Northern Research", re.I)
DROP_PROG = re.compile(r"Scholarship|Fellowship|Supplement|Tools and Instruments|Undergraduate|Postdoctoral|Connect|Engage|"
                       r"Award|Prize|Science Promotion|PromoScience|Launch", re.I)
TRAIN_PROG = re.compile(r"CREATE", re.I)
CENTER_PROG = re.compile(r"Network|Synergy|Subatomic|Chair|Alliance Missions", re.I)

T0 = time.time()


def left() -> float:
    return BUDGET_S - (time.time() - T0)


def get(url: str, binary: bool = False, timeout: int = 40):
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b = r.read()
                return b if binary else b.decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                raise
            print("retry", url[:90], e)
            time.sleep(3)


def slug(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def person(n: str) -> str:
    """'ABDEL SAMAD, Bassel' -> 'Bassel Abdel Samad'"""
    n = re.sub(r"\s+", " ", n or "").strip()
    if "," in n:
        last, first = [x.strip() for x in n.split(",", 1)]
        n = f"{first} {last}".strip()
    return " ".join(w.capitalize() if (w.isupper() and len(w) > 1) else w for w in n.split())


def load(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def save(p: Path, obj) -> None:
    p.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


# ------------------------------------------------------------------------------------------------ NSERC
def nserc_url(fy: int, kw: str = "", lo: str = "", hi: str = "", page: int = 0) -> str:
    q = {"fiscal_year_from": fy, "fiscal_year_to": fy, "competition_year_from": 0, "competition_year_to": 0,
         "person_name": "", "keywords": kw, "institution_type": 0, "area_code": "", "subject_code": "", "department": "",
         "award_amount_min": lo, "award_amount_max": hi, "report_type": 0, "op": "Search"}
    if page:
        q["page"] = page
    return NSERC + "?" + urllib.parse.urlencode(q)


ROW = re.compile(r"<tr[^>]*>\s*<td>(.*?)</td>\s*<td>\s*<a href=\"/en/awards-database/(\d+)\">(.*?)</a>\s*</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>\s*<td>(.*?)</td>", re.S)


def nserc_rows(html_text: str) -> list[dict]:
    out = []
    for name, aid, title, amt, fy, prog in ROW.findall(html_text):
        clean = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
        out.append({"name": clean(name), "id": aid, "title": clean(title), "amt": int(re.sub(r"[^\d]", "", clean(amt)) or 0),
                    "prog": clean(prog)})
    return out


def latest_fy() -> int:
    y = dt.date.today().year
    for fy in (y, y - 1, y - 2, y - 3):
        if nserc_rows(get(nserc_url(fy, "", "500000"))):
            return fy
    raise RuntimeError("no NSERC fiscal year found")


ITEM = re.compile(r'award-db-item-label">(.*?)</span>\s*<span class="award-db-item-value">(.*?)</span>', re.S)


def nserc_detail(aid: str) -> dict:
    t = get(f"{NSERC}/{aid}")
    d = {html.unescape(re.sub(r"<[^>]+>", "", k)).strip(): html.unescape(re.sub(r"<[^>]+>", " ", v)).strip() for k, v in ITEM.findall(t)}
    inst = re.findall(r"\d+", d.get("Installment", ""))
    return {"org": d.get("Institution", ""), "prov": d.get("Province", ""), "dept": d.get("Department", ""),
            "i": int(inst[0]) if inst else 0, "n": int(inst[1]) if len(inst) > 1 else 0}


def nserc_topic(fy: int, t: str, cache: dict) -> dict | None:
    rows, total = [], 0
    for lo, hi in (("200000", ""), ("80000", "199999"), ("45000", "79999"), ("25000", "44999")):
        page = 0
        while page < 4:
            h = get(nserc_url(fy, t, lo, hi, page))
            r = nserc_rows(h)
            m = re.search(r"of ([\d,]+) awards", h) or re.search(r"Showing all ([\d,]+) awards", h)
            if page == 0 and m:
                total += int(m.group(1).replace(",", ""))
            rows += r
            if len(r) < 25:
                break
            page += 1
            time.sleep(0.3)
        good = [x for x in rows if KEEP_PROG.search(x["prog"]) and not DROP_PROG.search(x["prog"])]
        if len({x["name"] for x in good}) >= KEEP * 1.2:
            break
    good = [x for x in rows if KEEP_PROG.search(x["prog"]) and not DROP_PROG.search(x["prog"])]
    best: dict[str, dict] = {}
    for x in sorted(good, key=lambda x: -x["amt"]):
        best.setdefault(x["name"], x)
    picked = list(best.values())[: int(KEEP * 1.2)]
    need = [x["id"] for x in picked if x["id"] not in cache]
    if need and left() < 25 + len(need) * 0.4:
        return None                               # out of time: finish this topic next run
    from concurrent.futures import ThreadPoolExecutor

    def fetch(aid):
        try:
            return aid, nserc_detail(aid)
        except Exception as e:  # noqa: BLE001
            print("NSERC detail failed", aid, e)
            return aid, None
    with ThreadPoolExecutor(4) as ex:
        for aid, d in ex.map(fetch, need):
            if d:
                cache[aid] = d
    out = []
    for x in picked:
        if x["id"] not in cache:
            continue
        d = cache[x["id"]]
        remaining = max(0, d["n"] - d["i"]) if d["n"] else 0
        end_year = fy + 1 + remaining              # fiscal year ends 31 March
        if dt.date(end_year, 3, 31) < dt.date.today():
            continue
        prog = x["prog"]
        out.append({"pi": person(x["name"]), "org": d["org"], "st": d["prov"], "amt": x["amt"], "end": f"{end_year}-03",
                    "title": x["title"], "prog": prog, "kind": "train" if TRAIN_PROG.search(prog) else "ctr" if CENTER_PROG.search(prog) else "lab",
                    "id": x["id"]})
        if len(out) >= KEEP:
            break
    return {"topic": t, "total": total, "fy": fy, "rows": out}


# ------------------------------------------------------------------------------------------------ CIHR
def pick(headers: list[str], *must: str, avoid: tuple[str, ...] = ()) -> int | None:
    for i, h in enumerate(headers):
        e = (h or "").split("_")[0].lower()        # English part of "EnglishName_NomFrancais"
        if all(m in e for m in must) and not any(a in e for a in avoid):
            return i
    return None


def first(*idx):
    return next((i for i in idx if i is not None), None)


def to_date(v) -> dt.date | None:
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(v or ""))
    return dt.date(int(m[1]), int(m[2]), int(m[3])) if m else None


def cihr() -> list[dict]:
    import openpyxl  # installed in the workflow
    res = json.loads(get(CIHR_PKG))["result"]["resources"]
    files = [r for r in res if re.search(r"CIHR Investments \d{4}-\d{2}", r.get("name", ""))]
    files.sort(key=lambda r: r["name"], reverse=True)
    rows: dict[str, dict] = {}
    for r in files[:2][::-1]:                      # previous year first, newest overwrites
        print("CIHR file:", r["name"])
        wb = openpyxl.load_workbook(io.BytesIO(get(r["url"], binary=True, timeout=180)), read_only=True, data_only=True)
        ws = next((wb[n] for n in wb.sheetnames if re.search(r"grant", n, re.I)), wb[wb.sheetnames[0]])
        it = ws.iter_rows(values_only=True)
        hdr = [str(h or "") for h in next(it)]
        print("CIHR sheet", ws.title, "columns:", hdr)
        c = {
            "id": first(pick(hdr, "fundingreferencenumber"), pick(hdr, "reference")),
            "title": pick(hdr, "title", avoid=("program", "competition")),
            "fam": first(pick(hdr, "principal", "family"), pick(hdr, "npi", "family"), pick(hdr, "familyname")),
            "giv": first(pick(hdr, "principal", "given"), pick(hdr, "npi", "given"), pick(hdr, "givenname")),
            "name": first(pick(hdr, "principal", "name"), pick(hdr, "npi"), pick(hdr, "investigator")),
            "org": first(pick(hdr, "institution", "name"), pick(hdr, "institution", avoid=("id", "code", "province", "country", "type"))),
            "prov": pick(hdr, "province"),
            "amt": first(pick(hdr, "cihr", "amount"), pick(hdr, "cihr", "contribution"), pick(hdr, "amount", avoid=("partner",))),
            "end": pick(hdr, "end", "date"),
            "prog": first(pick(hdr, "program", "name"), pick(hdr, "program", avoid=("code", "id"))),
            "type": first(pick(hdr, "grantoraward"), pick(hdr, "grant", "award", avoid=("amount", "date"))),
            "kw": pick(hdr, "keyword"),
        }
        print("CIHR column match:", {k: (hdr[v] if v is not None else None) for k, v in c.items()})
        if c["title"] is None or c["end"] is None or (c["name"] is None and c["fam"] is None):
            print("CIHR: required columns not found, skipping file")
            continue
        val = lambda row, k: row[c[k]] if c[k] is not None and c[k] < len(row) else None
        for row in it:
            end = to_date(val(row, "end"))
            if not end or end < dt.date.today():
                continue
            typ = str(val(row, "type") or "")
            if typ and not re.search(r"grant|subvention", typ, re.I):
                continue
            title = str(val(row, "title") or "").strip()
            if not title:
                continue
            if c["fam"] is not None:
                name = f"{val(row, 'giv') or ''} {val(row, 'fam') or ''}".strip()
            else:
                name = person(str(val(row, "name") or ""))
            try:
                amt = int(float(val(row, "amt") or 0))
            except (TypeError, ValueError):
                amt = 0
            key = str(val(row, "id") or f"{name}|{title}")
            prev = rows.get(key)
            rows[key] = {"pi": person(name), "org": str(val(row, "org") or "").strip(), "st": str(val(row, "prov") or "").strip(),
                         "amt": max(amt, prev["amt"]) if prev else amt, "end": end.isoformat()[:7], "title": title,
                         "prog": str(val(row, "prog") or "").strip(), "kw": str(val(row, "kw") or "")[:160], "id": key}
        wb.close()
    out = sorted(rows.values(), key=lambda x: -x["amt"])
    for x in out:
        p = x["prog"]
        x["kind"] = "train" if re.search(r"training|STIHR|fellowship", p, re.I) else "ctr" if re.search(r"team|network|SPOR|centre|center|platform|consorti", p, re.I) else "lab"
    return out[:8000]


# ------------------------------------------------------------------------------------------------ main
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    idx = load(OUT / "ca-index.json", {})
    force = "--force" in sys.argv
    try:
        age = (dt.date.today() - dt.date.fromisoformat(idx.get("updated", "2000-01-01"))).days
    except ValueError:
        age = 99
    pending = idx.get("pending") or []
    if age < REFRESH_DAYS and not pending and not force:
        print("Canada grants are less than a week old, skipping")
        return
    starting_fresh = age >= REFRESH_DAYS or force
    if starting_fresh:
        pending = list(TOPICS)
        idx["updated"] = dt.date.today().isoformat()

    # CIHR once per refresh
    if starting_fresh or not (OUT / "ca-cihr.json").exists():
        try:
            rows = cihr()
            if rows:
                save(OUT / "ca-cihr.json", {"updated": dt.date.today().isoformat(), "rows": rows})
                idx["cihr"] = len(rows)
                print(f"CIHR: {len(rows)} active grants")
        except Exception as e:  # noqa: BLE001
            print("CIHR failed:", e)

    cache = load(OUT / "ca-nserc-cache.json", {})
    topics = {t[0]: t for t in idx.get("topics", [])}
    try:
        fy = latest_fy()
        idx["nserc_fy"] = fy
        print("NSERC fiscal year", fy)
        while pending and left() > 30:
            t = pending[0]
            try:
                r = nserc_topic(fy, t, cache)
            except Exception as e:  # noqa: BLE001
                print("NSERC failed for", t, e)
                pending.pop(0)
                continue
            if r is None:
                break
            save(OUT / f"ca-nserc-{slug(t)}.json", r)
            topics[t] = [t, slug(t), r["total"], len(r["rows"])]
            print(f"NSERC {t}: {r['total']} awards, kept {len(r['rows'])} active research grants")
            pending.pop(0)
    except Exception as e:  # noqa: BLE001
        print("NSERC failed:", e)
    save(OUT / "ca-nserc-cache.json", cache)

    # featured list for the page before anyone searches: largest active grants across topics + CIHR
    feat, seen = [], set()
    for t in TOPICS:
        d = load(OUT / f"ca-nserc-{slug(t)}.json", {})
        for x in d.get("rows", []):
            if x["pi"] not in seen:
                seen.add(x["pi"])
                feat.append(dict(x, src="NSERC"))
    feat.sort(key=lambda x: -x["amt"])
    ci = load(OUT / "ca-cihr.json", {}).get("rows", [])
    mix = feat[:30] + [dict(x, src="CIHR") for x in ci[:30]]
    idx["featured"] = sorted(mix, key=lambda x: -x["amt"])
    idx["topics"] = [topics[t] for t in TOPICS if t in topics]
    idx["pending"] = pending
    save(OUT / "ca-index.json", idx)
    print(f"Canada grants: {len(idx['topics'])} topics ready, {len(pending)} pending, {round(time.time() - T0)}s")


if __name__ == "__main__":
    main()
