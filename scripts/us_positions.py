#!/usr/bin/env python3
"""
Open postdoc and graduate positions at US universities -> data/positions/us.json

Source: each university's own job site. Many US universities run their job
site on PeopleAdmin, which publishes an official Atom feed of open postings
(/postings/search.atom?query=...). We keep only the title, a short summary,
the date and the link to the official ad, and everyone applies there.

The list below includes universities we have confirmed plus candidates that
may use the same system; a site that doesn't answer with a feed is skipped and
reported, so the list can grow without breaking anything.
"""
import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

OUT = "data/positions/us.json"
UA = "ResearchBoard/1.0 (+https://researchboard.net; researchboardlive@gmail.com)"
QUERIES = ["postdoctoral", "postdoc", "post doc", "graduate assistant", "graduate research assistant", "PhD student"]
MAX_AGE_DAYS = 120

# host, university, city, state  (first five confirmed Nov 2026)
SITES = [
    ("www.ugajobsearch.com", "University of Georgia", "Athens", "GA"),
    ("unc.peopleadmin.com", "UNC-Chapel Hill", "Chapel Hill", "NC"),
    ("jobs.ncsu.edu", "NC State University", "Raleigh", "NC"),
    ("uscjobs.sc.edu", "University of South Carolina", "Columbia", "SC"),
    ("utah.peopleadmin.com", "University of Utah", "Salt Lake City", "UT"),
    # candidates (kept only if they answer with a feed)
    ("ecu.peopleadmin.com", "East Carolina University", "Greenville", "NC"),
    ("jobs.uncc.edu", "UNC Charlotte", "Charlotte", "NC"),
    ("jobs.uncg.edu", "UNC Greensboro", "Greensboro", "NC"),
    ("appstate.peopleadmin.com", "Appalachian State University", "Boone", "NC"),
    ("jobs.auburn.edu", "Auburn University", "Auburn", "AL"),
    ("jobs.ua.edu", "University of Alabama", "Tuscaloosa", "AL"),
    ("uah.peopleadmin.com", "University of Alabama in Huntsville", "Huntsville", "AL"),
    ("jobs.uark.edu", "University of Arkansas", "Fayetteville", "AR"),
    ("workforum.memphis.edu", "University of Memphis", "Memphis", "TN"),
    ("jobs.wm.edu", "William & Mary", "Williamsburg", "VA"),
    ("jobs.odu.edu", "Old Dominion University", "Norfolk", "VA"),
    ("joblink.jmu.edu", "James Madison University", "Harrisonburg", "VA"),
    ("jobs.uri.edu", "University of Rhode Island", "Kingston", "RI"),
    ("www.uvmjobs.com", "University of Vermont", "Burlington", "VT"),
    ("employment.unl.edu", "University of Nebraska–Lincoln", "Lincoln", "NE"),
    ("www.unrjobs.com", "University of Nevada, Reno", "Reno", "NV"),
    ("unm.peopleadmin.com", "University of New Mexico", "Albuquerque", "NM"),
    ("jobs.nmsu.edu", "New Mexico State University", "Las Cruces", "NM"),
    ("uidaho.peopleadmin.com", "University of Idaho", "Moscow", "ID"),
    ("jobs.montana.edu", "Montana State University", "Bozeman", "MT"),
    ("jobs.usu.edu", "Utah State University", "Logan", "UT"),
    ("jobs.txstate.edu", "Texas State University", "San Marcos", "TX"),
    ("jobs.unt.edu", "University of North Texas", "Denton", "TX"),
    ("jobs.fau.edu", "Florida Atlantic University", "Boca Raton", "FL"),
    ("jobs.wvu.edu", "West Virginia University", "Morgantown", "WV"),
    ("jobs.uky.edu", "University of Kentucky", "Lexington", "KY"),
    ("ukjobs.uky.edu", "University of Kentucky", "Lexington", "KY"),
    ("jobs.louisiana.edu", "University of Louisiana at Lafayette", "Lafayette", "LA"),
    ("jobs.olemiss.edu", "University of Mississippi", "Oxford", "MS"),
    ("jobs.msstate.edu", "Mississippi State University", "Starkville", "MS"),
    ("jobs.gsu.edu", "Georgia State University", "Atlanta", "GA"),
    ("jobs.kennesaw.edu", "Kennesaw State University", "Kennesaw", "GA"),
    ("jobs.uwyo.edu", "University of Wyoming", "Laramie", "WY"),
    ("jobs.ndsu.edu", "North Dakota State University", "Fargo", "ND"),
    ("jobs.sdstate.edu", "South Dakota State University", "Brookings", "SD"),
]

POSTDOC = re.compile(r"post[\s-]?doc|postdoctoral", re.I)
GRAD = re.compile(r"graduate (research |teaching )?assistant|graduate assistantship|ph\.?\s?d\.? (student|candidate|position|studentship)|doctoral (student|fellow)", re.I)
FIELDS = [
    ("Biology & medicine", r"biolog|biochem|molecular|cell|genom|neuro|immun|cancer|medic|health|clinic|patholog|pharma|microb|virus|infect|stem cell|regenerat|tissue|physiolog|bioinformatic|epigen|protein|disease|nutrition|vet"),
    ("Chemistry & materials", r"chemi|material|polymer|catalys|battery|electrochem|nano"),
    ("Physics & astronomy", r"physic|astro|quantum|optic|photon|planet|cosmo"),
    ("Engineering & computing", r"engineer|comput|machine learning|artificial intelligence|\bai\b|data science|robot|electrical|mechanic|software|cyber"),
    ("Earth, environment & agriculture", r"ecolog|environment|climate|soil|plant|crop|agricult|forest|marine|ocean|water|geolog|entomolog|wildlife|fish"),
    ("Mathematics & statistics", r"mathemat|statistic|biostatist|algebra|geometr|topolog|probabilit"),
    ("Education & social sciences", r"educat|psycholog|social|econom|policy|politic|public health|linguist|histor|philosoph"),
]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/atom+xml, application/xml;q=0.9, */*;q=0.1"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def text(s):
    s = re.sub(r"<(br|/p|/li|/div)[^>]*>", " ", s or "", flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"\s+", " ", s).strip()


def summary(s, n=260):
    s = re.sub(r"^(Posting Number|Job Title|Position Title|Department|Working Title)[^.]{0,120}?(?=[A-Z][a-z]+ )", "", s)
    if len(s) <= n:
        return s
    cut = s[:n]
    i = max(cut.rfind(". "), cut.rfind("? "))
    return (cut[: i + 1] if i > 120 else cut.rsplit(" ", 1)[0] + "…").strip()


def supervisor(t):
    for pat in (r"\b(?:Dr\.|Professor|Prof\.)\s+([A-Z][a-zA-Z'\-]+(?:\s+[A-Z]\.)?\s+[A-Z][a-zA-Z'\-]+)",
                r"\bthe\s+([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)?)\s+[Ll]ab(?:oratory)?\b",
                r"\b([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)?)\s+[Ll]ab\b"):
        m = re.search(pat, t)
        if m and not re.search(r"^(The|Our|This|Research|Honey|Bee|UGA|UNC|AI|Computer|Mixed|Vision)\b", m.group(1)):
            return m.group(1)
    return ""


def field(t):
    # the department named in the ad decides first, then whichever field's words appear most
    m = re.search(r"(?:Department|Dept\.?|School|Division|College) of ([A-Z][A-Za-z&,' ]{3,60})", t)
    if m:
        for name, pat in FIELDS:
            if re.search(pat, m.group(1), re.I):
                return name
    best, score = "Other", 0
    for name, pat in FIELDS:
        n = len(re.findall(pat, t, re.I))
        if n > score:
            best, score = name, n
    return best


def parse(raw):
    root = ET.fromstring(raw)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for e in root.findall("a:entry", ns):
        link = e.find("a:link", ns)
        out.append({
            "title": (e.findtext("a:title", "", ns) or "").strip(),
            "link": link.get("href") if link is not None else "",
            "date": (e.findtext("a:published", "", ns) or e.findtext("a:updated", "", ns) or "")[:10],
            "body": text(e.findtext("a:content", "", ns) or e.findtext("a:summary", "", ns)),
        })
    return out


def main():
    today = dt.date.today()
    rows, seen, report = [], set(), {}
    for host, uni, city, st in SITES:
        got = 0
        try:
            for q in QUERIES:
                raw = get(f"https://{host}/postings/search.atom?query={urllib.parse.quote(q)}")
                if b"<feed" not in raw[:600]:
                    raise ValueError("not a feed")
                for it in parse(raw):
                    kind = "Postdoc" if POSTDOC.search(it["title"]) else "Graduate" if GRAD.search(it["title"]) else ""
                    if not kind or not it["link"].startswith("https://") or it["link"] in seen:
                        continue
                    try:
                        age = (today - dt.date.fromisoformat(it["date"])).days
                    except ValueError:
                        age = 0
                    if age > MAX_AGE_DAYS:
                        continue
                    seen.add(it["link"])
                    blob = it["title"] + " " + it["body"]
                    rows.append({"kind": kind, "title": it["title"][:160], "uni": uni, "city": city, "st": st,
                                 "date": it["date"], "sum": summary(it["body"]), "pi": supervisor(it["body"]),
                                 "field": field(blob), "url": it["link"]})
                    got += 1
                time.sleep(0.5)
            report[uni] = got
        except Exception as ex:  # noqa: BLE001 - site not on PeopleAdmin, moved, or offline
            report.setdefault(uni, f"skipped ({type(ex).__name__})")
        print(f"{uni:45s} {report[uni]}", flush=True)

    if len(rows) < 10:
        print(f"only {len(rows)} positions found; keeping the previous file", file=sys.stderr)
        sys.exit(1 if not os.path.exists(OUT) else 0)
    rows.sort(key=lambda r: r["date"], reverse=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    unis = sorted({r["uni"] for r in rows})
    json.dump({"updated": today.isoformat(), "count": len(rows), "universities": unis, "rows": rows},
              open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))
    print(f"wrote {len(rows)} positions from {len(unis)} universities")


if __name__ == "__main__":
    import urllib.parse  # noqa: E402
    main()
