#!/usr/bin/env python3
"""
ResearchBoard - daily data collector.

Pulls daily publishing numbers from two free sources and saves them as JSON
files that the website (index.html) turns into charts:

  * PubMed (NCBI E-utilities): records ADDED to PubMed each day, overall and
    per country (by author affiliation).
  * OpenAlex: scholarly papers published each day (articles, reviews,
    preprints, letters, conference papers, book chapters - datasets and other
    non-paper records are left out), countries, universities, journals,
    research fields, citations made, and leaderboards of most-cited papers
    and scientists, plus who/what gained the most citations since yesterday.

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
AUTHOR_SNAPSHOT = DATA / "authors_snapshot.json"
WORK_SNAPSHOT = DATA / "works_snapshot.json"
TOTALS_SNAPSHOT = DATA / "totals_snapshot.json"
INST_FILE = DATA / "institutions.json"   # top 200 institutions per day, for search
INST_KEEP_DAYS = 120

SCHEMA = 2  # bump when the meaning of stored numbers changes; triggers a rebuild

OPENALEX = "https://api.openalex.org"
ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

OA_KEY = os.environ.get("OPENALEX_API_KEY", "").strip()
NCBI_KEY = os.environ.get("NCBI_API_KEY", "").strip()
CONTACT = os.environ.get("CONTACT_EMAIL", "").strip()
EXTRA_COUNTRIES = [c.strip().upper() for c in os.environ.get("EXTRA_COUNTRIES", "").split(",") if c.strip()]
REFRESH_DAYS = int(os.environ.get("REFRESH_DAYS", "7"))
BACKFILL_DAYS = int(os.environ.get("BACKFILL_DAYS", "30"))

# What counts as a "paper". OpenAlex also lists datasets, software, errata,
# peer reviews etc.; on some days ~100,000 dataset records from a single
# repository would otherwise swamp the numbers.
PAPER_TYPES = "type:article|review|preprint|letter|conference-paper|book-chapter"

# Works with known broken citation counts in OpenAlex (shown as all-time #1 otherwise).
EXCLUDE_WORKS = {"W3038568908"}

TOP_COUNTRIES_DETAIL = 25
INSTITUTIONS_PER_DAY = 25
JOURNALS_PER_DAY = 15
AUTHOR_SNAPSHOT_SIZE = 200
WORK_SNAPSHOT_SIZE = 200
MAX_CITATION_PAGES = 40
MAX_INSTITUTION_PAGES = 80

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

USER_AGENT = "ResearchBoard/2.0 (daily stats dashboard" + (f"; mailto:{CONTACT}" if CONTACT else "") + ")"

calls = {"openalex": 0, "pubmed": 0}
INST_DAYS: dict = {}    # day -> {institution id: papers} (top 200), filled while collecting
INST_NAMES: dict = {}
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
    url = f"{OPENALEX}/{path}?{urllib.parse.urlencode(params, safe=':,|*!')}"
    calls["openalex"] += 1
    data = http_json(url)
    time.sleep(0.1)
    return data


def pubmed_count(term: str) -> int:
    params = {"db": "pubmed", "term": term, "retmax": 0, "retmode": "json"}
    if NCBI_KEY:
        params["api_key"] = NCBI_KEY
    calls["pubmed"] += 1
    data = http_json(f"{ESEARCH}?{urllib.parse.urlencode(params)}")
    time.sleep(0.12 if NCBI_KEY else 0.4)
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


def day_filter(day: dt.date, extra: str = "") -> str:
    f = f"publication_date:{iso(day)},{PAPER_TYPES}"
    return f + ("," + extra if extra else "")


# --------------------------------------------------------------------------- daily metrics

def pubmed_added(day: dt.date, extra: str | None = None) -> int:
    term = f'"{day:%Y/%m/%d}"[edat]'
    if extra:
        term = f"({term}) AND {extra}"
    return pubmed_count(term)


def pubmed_country_term(code: str, name: str) -> str:
    return PUBMED_COUNTRY_TERMS.get(code, f'("{name}"[ad])')


def papers_published(day: dt.date) -> int:
    return int(openalex("works", filter=day_filter(day), per_page=1, select="id")["meta"]["count"])


def group(filter_: str, field: str) -> list[dict]:
    """First page of a group_by: up to 200 groups, largest first."""
    return openalex("works", filter=filter_, group_by=field).get("group_by", [])


def countries(day: dt.date) -> tuple[dict, dict]:
    """{code: papers} for every country that published, and {code: name}."""
    counts, names = {}, {}
    for g in group(day_filter(day), "authorships.countries"):
        code = short_id(g.get("key")).upper()
        if len(code) == 2:
            counts[code] = g["count"]
            names[code] = g.get("key_display_name") or code
    return dict(sorted(counts.items(), key=lambda kv: -kv[1])), names


def ranked(groups: list[dict], n: int) -> list[dict]:
    out = [{"id": short_id(g.get("key")), "name": g.get("key_display_name") or "Unknown", "count": g["count"]}
           for g in groups if g.get("key")]
    out.sort(key=lambda x: -x["count"])
    return out[:n]


def top_institutions(day: dt.date, country: str | None = None, n: int = INSTITUTIONS_PER_DAY) -> list[dict]:
    extra = f"authorships.institutions.country_code:{country}" if country else ""
    return ranked(group(day_filter(day, extra), "authorships.institutions.lineage"), n)


def top_journals(day: dt.date) -> list[dict]:
    return ranked(group(day_filter(day, "primary_location.source.type:journal"), "primary_location.source.id"),
                  JOURNALS_PER_DAY)


def fields(day: dt.date) -> list[dict]:
    return ranked(group(day_filter(day), "primary_topic.field.id"), 30)


def paged_groups(filter_: str, field: str, max_pages: int):
    cursor, pages = "*", 0
    while cursor and pages < max_pages:
        data = openalex("works", filter=filter_, group_by=field, cursor=cursor)
        yield data.get("group_by", [])
        cursor = data.get("meta", {}).get("next_cursor")
        pages += 1


def active_institutions(day: dt.date) -> int | None:
    """Number of distinct institutions with at least one paper that day."""
    total, pages = 0, 0
    for groups in paged_groups(day_filter(day), "authorships.institutions.id", MAX_INSTITUTION_PAGES):
        total += sum(1 for g in groups if g.get("key"))
        pages += 1
    return None if pages >= MAX_INSTITUTION_PAGES else total


def citations_made(day: dt.date) -> int:
    """
    New citations created on a day = total references listed in that day's
    papers: sum(reference_count * number_of_papers_with_that_count).
    """
    total = 0
    for groups in paged_groups(day_filter(day), "referenced_works_count", MAX_CITATION_PAGES):
        for g in groups:
            try:
                total += int(float(g["key"])) * int(g["count"])
            except (TypeError, ValueError):
                pass
    return total


FRACTIONAL_COUNTRIES = 30   # fractional counts for the day's top 30 countries (+ EXTRA_COUNTRIES, + Bangladesh)


def fractional(day: dt.date, counts: dict) -> dict:
    """
    Fractional count per country: a paper with authors from k countries adds 1/k
    to each of them (instead of 1 to each), so international papers are not
    counted several times. Uses one group_by per country on countries_distinct_count.
    """
    codes = list(counts)[:FRACTIONAL_COUNTRIES] + [c for c in EXTRA_COUNTRIES + ["BD"] if c in counts]
    out = {}
    for code in dict.fromkeys(codes):
        total = 0.0
        for g in group(day_filter(day, f"authorships.countries:{code}"), "countries_distinct_count"):
            try:
                k = int(float(g["key"]))
                total += g["count"] / k if k > 0 else g["count"]
            except (TypeError, ValueError):
                pass
        out[code] = round(total, 1)
    return out


def collect_day(day: dt.date, include_pubmed: bool, names: dict, deep: bool) -> dict:
    rec: dict = {}
    if include_pubmed:
        rec["pubmed_added"] = safe(f"pubmed {day}", lambda: pubmed_added(day))
    rec["papers"] = safe(f"papers {day}", lambda: papers_published(day))
    rec["citations_made"] = safe(f"citations {day}", lambda: citations_made(day))
    got = safe(f"countries {day}", lambda: countries(day))
    if got:
        rec["countries"], n = got
        names.update(n)
        rec["countries_active"] = len(rec["countries"])
    if rec.get("countries"):
        rec["countries_frac"] = safe(f"fractional {day}", lambda: fractional(day, rec["countries"]), {}) or {}
    groups = safe(f"institutions {day}", lambda: group(day_filter(day), "authorships.institutions.lineage"), []) or []
    rec["institutions"] = ranked(groups, INSTITUTIONS_PER_DAY)
    full = ranked(groups, 200)
    if full:
        INST_DAYS[iso(day)] = {x["id"]: x["count"] for x in full}
        INST_NAMES.update({x["id"]: x["name"] for x in full})
    rec["journals"] = safe(f"journals {day}", lambda: top_journals(day), [])
    rec["fields"] = safe(f"fields {day}", lambda: fields(day), [])
    if deep:
        rec["institutions_active"] = safe(f"active institutions {day}", lambda: active_institutions(day))
    rec["checked_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    return {k: v for k, v in rec.items() if v is not None}


def is_complete(days: dict, d: dt.date, newest: dt.date) -> bool:
    """
    A day counts as complete when it has at least 40% of the papers that the
    same weekday usually has (so quieter weekends can qualify too).
    Reference days are at least a week old, i.e. mostly indexed already.
    """
    v = days.get(iso(d), {}).get("papers")
    if not isinstance(v, int):
        return False
    same = [days.get(iso(d - dt.timedelta(days=7 * k)), {}).get("papers") for k in range(1, 6)]
    ref = sorted(x for x in same if isinstance(x, int))
    if len(ref) < 2:  # not enough history for this weekday: use all mature days
        ref = sorted(r.get("papers") for k, r in days.items()
                     if isinstance(r.get("papers"), int) and k <= iso(newest - dt.timedelta(days=7)))
    if not ref:
        return True
    return v >= 0.4 * ref[len(ref) // 2]


def pick_complete_day(days: dict, newest: dt.date, previous: dict, today: dt.date) -> dt.date:
    """
    The day the rankings, the daily report and the social posts are about.
    Moves forward ONE day per daily run, so every day (weekends too) gets its
    own report in order. Falls back to the newest complete day when starting
    fresh or when it has fallen far behind.
    """
    prev = previous.get("latest_day")
    prev_d = dt.date.fromisoformat(prev) if prev else None
    if prev_d and previous.get("advanced_on") == iso(today):
        return prev_d                      # already advanced today (manual re-run)
    if prev_d and dt.timedelta(days=1) <= newest - prev_d <= dt.timedelta(days=10):
        nxt = prev_d + dt.timedelta(days=1)
        return nxt if is_complete(days, nxt, newest) else prev_d
    for i in range(0, 7):
        d = newest - dt.timedelta(days=i)
        if is_complete(days, d, newest):
            return d
    return newest



# --------------------------------------------------------------------------- 24-hour "market" change

def totals_now(today: dt.date) -> dict:
    """
    Running totals of recent papers (published this year or last year): overall,
    per country and per institution. The difference between two daily runs is
    what was added to the scientific record in those ~24 hours.
    """
    flt = f"publication_year:>{today.year - 2},{PAPER_TYPES}"
    by_country = openalex("works", filter=flt, group_by="authorships.countries")
    countries_ = {}
    for g in by_country.get("group_by", []):
        code = short_id(g.get("key")).upper()
        if len(code) == 2:
            countries_[code] = g["count"]
    insts = {}
    for g in group(flt, "authorships.institutions.lineage"):
        if g.get("key"):
            insts[short_id(g["key"])] = [g.get("key_display_name") or "Unknown", g["count"]]
    total = int(by_country.get("meta", {}).get("count") or openalex("works", filter=flt, per_page=1, select="id")["meta"]["count"])
    return {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "filter": flt,
            "total": total, "countries": countries_, "institutions": insts}


def market_change(now: dict, prev: dict, pubmed_yesterday: int | None, history_deltas: list[int]) -> dict | None:
    """Compare two snapshots ~24 h apart. Returns None if they can't be compared."""
    if not prev or prev.get("filter") != now["filter"]:
        return None
    t0 = dt.datetime.fromisoformat(prev["at"])
    t1 = dt.datetime.fromisoformat(now["at"])
    hours = (t1 - t0).total_seconds() / 3600
    if not 12 <= hours <= 36:
        return None
    added = now["total"] - prev["total"]
    flagged = ""
    usual = sorted(history_deltas)[len(history_deltas) // 2] if len(history_deltas) >= 3 else None
    if added <= 0:
        flagged = "no growth (database update pending)"
    elif usual and (added > 4 * usual or added < usual / 4):
        flagged = f"unusual jump ({added:,} vs usual {usual:,}) - likely a database clean-up or bulk import"
    c_delta = {c: n - prev["countries"].get(c, 0) for c, n in now["countries"].items() if c in prev["countries"]}
    c_top = sorted(((c, d) for c, d in c_delta.items() if d > 0), key=lambda x: -x[1])[:10]
    i_top = []
    for iid, (name, n) in now["institutions"].items():
        if iid in prev["institutions"]:
            d = n - prev["institutions"][iid][1]
            if d > 0:
                i_top.append({"id": iid, "name": name, "added": d})
    i_top.sort(key=lambda x: -x["added"])
    return {"from": prev["at"], "to": now["at"], "hours": round(hours, 1), "papers_added": added,
            "pubmed_yesterday": pubmed_yesterday, "countries": [{"code": c, "added": d} for c, d in c_top],
            "countries_active": sum(1 for d in c_delta.values() if d > 0),
            "institutions": i_top[:10], "flagged": flagged}

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


def works_list(filter_: str, n: int) -> list[dict]:
    rows, page = [], 1
    while len(rows) < n:
        data = openalex("works", filter=filter_, sort="cited_by_count:desc",
                        per_page=min(100, n + len(EXCLUDE_WORKS)), page=page, select=PAPER_FIELDS)
        results = data.get("results", [])
        if not results:
            break
        rows += [paper_row(w) for w in results if short_id(w.get("id")) not in EXCLUDE_WORKS]
        page += 1
    return rows[:n]


def top_papers_all_time() -> list[dict]:
    return works_list("type:article|review,primary_location.source.type:journal", 10)


def recent_papers(today: dt.date, n: int) -> list[dict]:
    start = today - dt.timedelta(days=730)
    return works_list(f"from_publication_date:{iso(start)},to_publication_date:{iso(today)},"
                      "type:article|review,primary_location.source.type:journal", n)


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


def institution_countries(ids: list[str], known: dict) -> dict:
    """Look up the country of each institution id not seen before."""
    todo = [i for i in dict.fromkeys(ids) if i and i not in known]
    for k in range(0, len(todo), 50):
        chunk = todo[k:k + 50]
        data = openalex("institutions", filter="openalex:" + "|".join(chunk), per_page=50,
                        select="id,country_code")
        for r in data.get("results", []):
            known[short_id(r.get("id"))] = (r.get("country_code") or "").upper() or None
        for i in chunk:
            known.setdefault(i, None)
    return known


def gains(rows: list[dict], path: Path, today: dt.date) -> tuple[list[dict], str | None, int | None]:
    """
    Compare today's citation totals with the previous daily snapshot.
    Re-runs on the same day compare with the day before, so a manual re-run
    never wipes out the day's gains.
    """
    snap = load_json(path, {})
    snap_date = snap.get("date")
    if snap_date != iso(today):
        base_date, base = snap_date, snap.get("counts", {})
        save_json(path, {"date": iso(today), "counts": {r["id"]: r["citations"] for r in rows},
                         "previous": {"date": snap_date, "counts": base} if snap_date else None})
    else:
        prev = snap.get("previous") or {}
        base_date, base = prev.get("date"), prev.get("counts", {})
        # keep today's counts current
        snap["counts"] = {r["id"]: r["citations"] for r in rows}
        save_json(path, snap)
    if not base_date:
        return [], None, None
    out = []
    for r in rows:
        before = base.get(r["id"])
        if before is not None and r["citations"] > before:
            out.append({**r, "gain": r["citations"] - before})
    out.sort(key=lambda x: -x["gain"])
    gap = (today - dt.date.fromisoformat(base_date)).days or None
    return out[:10], base_date, gap


# --------------------------------------------------------------------------- main

def main() -> int:
    today = dt.datetime.now(dt.timezone.utc).date()
    newest = today - dt.timedelta(days=1)  # last complete UTC day
    print(f"Collecting up to {newest} (OpenAlex key: {'yes' if OA_KEY else 'no'}, NCBI key: {'yes' if NCBI_KEY else 'no'})",
          flush=True)

    history = load_json(HISTORY_FILE, {"days": {}})
    previous_latest = load_json(LATEST_FILE, {})
    if history.get("schema") != SCHEMA:
        print("Data format changed - rebuilding history", flush=True)
        old_pubmed = {d: r.get("pubmed_added") for d, r in history.get("days", {}).items()}
        history = {"schema": SCHEMA, "days": {}}
        for d, v in old_pubmed.items():  # PubMed numbers did not change meaning; keep them
            if v is not None:
                history["days"][d] = {"pubmed_added": v}
    days: dict = history["days"]
    names: dict = dict(previous_latest.get("country_names", {}))

    # 1) Backfill so the graphs have a line from day one.
    for i in range(BACKFILL_DAYS, REFRESH_DAYS, -1):
        d = newest - dt.timedelta(days=i - 1)
        if "papers" not in days.get(iso(d), {}):
            print("backfill", d, flush=True)
            days[iso(d)] = {**days.get(iso(d), {}),
                            **collect_day(d, "pubmed_added" not in days.get(iso(d), {}), names, deep=False)}

    # 2) Re-count recent days: databases keep adding papers for a while.
    for i in range(REFRESH_DAYS - 1, -1, -1):
        d = newest - dt.timedelta(days=i)
        old = days.get(iso(d), {})
        print("refresh", d, flush=True)
        days[iso(d)] = {**old, **collect_day(d, i < 3 or "pubmed_added" not in old, names, deep=True)}

    # 3) Rankings use the newest day OpenAlex has mostly finished indexing.
    rank_day = pick_complete_day(days, newest, previous_latest, today)
    print("Rankings day:", rank_day, flush=True)
    rec = days[iso(rank_day)]

    country_counts = rec.get("countries", {})
    detail_codes = list(country_counts)[:TOP_COUNTRIES_DETAIL]
    for code in EXTRA_COUNTRIES:
        if code not in detail_codes:
            detail_codes.append(code)

    countries_detail, pubmed_by_country = {}, {}
    for code in detail_codes:
        name = names.get(code, code)
        pm = safe(f"pubmed {code}", lambda: pubmed_added(rank_day, pubmed_country_term(code, name)))
        if pm is not None:
            pubmed_by_country[code] = pm
        countries_detail[code] = {
            "name": name,
            "papers": country_counts.get(code, 0),
            "pubmed_added": pm,
            "top_institutions": safe(f"institutions {code}", lambda: top_institutions(rank_day, code, 5), []),
            "top_authors": safe(f"authors {code}", lambda: top_authors_in(code), []),
        }
    rec["pubmed_by_country"] = pubmed_by_country

    # 4) Country of each institution shown on the board.
    inst_country = dict(previous_latest.get("inst_country", {}))
    inst_ids = [x["id"] for d in days.values() for x in d.get("institutions", [])[:10]]
    inst_ids += [x["id"] for c in countries_detail.values() for x in c.get("top_institutions", [])]
    inst_country = safe("institution countries", lambda: institution_countries(inst_ids, inst_country), inst_country)

    # 5) Leaderboards and "gained the most citations since yesterday".
    authors = safe("top authors", lambda: top_authors(AUTHOR_SNAPSHOT_SIZE), []) or []
    author_gains, a_base, a_gap = gains(authors, AUTHOR_SNAPSHOT, today) if authors else ([], None, None)
    recent = safe("recent papers", lambda: recent_papers(today, WORK_SNAPSHOT_SIZE), []) or []
    paper_gains, p_base, p_gap = gains(recent, WORK_SNAPSHOT, today) if recent else ([], None, None)
    if author_gains:
        rec["top_gainers"] = [{"id": g["id"], "name": g["name"], "gain": g["gain"]} for g in author_gains[:5]]

    # 6) 24-hour change of the running totals ("market" post).
    prev_totals = load_json(TOTALS_SNAPSHOT, {})
    now_totals = safe("24h totals", lambda: totals_now(today))
    market = None
    deltas = [m["papers_added"] for m in history.get("market", []) if not m.get("flagged")][-14:]
    if now_totals:
        market = market_change(now_totals, prev_totals, days.get(iso(newest), {}).get("pubmed_added"), deltas)
        if market:
            history["market"] = (history.get("market", []) + [market])[-120:]
        # Keep the old snapshot if this run came too soon after it (e.g. a manual re-run).
        if not prev_totals or market or (dt.datetime.fromisoformat(now_totals["at"]) -
                                         dt.datetime.fromisoformat(prev_totals["at"])).total_seconds() > 36 * 3600:
            save_json(TOTALS_SNAPSHOT, now_totals)

    # 7) Top-200 institutions per day (used by the site search).
    def save_institutions():
        inst = load_json(INST_FILE, {"days": {}, "names": {}, "country": {}})
        inst["days"].update(INST_DAYS)
        keep = sorted(inst["days"])[-INST_KEEP_DAYS:]
        inst["days"] = {k: inst["days"][k] for k in keep}
        inst["names"].update(INST_NAMES)
        live = {i for d in inst["days"].values() for i in d}
        inst["names"] = {i: n for i, n in inst["names"].items() if i in live}
        cc = dict(inst.get("country", {}))
        cc.update({k: v for k, v in inst_country.items() if k in live and v})
        cc = institution_countries([i for i in live if i not in cc], cc)
        inst["country"] = {i: c for i, c in cc.items() if i in live and c}
        save_json(INST_FILE, inst)
    if INST_DAYS:
        safe("institutions file", save_institutions)

    latest = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "latest_day": iso(rank_day),
        "advanced_on": iso(today) if iso(rank_day) != previous_latest.get("latest_day") else previous_latest.get("advanced_on"),
        "newest_day": iso(newest),
        "paper_types": PAPER_TYPES.split(":", 1)[1].split("|"),
        "country_names": names,
        "inst_country": inst_country,
        "top_papers": safe("top papers", top_papers_all_time) or previous_latest.get("top_papers", []),
        "hot_papers": recent[:10] or previous_latest.get("hot_papers", []),
        "top_authors": authors[:20] or previous_latest.get("top_authors", []),
        "gainers": author_gains,
        "gainers_baseline": a_base,
        "gainers_days": a_gap,
        "paper_gainers": paper_gains,
        "paper_gainers_baseline": p_base,
        "paper_gainers_days": p_gap,
        "countries_detail": countries_detail,
        "market": market or previous_latest.get("market"),
        "calls": calls,
        "warnings": warnings[-20:],
    }

    history["schema"] = SCHEMA
    history["updated"] = latest["generated_at"]
    history["days"] = dict(sorted(days.items()))
    save_json(HISTORY_FILE, history)
    save_json(LATEST_FILE, latest)

    print(f"Done. API calls: {calls}. Warnings: {len(warnings)}", flush=True)
    for w in warnings[:10]:
        print("  -", w)
    got_anything = any(k in rec for k in ("pubmed_added", "papers"))
    return 0 if got_anything else 1


def totals_only() -> int:
    """Save just the running totals (the starting point for the next 24-hour comparison)."""
    today = dt.datetime.now(dt.timezone.utc).date()
    now_totals = safe("24h totals", lambda: totals_now(today))
    if not now_totals:
        return 1
    save_json(TOTALS_SNAPSHOT, now_totals)
    print("Saved totals snapshot:", now_totals["at"], f"{now_totals['total']:,} papers", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(totals_only() if "--totals-only" in sys.argv else main())
