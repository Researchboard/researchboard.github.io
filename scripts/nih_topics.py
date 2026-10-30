#!/usr/bin/env python3
"""
Active NIH grants for popular research topics, for the Study Abroad › US active grants tab.
NIH RePORTER does not allow searches from a web browser, so this runs in the workflow once a week.

  data/grants/nih-index.json        topics with counts and refresh date
  data/grants/nih-<slug>.json       up to 80 active grants per topic, largest first
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "grants"
API = "https://api.reporter.nih.gov/v2/projects/search"
REFRESH_DAYS = 6

TOPICS = ["cancer", "diabetes", "Alzheimer's disease", "HIV", "malaria", "tuberculosis", "antimicrobial resistance", "vaccines",
          "mental health", "depression", "obesity", "cardiovascular disease", "stroke", "kidney disease", "arsenic",
          "air pollution", "climate change", "nutrition", "maternal health", "child development", "genomics", "CRISPR",
          "microbiome", "immunology", "neuroscience", "machine learning", "artificial intelligence", "bioinformatics",
          "epidemiology", "public health", "global health", "infectious disease", "drug discovery", "nanoparticles",
          "stem cells", "aging", "sleep", "addiction", "COVID-19", "dengue"]

# research and training grants that can pay graduate students (not contracts or NIH's own labs)
CODES = ["R01", "R03", "R15", "R21", "R33", "R35", "R37", "R56", "R61", "R00", "K99", "K01", "K08", "K23", "K25",
         "P01", "P20", "P30", "P42", "P50", "U01", "U19", "U54", "UG3", "UH3", "UM1", "T32", "D43"]


def kind(code: str) -> str:
    if code.startswith("T") or code == "D43":
        return "training"        # training programmes fund PhD students directly
    if code[0] in "PU":
        return "center"
    return "lab"


def slug(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def post(body: dict) -> dict:
    req = urllib.request.Request(API, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                raise
            print("retry", e)
            time.sleep(5)
    return {}


def fresh() -> bool:
    try:
        meta = json.loads((OUT / "nih-index.json").read_text(encoding="utf-8"))
        return (dt.date.today() - dt.date.fromisoformat(meta["updated"])).days < REFRESH_DAYS
    except Exception:  # noqa: BLE001
        return False


def main() -> None:
    if fresh() and "--force" not in sys.argv:
        print("NIH topics are less than a week old, skipping")
        return
    today = dt.date.today()
    fy = today.year + (1 if today.month >= 10 else 0)        # US federal fiscal year starts 1 October
    OUT.mkdir(parents=True, exist_ok=True)
    index = {"updated": today.isoformat(), "fiscal_year": fy, "topics": []}
    for t in TOPICS:
        body = {"criteria": {"fiscal_years": [fy, fy - 1], "include_active_projects": True, "activity_codes": CODES,
                             "project_end_date": {"from_date": today.isoformat(), "to_date": "2040-12-31"},
                             "advanced_text_search": {"operator": "and", "search_field": "projecttitle,terms", "search_text": t}},
                "include_fields": ["ApplId", "ProjectNum", "ProjectTitle", "PrincipalInvestigators", "Organization",
                                   "AwardAmount", "ProjectEndDate", "ActivityCode", "FiscalYear"],
                "offset": 0, "limit": 200, "sort_field": "award_amount", "sort_order": "desc"}
        try:
            r = post(body)
        except Exception as e:  # noqa: BLE001
            print("NIH failed for", t, e)
            continue
        seen, rows = set(), []
        for p in r.get("results", []):
            pis = p.get("principal_investigators") or []
            if not pis:
                continue
            pi = next((x for x in pis if x.get("is_contact_pi")), pis[0])
            key = (pi.get("full_name") or "").lower()
            if key in seen:
                continue
            seen.add(key)
            org = p.get("organization") or {}
            name = " ".join(w.capitalize() if w.isupper() else w for w in (pi.get("full_name") or "").split())
            rows.append({"pi": name, "org": (org.get("org_name") or "").title(), "st": org.get("org_state") or "",
                         "amt": p.get("award_amount") or 0, "end": (p.get("project_end_date") or "")[:10],
                         "code": p.get("activity_code") or "", "kind": kind(p.get("activity_code") or "R"),
                         "title": p.get("project_title") or "", "appl": p.get("appl_id")})
            if len(rows) >= 80:
                break
        total = (r.get("meta") or {}).get("total", 0)
        (OUT / f"nih-{slug(t)}.json").write_text(json.dumps({"topic": t, "total": total, "rows": rows}, ensure_ascii=False,
                                                            separators=(",", ":")), encoding="utf-8")
        index["topics"].append([t, slug(t), total])
        print(f"NIH {t}: {total} active, kept {len(rows)}")
        time.sleep(1.2)       # NIH asks for no more than one request per second
    if index["topics"]:
        (OUT / "nih-index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
