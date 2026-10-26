#!/usr/bin/env python3
"""
ResearchBoard - daily data collector.

Pulls daily publishing numbers from two free sources and saves them as JSON
files that the website (index.html) turns into charts:

  * PubMed (NCBI E-utilities): how many records were ADDED to PubMed each day,
    overall and per country (by author affiliation).
  * OpenAlex: papers published each day worldwide, top countries, top
    universities, new citations made that day, most-cited papers and scientists.

Run once a day (GitHub Actions does this automatically - see README.md).
Uses only the Python standard library.

Environment variables (all optional):
  OPENALEX_API_KEY   free key from https://openalex.org/settings/api (recommended)
  NCBI_API_KEY       free key from your NCBI account (raises PubMed rate limit)
  CONTACT_EMAIL      sent in the User-Agent so the APIs can contact you
  EXTRA_COUNTRIES    comma-separated 2-letter codes always tracked, e.g. "BD,NG"
  REFRESH_DAYS       how many recent days to re-count each run (default 7)
  BACKFILL_DAYS      history to build on the first run (default 30)
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
HISTORY_FILE = DATA / "history.json"
LATEST_FILE = DATA / "latest.json"
SNAPSHOT_FILE = DATA / "authors_snapshot.json"

OPENALEX = "https://api.openalex.org"
ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

OA_KEY = os.environ.get("OPENALEX_API_KEY", "").strip()
NCBI_KEY = os.environ.get("NCBI_API_KEY", "").strip()
CONTACT = os.environ.get("CONTACT_EMAIL", "").strip()
EXTRA_COUNTRIES = [c.strip().upper() for c in os.environ.get("EXTRA_COUNTRIES", "").split(",") if c.strip()]
REFRESH_DAYS = int(os.environ.get("REFRESH_DAYS", "7"))
BACKFILL_DAYS = int(os.environ.get("BACKFILL_DAYS", "30"))

TOP_COUNTRIES_DETAIL = 25   # countries that get a detail card (authors, universities, PubMed count)
COUNTRIES_PER_DAY = 60      # countries kept in each day's history
INSTITUTIONS_PER_DAY = 25
AUTHOR_SNAPSHOT_SIZE = 200  # top authors snapshotted daily to measure citation gains
MAX_CITATION_PAGES = 40

# PubMed affiliation search terms for countries whose OpenAlex name differs
# from how affiliations are usually written.
PUBMED_COUNTRY_TERMS = {
    "US": '("United States"[ad] OR USA[ad] OR U.S.A.[ad])',
    "GB": '("United Kingdom"[ad] OR UK[ad] OR England[ad] OR Scotland[ad] OR Wales[ad])',
    "KR": '("Korea"[ad] NOT "Democratic People\'s Republic"[ad])',
    "CN": '(China[ad] NOT Taiwan[ad])',
    "IR": '(Iran[ad])',
    "RU": '(Russia[ad] OR "Russian Federation"[ad])',
    "TW": '(Taiwan[ad])',
    "CZ": '("Czech Republic"[ad] OR Czechia[ad])',
    "TR": '(Turkey[ad] OR Türkiye[ad] OR Turkiye[ad])',
    "NL": '(Netherlands[ad])',
    "VN": '(Vietnam[ad] OR "Viet Nam"[ad])',
}

USER_AGENT = "ResearchBoard/1.0 (daily stats dashboard" + (f"; mailto:{CONTACT}" if CONTACT else "") + ")"

calls = {"openalex": 0, "pubmed": 0}
warnings: list[str] = []


# --------------------------------------------------------------------------- HTTP

def http_json(url: str, retries: int = 5) -> dict:
    delay = 2.0
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            body = e.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"HTTP {e.code} for {redact(url)}: {body}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise RuntimeError(f"Network error for {redact(url)}: {e}") from None
    raise RuntimeError(f"Gave up on {redact(url)}")


def redact(url: str) -> str:
    for secret in (OA_KEY, NCBI_KEY):
        if secret:
            url = url.replace(secret, "***")
    return url


def openalex(path: str, **params) -> dict:
    if OA_KEY:
        params["api_key"] = OA_KEY
    url = f"{OPENALEX}/{path}?{urllib.parse.urlencode(params, safe=':,|*')}"
    calls["openalex"] += 1
    data = http_json(url)
    time.sleep(0.12)
    return data


def pubmed_count(term: str) -> int:
    params = {"db": "pubmed", "term": term, "retmax": 0, "retmode": "json"}
    if NCBI_KEY:
        params["api_key"] = NCBI_KEY
    calls["pubmed"] += 1
    data = http_json(f"{ESEARCH}?{urllib.parse.urlencode(params)}")
    time.sleep(0.12 if NCBI_KEY else 0.4)  # NCBI allows 3 req/s without key, 10 with
    return int(data["esearchresult"]["count"])


# --------------------------------------------------------------------------- helpers

def iso(d: dt.date) -> str:
    return d.isoformat()


def short_id(openalex_url: str | None) -> str:
    return (openalex_url or "").rstrip("/").rsplit("/", 1)[-1]


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def safe(label: str, fn, default=None):
    """Run one collection step; on failure keep going and record a warning."""
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 - one bad call must not lose the whole day
        msg = f"{label}: {e}"
        print("WARN", msg, file=sys.stderr)
        warnings.append(msg)
        return default


# --------------------------------------------------------------------------- daily metrics

def pubmed_added(day: dt.date, extra: str | None = None) -> int:
    term = f'"{day:%Y/%m/%d}"[edat]'
    if extra:
        term = f"({term}) AND {extra}"
    return pubmed_count(term)


def pubmed_country_term(code: str, name: str) -> str:
    return PUBMED_COUNTRY_TERMS.get(code, f'("{name}"[ad])')


def works_published(day: dt.date) -> int:
    data = openalex("works", filter=f"publication_date:{iso(day)}", per_page=1, select="id")
    return int(data["meta"]["count"])


def group(filter_: str, field: str) -> list[dict]:
    """First page of a group_by: up to 200 groups, largest first."""
    data = openalex("works", filter=filter_, group_by=field)
    return data.get("group_by", [])


def top_countries(day: dt.date) -> list[dict]:
    out = []
    for g in group(f"publication_date:{iso(day)}", "authorships.countries"):
        code = short_id(g.get("key")).upper()
        if len(code) == 2:
            out.append({"code": code, "name": g.get("key_display_name") or code, "count": g["count"]})
    out.sort(key=lambda x: -x["count"])
    return out[:COUNTRIES_PER_DAY]


def top_institutions(day: dt.date, country: str | None = None, n: int = INSTITUTIONS_PER_DAY) -> list[dict]:
    f = f"publication_date:{iso(day)}"
    if country:
        f += f",authorships.institutions.country_code:{country}"
    out = [
        {"id": short_id(g.get("key")), "name": g.get("key_display_name") or "Unknown", "count": g["count"]}
        for g in group(f, "authorships.institutions.lineage")
    ]
    out.sort(key=lambda x: -x["count"])
    return out[:n]


def citations_made(day: dt.date) -> int:
    """
    New citations created on a day = total references listed in the papers
    published that day. One grouped query per 200 distinct reference counts:
    sum(reference_count * number_of_papers_with_that_count).
    """
    total, cursor, pages = 0, "*", 0
    while cursor and pages < MAX_CITATION_PAGES:
        data = openalex(
            "works",
            filter=f"publication_date:{iso(day)}",
            group_by="referenced_works_count",
            cursor=cursor,
        )
        for g in data.get("group_by", []):
            try:
                total += int(float(g["key"])) * int(g["count"])
            except (TypeError, ValueError):
                pass
        cursor = data.get("meta", {}).get("next_cursor")
        pages += 1
    return total


def collect_day(day: dt.date, include_pubmed: bool) -> dict:
    rec: dict = {}
    if include_pubmed:
        rec["pubmed_added"] = safe(f"pubmed {day}", lambda: pubmed_added(day))
    rec["openalex_published"] = safe(f"works {day}", lambda: works_published(day))
    rec["citations_made"] = safe(f"citations {day}", lambda: citations_made(day))
    rec["countries"] = safe(f"countries {day}", lambda: top_countries(day), [])
    rec["institutions"] = safe(f"institutions {day}", lambda: top_institutions(day), [])
    rec["checked_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    return {k: v for k, v in rec.items() if v is not None}


# --------------------------------------------------------------------------- leaderboards

PAPER_FIELDS = "id,doi,display_name,cited_by_count,publication_year,publication_date,primary_location"
AUTHOR_FIELDS = "id,display_name,cited_by_count,works_count,last_known_institutions"


def paper_row(w: dict) -> dict:
    loc = w.get("primary_location") or {}
    src = loc.get("source") or {}
    return {
        "id": short_id(w.get("id")),
        "title": w.get("display_name") or "(untitled)",
        "citations": w.get("cited_by_count", 0),
        "year": w.get("publication_year"),
        "date": w.get("publication_date"),
        "venue": src.get("display_name"),
        "doi": w.get("doi"),
    }


def author_row(a: dict) -> dict:
    insts = a.get("last_known_institutions") or []
    inst = insts[0] if insts else {}
    return {
        "id": short_id(a.get("id")),
        "name": a.get("display_name") or "Unknown",
        "citations": a.get("cited_by_count", 0),
        "works": a.get("works_count", 0),
        "institution": inst.get("display_name"),
        "country": (inst.get("country_code") or "").upper() or None,
    }


def top_papers_all_time() -> list[dict]:
    data = openalex("works", sort="cited_by_count:desc", per_page=10, select=PAPER_FIELDS)
    return [paper_row(w) for w in data.get("results", [])]


def hot_papers(today: dt.date) -> list[dict]:
    start = today - dt.timedelta(days=365)
    data = openalex(
        "works",
        filter=f"from_publication_date:{iso(start)},to_publication_date:{iso(today)}",
        sort="cited_by_count:desc",
        per_page=10,
        select=PAPER_FIELDS,
    )
    return [paper_row(w) for w in data.get("results", [])]


def top_authors(n: int) -> list[dict]:
    rows, page = [], 1
    while len(rows) < n:
        data = openalex("authors", sort="cited_by_count:desc", per_page=100, page=page, select=AUTHOR_FIELDS)
        results = data.get("results", [])
        if not results:
            break
        rows += [author_row(a) for a in results]
        page += 1
    return rows[:n]


AUTHOR_COUNTRY_FILTERS = ["last_known_institutions.country_code", "last_known_institution.country_code"]


def top_authors_in(country: str, n: int = 5) -> list[dict]:
    last_err = None
    for f in AUTHOR_COUNTRY_FILTERS:
        try:
            data = openalex("authors", filter=f"{f}:{country}", sort="cited_by_count:desc",
                            per_page=n, select=AUTHOR_FIELDS)
            return [author_row(a) for a in data.get("results", [])]
        except RuntimeError as e:
            last_err = e
            if "HTTP 400" not in str(e) and "HTTP 403" not in str(e):
                raise
    raise last_err  # type: ignore[misc]


def citation_gainers(authors: list[dict], today: dt.date) -> tuple[list[dict], str | None, float | None]:
    """Compare today's citation totals with the previous snapshot."""
    prev = load_json(SNAPSHOT_FILE, {})
    prev_counts: dict = prev.get("counts", {})
    prev_date = prev.get("date")
    gains = []
    for a in authors:
        before = prev_counts.get(a["id"])
        if before is not None and a["citations"] >= before:
            gains.append({**a, "gain": a["citations"] - before})
    gains.sort(key=lambda x: -x["gain"])
    days_between = None
    if prev_date:
        days_between = (today - dt.date.fromisoformat(prev_date)).days or None
    # Only advance the baseline when the date changes, so re-runs on the same day
    # do not wipe out the gain.
    if prev_date != iso(today):
        save_json(SNAPSHOT_FILE, {"date": iso(today), "counts": {a["id"]: a["citations"] for a in authors},
                                  "previous": {"date": prev_date, "counts": prev_counts} if prev_date else None})
        if prev_date is None:
            return [], None, None
        return [g for g in gains if g["gain"] > 0][:10], prev_date, days_between
    # Same-day re-run: compare against the stored previous baseline instead.
    older = prev.get("previous") or {}
    if not older.get("date"):
        return [], None, None
    gains = []
    for a in authors:
        before = older["counts"].get(a["id"])
        if before is not None and a["citations"] >= before:
            gains.append({**a, "gain": a["citations"] - before})
    gains.sort(key=lambda x: -x["gain"])
    days_between = (today - dt.date.fromisoformat(older["date"])).days or None
    return [g for g in gains if g["gain"] > 0][:10], older["date"], days_between


# --------------------------------------------------------------------------- main

def pick_complete_day(days: dict, newest: dt.date, look_back: int = 14) -> dt.date:
    """Newest day whose OpenAlex count is at least 40% of the recent median."""
    counts = []
    for i in range(1, look_back + 1):
        v = days.get(iso(newest - dt.timedelta(days=i)), {}).get("openalex_published")
        if isinstance(v, int):
            counts.append(v)
    if not counts:
        return newest
    counts.sort()
    median = counts[len(counts) // 2]
    for i in range(0, 7):
        d = newest - dt.timedelta(days=i)
        v = days.get(iso(d), {}).get("openalex_published")
        if isinstance(v, int) and v >= 0.4 * median:
            return d
    return newest


def main() -> int:
    today = dt.datetime.now(dt.timezone.utc).date()
    latest_day = today - dt.timedelta(days=1)  # last complete UTC day
    print(f"Collecting for {latest_day} (OpenAlex key: {'yes' if OA_KEY else 'no'}, NCBI key: {'yes' if NCBI_KEY else 'no'})")

    history = load_json(HISTORY_FILE, {"days": {}})
    days: dict = history.setdefault("days", {})

    # 1) Backfill on first run(s) so the graphs have a line from day one.
    for i in range(BACKFILL_DAYS, REFRESH_DAYS, -1):
        d = latest_day - dt.timedelta(days=i - 1)
        if iso(d) not in days:
            print("backfill", d)
            days[iso(d)] = collect_day(d, include_pubmed=True)

    # 2) Re-count the most recent days: databases keep adding papers for a while.
    for i in range(REFRESH_DAYS - 1, -1, -1):
        d = latest_day - dt.timedelta(days=i)
        old = days.get(iso(d), {})
        print("refresh", d)
        fresh = collect_day(d, include_pubmed=(i < 3 or "pubmed_added" not in old))
        merged = {**old, **fresh}
        days[iso(d)] = merged

    # 3) Pick the newest day OpenAlex has mostly finished indexing. The last
    #    day or two are often only partly indexed (a few hundred papers instead
    #    of tens of thousands), which would make the rankings misleading.
    latest_day = pick_complete_day(days, latest_day)
    print("Rankings day:", latest_day)

    # Country detail for that day.
    latest_rec = days[iso(latest_day)]
    country_list = list(latest_rec.get("countries", []))
    names = {c["code"]: c["name"] for c in country_list}
    detail_codes = [c["code"] for c in country_list[:TOP_COUNTRIES_DETAIL]]
    for code in EXTRA_COUNTRIES:
        if code not in detail_codes:
            detail_codes.append(code)

    countries_detail = {}
    pubmed_by_country = {}
    for code in detail_codes:
        name = names.get(code, code)
        papers = next((c["count"] for c in country_list if c["code"] == code), 0)
        pm = safe(f"pubmed {code}", lambda: pubmed_added(latest_day, pubmed_country_term(code, name)))
        if pm is not None:
            pubmed_by_country[code] = pm
        countries_detail[code] = {
            "name": name,
            "papers": papers,
            "pubmed_added": pm,
            "top_institutions": safe(f"institutions {code}", lambda: top_institutions(latest_day, code, 5), []),
            "top_authors": safe(f"authors {code}", lambda: top_authors_in(code), []),
        }
    latest_rec["pubmed_by_country"] = pubmed_by_country

    # 4) Leaderboards and daily citation gainers.
    authors = safe("top authors", lambda: top_authors(AUTHOR_SNAPSHOT_SIZE), []) or []
    gainers, baseline, gap = ([], None, None)
    if authors:
        gainers, baseline, gap = citation_gainers(authors, today)
        if gainers:
            latest_rec["top_gainers"] = [{"id": g["id"], "name": g["name"], "gain": g["gain"]} for g in gainers[:5]]

    previous_latest = load_json(LATEST_FILE, {})
    latest = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "latest_day": iso(latest_day),
        "top_papers": safe("top papers", top_papers_all_time) or previous_latest.get("top_papers", []),
        "hot_papers": safe("hot papers", lambda: hot_papers(today)) or previous_latest.get("hot_papers", []),
        "top_authors": authors[:20] or previous_latest.get("top_authors", []),
        "gainers": gainers[:10],
        "gainers_baseline": baseline,
        "gainers_days": gap,
        "countries_detail": countries_detail,
        "calls": calls,
        "warnings": warnings[-20:],
    }

    history["updated"] = latest["generated_at"]
    history["days"] = dict(sorted(days.items()))
    save_json(HISTORY_FILE, history)
    save_json(LATEST_FILE, latest)

    print(f"Done. API calls: {calls}. Warnings: {len(warnings)}")
    # Fail the run only if nothing at all came back (e.g. bad API key), so a
    # broken setup is visible in GitHub Actions instead of silently empty.
    got_anything = any(k in latest_rec for k in ("pubmed_added", "openalex_published"))
    return 0 if got_anything else 1


if __name__ == "__main__":
    sys.exit(main())
