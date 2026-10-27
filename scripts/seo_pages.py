#!/usr/bin/env python3
"""
Search-engine pages built from the daily data (run by build_blog.py):

  country/index.html          all countries, ranked by papers on the latest fully counted day
  country/<slug>.html         one page per country, rewritten every day
  blog/_index.html            the homepage with a plain-text daily summary and a
                              schema.org Dataset description (the workflow publishes it
                              as the site's index.html)

Returns the extra URLs for the sitemap.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
from pathlib import Path

esc = html.escape


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "country"


def nice(d: dt.date) -> str:
    return f"{d:%B} {d.day}, {d.year}"


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def spark_svg(values: list, labels: list[str]) -> str:
    """Small bar chart as inline SVG (no JavaScript needed)."""
    vals = [v or 0 for v in values]
    if not vals or not max(vals):
        return ""
    w, h, gap = 640, 140, 3
    bw = (w - gap * (len(vals) - 1)) / len(vals)
    top = max(vals)
    bars = []
    for i, (v, lab) in enumerate(zip(vals, labels)):
        bh = max(2, v / top * (h - 20))
        x = i * (bw + gap)
        bars.append(f'<rect x="{x:.1f}" y="{h - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="2">'
                    f'<title>{esc(lab)}: {v:,} papers</title></rect>')
    return (f'<svg class="c-spark" viewBox="0 0 {w} {h}" role="img" '
            f'aria-label="Papers per day over the last {len(vals)} days">{"".join(bars)}</svg>')


def build(root: Path, site_url: str, page, out_blog: Path) -> list[tuple[str, str, str, str]]:
    data = root / "data"
    try:
        hist = json.loads((data / "history.json").read_text(encoding="utf-8"))
        latest = json.loads((data / "latest.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    days = hist.get("days", {})
    day = latest.get("latest_day")
    if not day or day not in days:
        return []
    d = dt.date.fromisoformat(day)
    rec = days[day]
    names = latest.get("country_names", {})
    counts = rec.get("countries") or {}
    if isinstance(counts, list):  # old format
        counts = {c.get("code"): c.get("count") for c in counts}
    world = rec.get("papers") or sum(counts.values()) or 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    rank_of = {c: i + 1 for i, (c, _) in enumerate(ranked)}
    keys30 = [k for k in sorted(days) if k <= day][-30:]
    detail = latest.get("countries_detail", {})
    pubmed_c = rec.get("pubmed_by_country") or {}

    def cc(day_key, code):
        c = days.get(day_key, {}).get("countries") or {}
        return c.get(code, 0) if isinstance(c, dict) else 0

    # every country seen in the last 30 days
    codes = set()
    for k in keys30:
        c = days[k].get("countries") or {}
        if isinstance(c, dict):
            codes.update(c)
    codes = sorted(codes, key=lambda c: (-counts.get(c, 0), names.get(c, c)))

    out = root / "country"
    if out.exists():
        for f in out.glob("*.html"):
            f.unlink()
    out.mkdir(exist_ok=True)

    def fix_nav(htm: str) -> str:
        """The shared template is written for /blog/; adjust links for /country/."""
        return (htm.replace('<a href="./" class="on">Blog</a>', '<a href="../blog/">Blog</a>')
                   .replace('<a href="../#countries">Countries</a>', '<a href="./" class="on">Countries</a>')
                   .replace('href="feed.xml"', 'href="../blog/feed.xml"'))

    urls = [(f"{site_url}/country/", day, "daily", "0.8")]
    rows = []
    for code in codes:
        name = names.get(code) or (detail.get(code) or {}).get("name") or code
        slug = slugify(name)
        n = counts.get(code, 0)
        series = [cc(k, code) for k in keys30]
        last7 = sum(series[-7:])
        total30 = sum(series)
        avg30 = total30 / max(1, len(series))
        share = n / world * 100 if world else 0
        rank = rank_of.get(code)
        det = detail.get(code) or {}
        pm = det.get("pubmed_added", pubmed_c.get(code))
        rows.append((code, name, slug, n, rank, share, total30))

        rank_txt = f"ranking <b>{ordinal(rank)}</b> of {len(ranked)} countries" if rank else "not among the countries with papers that day"
        lead = (f"On <b>{nice(d)}</b>, researchers affiliated with institutions in <b>{esc(name)}</b> published "
                f"<b>{n:,}</b> research papers, {rank_txt} and <b>{share:.1f}%</b> of the world's output that day.")
        if pm:
            lead += f" <b>{pm:,}</b> records with a {esc(name)} affiliation were added to PubMed."
        stats = [("Papers on " + f"{d:%b} {d.day}", f"{n:,}"), ("World rank", f"#{rank}" if rank else "—"),
                 ("Share of world output", f"{share:.1f}%"), ("Last 7 days", f"{last7:,}"),
                 ("Last 30 days", f"{total30:,}"), ("Daily average (30 days)", f"{avg30:,.0f}")]
        stat_html = "".join(f'<div class="c-stat"><span>{esc(k)}</span><b>{esc(v)}</b></div>' for k, v in stats)

        insts = det.get("top_institutions") or []
        inst_html = ""
        if insts:
            inst_html = ("<h2>Most active institutions</h2><ol class=\"c-list\">" +
                         "".join(f"<li>{esc(i.get('name', ''))} <span class=\"muted\">· {i.get('count', 0):,} papers</span></li>"
                                 for i in insts[:5]) + "</ol>")
        auth = det.get("top_authors") or []
        auth_html = ""
        if auth:
            auth_html = ("<h2>Most-cited scientists</h2><ol class=\"c-list\">" +
                         "".join(f"<li>{esc(a.get('name', ''))} <span class=\"muted\">· {esc(a.get('institution') or '')}"
                                 f" · {a.get('citations', 0):,} citations</span></li>" for a in auth[:5]) + "</ol>")

        last14 = list(zip(keys30, series))[-14:]
        table = ("<h2>Papers per day</h2><table class=\"c-table\"><thead><tr><th>Date</th><th>Papers</th></tr></thead><tbody>" +
                 "".join(f"<tr><td>{dt.date.fromisoformat(k):%a, %b} {dt.date.fromisoformat(k).day}</td><td>{v:,}</td></tr>"
                         for k, v in reversed(last14)) + "</tbody></table>")

        i = codes.index(code)
        neigh = [c for c in (codes[i - 1] if i > 0 else None, codes[i + 1] if i + 1 < len(codes) else None) if c]
        neigh_html = " · ".join(f'<a href="{slugify(names.get(c, c))}.html">{esc(names.get(c, c))}</a>' for c in neigh)

        ld = json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "ResearchBoard", "item": f"{site_url}/"},
            {"@type": "ListItem", "position": 2, "name": "Countries", "item": f"{site_url}/country/"},
            {"@type": "ListItem", "position": 3, "name": name, "item": f"{site_url}/country/{slug}.html"}]})
        body = f"""<article class="post c-page">
<p class="post-meta"><a href="./">All countries</a> · Updated daily · Latest fully counted day: {nice(d)}</p>
<h1><span class="fi fi-{code.lower()}"></span> {esc(name)}: research output today</h1>
<p class="lead">{lead}</p>
<div class="c-stats">{stat_html}</div>
<h2>Last 30 days</h2>
{spark_svg(series, keys30)}
{inst_html}
{auth_html}
{table}
<p class="muted small">Counts are papers (articles, reviews, preprints, letters, conference papers and book chapters) with at least one author
affiliated with an institution in {esc(name)}, by publication date, from <a href="https://openalex.org" rel="noopener">OpenAlex</a>.
Recent days keep rising for a week as journals report their papers.</p>
<p><a class="btn" href="../">Open the live dashboard</a> {('· Nearby in the ranking: ' + neigh_html) if neigh_html else ''}</p>
</article>"""
        title = f"{name} research output today: papers, universities and scientists · ResearchBoard"
        desc = (f"{name}: {n:,} research papers published on {nice(d)}" + (f" (#{rank} worldwide)" if rank else "") +
                f". Daily research statistics for {name}: papers, top universities and most-cited scientists, updated every day.")
        htm = page(title, desc, body, f"{site_url}/country/{slug}.html", active="Countries", extra_head=
                   f'<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flag-icons@7.2.3/css/flag-icons.min.css">'
                   f'<script type="application/ld+json">{ld}</script>')
        (out / f"{slug}.html").write_text(fix_nav(htm), encoding="utf-8")
        urls.append((f"{site_url}/country/{slug}.html", day, "daily", "0.6"))

    # index of all countries
    trs = "".join(
        f'<tr><td>{r or "—"}</td><td><span class="fi fi-{c.lower()}"></span> <a href="{s}.html">{esc(nm)}</a></td>'
        f'<td>{n:,}</td><td>{sh:.1f}%</td><td>{t30:,}</td></tr>'
        for c, nm, s, n, r, sh, t30 in sorted(rows, key=lambda x: (x[4] or 9999, x[1])))
    body = f"""<article class="post c-page">
<h1>Research output by country</h1>
<p class="lead">Papers published by researchers in each country on <b>{nice(d)}</b>, the latest fully counted day,
with their share of world output and the total for the last 30 days. Updated every day from open data.</p>
<table class="c-table c-all"><thead><tr><th>#</th><th>Country</th><th>Papers</th><th>Share</th><th>Last 30 days</th></tr></thead>
<tbody>{trs}</tbody></table>
</article>"""
    htm = page("Research output by country, updated daily · ResearchBoard",
               f"Which countries publish the most research? Daily ranking of {len(rows)} countries by papers published, "
               f"with share of world output. Latest: {nice(d)}.", body, f"{site_url}/country/", active="Countries",
               extra_head='<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flag-icons@7.2.3/css/flag-icons.min.css">')
    (out / "index.html").write_text(fix_nav(htm), encoding="utf-8")

    # homepage with a plain-text summary and a Dataset description
    idx = (root / "index.html").read_text(encoding="utf-8")
    top3 = ", ".join(f"{names.get(c, c)} ({n:,})" for c, n in ranked[:3])
    inst = (rec.get("institutions") or [{}])[0]
    summary = (f"Latest fully counted day, {nice(d)}: {world:,} research papers were published worldwide by authors in "
               f"{rec.get('countries_active', len(counts)):,} countries"
               + (f", {rec['pubmed_added']:,} records were added to PubMed" if rec.get("pubmed_added") else "")
               + (f" and {rec['citations_made']:,} new citations were made" if rec.get("citations_made") else "")
               + f". Leading countries: {top3}."
               + (f" Most active institution: {inst['name']} ({inst['count']:,} papers)." if inst.get("name") else ""))
    idx = idx.replace('<p id="sumText"></p>', f'<p id="sumText">{esc(summary)}</p>', 1)
    dataset = {
        "@context": "https://schema.org", "@type": "Dataset",
        "name": "ResearchBoard: daily global research output",
        "description": ("Daily counts of research papers published worldwide, records added to PubMed, citations made, "
                        "and rankings of countries, institutions, journals and research fields. Updated every day from "
                        "OpenAlex and PubMed."),
        "url": f"{site_url}/", "isAccessibleForFree": True,
        "keywords": ["research output", "scientific publications", "citations", "bibliometrics", "PubMed",
                     "OpenAlex", "research by country", "university rankings"],
        "creator": {"@type": "Organization", "name": "ResearchBoard", "url": f"{site_url}/"},
        "temporalCoverage": f"{min(days)}/{day}", "dateModified": day,
        "isBasedOn": ["https://openalex.org", "https://pubmed.ncbi.nlm.nih.gov/"],
        "distribution": [
            {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{site_url}/data/history.json"},
            {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{site_url}/data/latest.json"}],
    }
    desc = esc(f"Live daily board of global research. {nice(d)}: {world:,} papers worldwide; top countries {top3}. "
               "Papers, PubMed, citations, countries, universities and journals.")
    idx = re.sub(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{desc}">', idx, 1)
    idx = idx.replace("</head>", f'<link rel="canonical" href="{site_url}/">\n'
                                  f'<script type="application/ld+json">{json.dumps(dataset)}</script>\n</head>', 1)
    (out_blog / "_index.html").write_text(idx, encoding="utf-8")
    print(f"SEO pages: {len(rows)} country pages, homepage summary for {day}")
    return urls
