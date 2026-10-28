#!/usr/bin/env python3
"""
Evergreen "data guides": blog articles that answer the questions people search
for ("how many research papers are published per day", "which country
publishes the most research", ...). Rewritten from the latest data on every
daily run, so the numbers stay current and the date shows "updated".

    python scripts/guides.py        → posts/guides/*.md  (built by build_blog.py)
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "posts" / "guides"
SOUTH_ASIA = ["IN", "BD", "PK", "LK", "NP", "AF", "BT", "MV"]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "country"


def nice(d: str) -> str:
    x = dt.date.fromisoformat(d)
    return f"{x:%B} {x.day}, {x.year}"


def short(d: str) -> str:
    x = dt.date.fromisoformat(d)
    return f"{x:%b} {x.day}"


def cell(s: str) -> str:
    return str(s).replace("|", "/").replace("\n", " ")


def write(slug: str, title: str, summary: str, tags: str, date: str, body: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    head = (f"---\ntitle: {title}\ndate: {date}\nauthor: ResearchBoard\nslug: {slug}\n"
            f"summary: {summary}\ntags: {tags}\n---\n\n")
    (OUT / f"{slug}.md").write_text(head + body.strip() + "\n", encoding="utf-8")


def main() -> int:
    try:
        hist = json.loads((DATA / "history.json").read_text(encoding="utf-8"))
        latest = json.loads((DATA / "latest.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        print("guides: no data yet"); return 0
    try:
        inst = json.loads((DATA / "institutions.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        inst = {"days": {}, "names": {}, "country": {}}
    days, day = hist.get("days", {}), latest.get("latest_day")
    if not day or day not in days:
        return 0
    keys = [k for k in sorted(days) if k <= day][-30:]
    if len(keys) < 7:
        return 0
    names = latest.get("country_names", {})
    year = dt.date.fromisoformat(day).year
    span = f"{nice(keys[0])} – {nice(keys[-1])}"
    n = len(keys)
    upd = f"*Updated automatically every day. Data: {n} fully counted days, {span}. Source: [OpenAlex](https://openalex.org) and [PubMed](https://pubmed.ncbi.nlm.nih.gov/).*"
    ic = dict(inst.get("country", {})); ic.update({k: v for k, v in (latest.get("inst_country") or {}).items() if v})

    def ctry(code: str) -> str:
        nm = names.get(code, code)
        return f"[{cell(nm)}](../country/{slugify(nm)}.html)"

    # ---------------------------------------------------------------- 1. papers per day
    papers = [days[k].get("papers") or 0 for k in keys]
    pubmed = [days[k].get("pubmed_added") or 0 for k in keys]
    cites = [days[k].get("citations_made") or 0 for k in keys]
    avg = sum(papers) / n
    srt = sorted(papers); med = srt[n // 2] if n % 2 else (srt[n // 2 - 1] + srt[n // 2]) / 2
    # papers known only by month get dated the 1st, so the 1st of a month is a spike; keep it out of "typical"
    normal = [(v, k) for v, k in zip(papers, keys) if not (k.endswith("-01") and v > 2 * med)]
    hi, lo = max(normal), min(normal)
    spikes = [(v, k) for v, k in zip(papers, keys) if k.endswith("-01") and v > 2 * med]
    wd = {}
    for v, k in normal:
        wd.setdefault(dt.date.fromisoformat(k).strftime("%A"), []).append(v)
    mid = lambda xs: sorted(xs)[len(xs) // 2]
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    wd_rows = "\n".join(f"| {w} | {mid(wd[w]):,} |" for w in order if w in wd)
    busiest = max(wd, key=lambda w: mid(wd[w]))
    quietest = min(wd, key=lambda w: mid(wd[w]))
    spike_txt = (f" The exception is the 1st of each month: on {nice(spikes[0][1])} {spikes[0][0]:,} papers carry that date, because papers known only by their month are dated the 1st."
                 if spikes else "")
    last14 = "\n".join(f"| {short(k)} | {days[k].get('papers') or 0:,} | {days[k].get('pubmed_added') or 0:,} | {days[k].get('citations_made') or 0:,} |"
                       for k in reversed(keys[-14:]))
    write("how-many-research-papers-are-published-per-day",
          f"How many research papers are published every day? ({year} data)",
          f"On a typical day about {med:,.0f} research papers are published worldwide — about {avg * 365 / 1e6:.1f} million a year. Daily numbers, updated every day.",
          "data guide, papers, statistics", day, f"""
**On a typical day about {med:,.0f} research papers are published around the world** — about {med / 24:,.0f} every hour, or one every {86400 / med:.0f} seconds. Including papers dated only by month, the world publishes roughly **{avg * 365 / 1e6:.1f} million papers a year**.

{upd}

## How many papers a day, exactly?

Over the last {n} fully counted days the world published **{sum(papers):,} papers**, an average of **{avg:,.0f} a day** (typical day: {med:,.0f}). The busiest ordinary day was {nice(hi[1])} with {hi[0]:,} papers; the quietest was {nice(lo[1])} with {lo[0]:,}.{spike_txt}

PubMed, the main database for medicine and life sciences, added an average of **{sum(pubmed) / n:,.0f} records a day**. And every day new papers cite older work about **{sum(cites) / n:,.0f} times**.

## Which day of the week has the most papers?

{busiest} is the busiest publishing day and {quietest} the quietest. Typical papers per day of the week (median, leaving out the 1st of the month):

| Day | Typical papers |
| --- | ---: |
{wd_rows}

## The last 14 days

| Date | Papers | Added to PubMed | Citations made |
| --- | ---: | ---: | ---: |
{last14}

## What counts as a "paper"?

We count journal articles, reviews, preprints, letters, conference papers and book chapters, by their publication date, from OpenAlex, an open index of the world's research. Datasets, errata and peer reviews are left out. Recent days keep rising for about a week as journals report late, so we only use days that are fully counted.

See today's numbers live on the [ResearchBoard dashboard](../).
""")

    # ---------------------------------------------------------------- 2. countries
    tot = {}
    for k in keys:
        for c, v in (days[k].get("countries") or {}).items():
            tot[c] = tot.get(c, 0) + v
    ranked = sorted(tot.items(), key=lambda kv: -kv[1])
    world = sum(papers) or 1
    fdays = [k for k in keys if days[k].get("countries_frac")]
    ftot = {}
    for k in fdays:
        for c, v in days[k]["countries_frac"].items():
            ftot[c] = ftot.get(c, 0) + v
    fw = sum(days[k].get("papers") or 0 for k in fdays) or 1
    dlab = f"{len(fdays)} day" + ("s" if len(fdays) != 1 else "")
    fcol = f" Fractional share (last {dlab}) |" if fdays else ""
    fsep = " ---: |" if fdays else ""
    rows = "\n".join(f"| {i} | {ctry(c)} | {v:,} | {v / n:,.0f} | {v / world * 100:.1f}% |" + (f" {ftot[c] / fw * 100:.1f}% |" if c in ftot else (" — |" if fdays else ""))
                     for i, (c, v) in enumerate(ranked[:50], 1))
    fnote = (f"\n\n**Fractional** counts split papers written by authors from several countries equally between them (2 countries: ½ each), "
             f"so international co-authorship is not counted twice and the shares never add up to more than 100%. Available for the top countries over the last {dlab}. "
             f"[How we count](../about/methods.html)") if fdays else ""
    t1, t2, t3 = (names.get(c, c) for c, _ in ranked[:3])
    write(f"countries-that-publish-the-most-research",
          f"Which countries publish the most research papers? {year} ranking",
          f"{t1} publishes the most research papers, followed by {t2} and {t3}. Full ranking of {len(ranked)} countries, updated daily.",
          "data guide, countries, ranking", day, f"""
**{t1} publishes the most research papers in the world**, with {ranked[0][1]:,} papers in the last {n} days ({ranked[0][1] / world * 100:.0f}% of papers with a known country). **{t2}** is second with {ranked[1][1]:,} and **{t3}** third with {ranked[2][1]:,}.

{upd}

## Top 50 countries by research papers

A paper counts for a country when at least one author works at an institution there, so papers written by international teams count for every country involved.

| Rank | Country | Papers ({n} days) | Per day | Share |{fcol}
| ---: | --- | ---: | ---: | ---: |{fsep}
{rows}{fnote}

## How many countries publish research?

In the last {n} days, researchers in **{len(ranked)} countries and territories** published at least one paper. Click any country above for its own page with daily numbers, top universities and most-cited scientists, or search any country in the search box at the top.
""")

    # ---------------------------------------------------------------- 3. universities
    def inst_counts(k):
        if k in inst.get("days", {}):
            return inst["days"][k]
        return {x["id"]: x["count"] for x in days[k].get("institutions", [])}
    inames = dict(inst.get("names", {}))
    for k in keys:
        for x in days[k].get("institutions", []):
            inames.setdefault(x["id"], x["name"])
    it = {}
    for k in keys:
        for i, v in inst_counts(k).items():
            it[i] = it.get(i, 0) + v
    ir = sorted(it.items(), key=lambda kv: -kv[1])[:50]
    if ir:
        rows = "\n".join(f"| {j} | [{cell(inames.get(i, i))}](../explore/?id={i}) | {cell(names.get(ic.get(i) or '', ic.get(i) or '—'))} | {v:,} |"
                         for j, (i, v) in enumerate(ir, 1))
        u1 = inames.get(ir[0][0], ir[0][0])
        write(f"top-universities-by-research-output",
              f"Top 50 universities and research institutions by papers published ({year})",
              f"{u1} is the world's most active research institution. Top 50 universities and institutes by papers in the last {n} days, updated daily.",
              "data guide, universities, ranking", day, f"""
**{u1} published the most research papers of any institution** in the last {n} days, with {ir[0][1]:,} papers. This ranking counts papers with at least one author from each university or research institute.

{upd}

## Top 50 institutions by papers published

| Rank | Institution | Country | Papers ({n} days) |
| ---: | --- | --- | ---: |
{rows}

## How is this different from university rankings?

Rankings such as QS or Times Higher Education mix teaching, reputation and citations. This list measures one thing only: **how many research papers each institution publishes**, counted every day from open data. Large national research organisations (for example academies of sciences) often top it because they include many institutes.

Look up any university's papers day by day with the search box at the top of every page, or see the [live universities ranking](../universities/).
""")

    # ---------------------------------------------------------------- 4. most-cited papers
    hp = latest.get("hot_papers") or []
    tp = latest.get("top_papers") or []
    if hp:
        def prow(p, i):
            link = p.get("doi") or f"https://openalex.org/{p.get('id')}"
            return f"| {i} | [{cell(p.get('title', ''))}]({link}) | {cell(p.get('venue') or '—')} | {p.get('year') or ''} | {p.get('citations', 0):,} |"
        write(f"most-cited-research-papers",
              f"Most-cited research papers of {year - 1}–{year}",
              f"The most-cited recent paper is “{cell(hp[0]['title'])[:80]}” with {hp[0]['citations']:,} citations. Top 20 new papers and all-time leaders, updated daily.",
              "data guide, citations, papers", day, f"""
**The most-cited research paper published in {year - 1} or {year} is "{cell(hp[0]['title'])}"** ({hp[0].get('venue') or 'unknown journal'}), with **{hp[0]['citations']:,} citations** so far.

{upd}

## Top 20 most-cited papers of the last two years

| # | Paper | Journal | Year | Citations |
| ---: | --- | --- | ---: | ---: |
{chr(10).join(prow(p, i) for i, p in enumerate(hp[:20], 1))}

## Most-cited papers of all time

| # | Paper | Journal | Year | Citations |
| ---: | --- | --- | ---: | ---: |
{chr(10).join(prow(p, i) for i, p in enumerate(tp[:10], 1))}

## Why are these papers cited so much?

Papers that describe widely used methods, software, statistics or guidelines collect the most citations, because thousands of later studies rely on them. Yearly cancer statistics, analysis tools and survey papers on fast-moving fields such as large language models are typical examples.

See today's citation movers on the [papers page](../papers/).
""")

    # ---------------------------------------------------------------- 5. scientists
    ta = latest.get("top_authors") or []
    if ta:
        rows = "\n".join(f"| {i} | {cell(a['name'])} | {cell(a.get('institution') or '—')} | {cell(names.get(a.get('country') or '', a.get('country') or '—'))} | {a['citations']:,} |"
                         for i, a in enumerate(ta[:30], 1))
        write(f"most-cited-scientists-in-the-world",
              f"The most-cited scientists in the world ({year} list)",
              f"{ta[0]['name']} is the most-cited scientist with {ta[0]['citations']:,} citations. Top 30 list with institutions and countries, updated daily.",
              "data guide, scientists, citations", day, f"""
**{ta[0]['name']} is the most-cited scientist in the world**, with **{ta[0]['citations']:,} citations**, followed by {ta[1]['name']} and {ta[2]['name']}.

{upd}

## Top 30 most-cited scientists

| # | Scientist | Institution | Country | Citations |
| ---: | --- | --- | --- | ---: |
{rows}

## How are citations counted?

A citation is one paper referring to another. Each scientist's total adds up the citations of all their papers in OpenAlex. Authors of widely used methods, statistics and reporting guidelines lead the list. Name matching is automatic, so a few totals may combine or split people with similar names.

See who is gaining citations today on the [scientists page](../scientists/).
""")

    # ---------------------------------------------------------------- 6. journals
    jt, jn = {}, {}
    for k in keys:
        for x in days[k].get("journals") or []:
            jt[x["id"]] = jt.get(x["id"], 0) + x["count"]; jn[x["id"]] = x["name"]
    jr = sorted(jt.items(), key=lambda kv: -kv[1])[:30]
    if jr:
        rows = "\n".join(f"| {i} | {cell(jn[j])} | {v:,} | {v / n:,.0f} |" for i, (j, v) in enumerate(jr, 1))
        write(f"journals-that-publish-the-most-papers",
              f"Which journals publish the most papers? ({year})",
              f"{jn[jr[0][0]]} published the most papers in the last {n} days. Top 30 journals by papers published, updated daily.",
              "data guide, journals, publishing", day, f"""
**{cell(jn[jr[0][0]])} published the most papers** of any journal in the last {n} days ({jr[0][1]:,} papers), ahead of {cell(jn[jr[1][0]])} and {cell(jn[jr[2][0]])}.

{upd}

## Top 30 journals by papers published

| Rank | Journal | Papers ({n} days) | Per day |
| ---: | --- | ---: | ---: |
{rows}

## Are bigger journals better?

No. A high number of papers says nothing about quality: large open-access "mega-journals" publish thousands of papers a year, while many top journals publish only a few hundred. Use this list to see where research is being published, not to judge papers.

See the [live journals ranking](../journals/).
""")

    # ---------------------------------------------------------------- 7. fields
    ft, fn = {}, {}
    for k in keys:
        for x in days[k].get("fields") or []:
            ft[x["id"]] = ft.get(x["id"], 0) + x["count"]; fn[x["id"]] = x["name"]
    fr = sorted(ft.items(), key=lambda kv: -kv[1])
    if fr:
        ftot = sum(v for _, v in fr) or 1
        rows = "\n".join(f"| {i} | {cell(fn[f])} | {v:,} | {v / ftot * 100:.1f}% |" for i, (f, v) in enumerate(fr, 1))
        write(f"research-fields-with-the-most-papers",
              f"Which research fields publish the most papers? ({year})",
              f"{fn[fr[0][0]]} is the largest research field with {fr[0][1] / ftot * 100:.0f}% of new papers. All {len(fr)} fields ranked, updated daily.",
              "data guide, fields, statistics", day, f"""
**{cell(fn[fr[0][0]])} is the largest field of research**, with {fr[0][1] / ftot * 100:.1f}% of all new papers in the last {n} days, followed by {cell(fn[fr[1][0]])} ({fr[1][1] / ftot * 100:.1f}%) and {cell(fn[fr[2][0]])} ({fr[2][1] / ftot * 100:.1f}%).

{upd}

## All research fields ranked

| Rank | Field | Papers ({n} days) | Share |
| ---: | --- | ---: | ---: |
{rows}

Each paper is counted once, under its main field (OpenAlex topics). See the [live fields page](../fields/).
""")

    # ---------------------------------------------------------------- 8. South Asia
    sa = [(c, tot.get(c, 0)) for c in SOUTH_ASIA if tot.get(c)]
    sa.sort(key=lambda kv: -kv[1])
    if len(sa) >= 3:
        rank_of = {c: i for i, (c, _) in enumerate(ranked, 1)}
        rows = "\n".join(f"| {i} | {ctry(c)} | {v:,} | {v / n:,.0f} | #{rank_of.get(c, '—')} |" for i, (c, v) in enumerate(sa, 1))
        bd = tot.get("BD", 0)
        write(f"research-output-south-asia",
              f"Research output in South Asia: India, Bangladesh, Pakistan, Sri Lanka and Nepal ({year})",
              f"India leads South Asia in research papers; Bangladesh publishes about {bd / n:,.0f} a day. Country comparison, updated daily.",
              "data guide, South Asia, Bangladesh, India, Pakistan", day, f"""
**{names.get(sa[0][0], sa[0][0])} publishes the most research in South Asia** ({sa[0][1]:,} papers in the last {n} days), followed by {names.get(sa[1][0], sa[1][0])} ({sa[1][1]:,}) and {names.get(sa[2][0], sa[2][0])} ({sa[2][1]:,}). **Bangladesh** published {bd:,} papers, about **{bd / n:,.0f} a day**.

{upd}

## South Asian countries compared

| # | Country | Papers ({n} days) | Per day | World rank |
| ---: | --- | ---: | ---: | ---: |
{rows}

## Follow your country

Every country has its own page with papers per day, top universities and most-cited scientists. ResearchBoard also posts a daily Bangladesh update on Facebook. Use the search box at the top to look up any university, for example University of Dhaka or BUET.
""")
    rank_of = {c: i for i, (c, _) in enumerate(ranked, 1)}

    # ---------------------------------------------------------------- 9. country vs country
    PAIRS = [("BD", "PK"), ("IN", "CN"), ("US", "CN"), ("IN", "PK"), ("BD", "IN"), ("ID", "MY"),
             ("NG", "ZA"), ("EG", "SA"), ("BR", "MX"), ("TR", "IR"), ("GB", "DE"), ("JP", "KR")]
    for a, b in PAIRS:
        if not (tot.get(a) and tot.get(b)):
            continue
        na, nb = names.get(a, a), names.get(b, b)
        win, lose = (a, b) if tot[a] >= tot[b] else (b, a)
        ratio = tot[win] / max(1, tot[lose])
        sa_, sb_ = [(days[k].get("countries") or {}).get(a, 0) for k in keys], [(days[k].get("countries") or {}).get(b, 0) for k in keys]
        wins_a = sum(1 for x, y in zip(sa_, sb_) if x > y)
        rows = "\n".join(f"| {short(k)} | {x:,} | {y:,} |" for k, x, y in list(zip(keys, sa_, sb_))[::-1][:14])
        write(f"{slugify(na)}-vs-{slugify(nb)}-research-output",
              f"{na} vs {nb}: which publishes more research? ({year})",
              f"{names.get(win, win)} publishes {ratio:.1f}× as many research papers as {names.get(lose, lose)}. Daily comparison, updated every day.",
              f"data guide, comparison, {na}, {nb}", day, f"""
**{names.get(win, win)} publishes more research than {names.get(lose, lose)}** — {tot[win]:,} papers against {tot[lose]:,} in the last {n} days, about **{ratio:.1f} times as many**.

{upd}

## {na} and {nb} compared

| | {ctry(a)} | {ctry(b)} |
| --- | ---: | ---: |
| Papers, last {n} days | {tot[a]:,} | {tot[b]:,} |
| Papers per day | {tot[a] / n:,.0f} | {tot[b] / n:,.0f} |
| World rank | #{rank_of.get(a, '—')} | #{rank_of.get(b, '—')} |
| Share of world papers | {tot[a] / world * 100:.2f}% | {tot[b] / world * 100:.2f}% |
| Days ahead (of {n}) | {wins_a} | {n - wins_a} |

## Day by day, last 14 days

| Date | {cell(na)} | {cell(nb)} |
| --- | ---: | ---: |
{rows}

## How to read this

A paper counts for a country when at least one author works there, so a paper written together by {na} and {nb} researchers counts for both. Larger countries publish more in total; the share of world papers shows how much each contributes globally.

Open the full pages for [{cell(na)}](../country/{slugify(na)}.html) and [{cell(nb)}](../country/{slugify(nb)}.html), or compare any other country with the search box at the top.
""")

    # ---------------------------------------------------------------- 10. fastest-growing countries
    if n >= 28:
        h1, h2 = keys[:14], keys[14:28]
        A = {c: sum((days[k].get("countries") or {}).get(c, 0) for k in h1) for c in tot}
        B = {c: sum((days[k].get("countries") or {}).get(c, 0) for k in h2) for c in tot}
        TA, TB = sum(A.values()) or 1, sum(B.values()) or 1
        grow = [(c, B[c], (B[c] / TB) / (A[c] / TA) - 1) for c in tot if A[c] >= 200 and B[c] >= 200]
        grow.sort(key=lambda x: -x[2])
        up = [g for g in grow if g[2] > 0][:20]
        if len(up) >= 5:
            rows = "\n".join(f"| {i} | {ctry(c)} | {v:,} | +{g * 100:.0f}% |" for i, (c, v, g) in enumerate(up, 1))
            write(f"fastest-growing-research-countries",
                  f"Fastest-growing research countries right now ({year})",
                  f"{names.get(up[0][0], up[0][0])} grew its share of world research the most in the last two weeks. Top 20 rising countries, updated daily.",
                  "data guide, countries, growth", day, f"""
**{names.get(up[0][0], up[0][0])} is the fastest-growing research country right now**: its share of the world's new papers rose {up[0][2] * 100:.0f}% in the last two weeks compared with the two weeks before.

{upd}

## Top 20 rising countries

We compare each country's **share of world papers** in the latest 14 days ({short(h2[0])}–{short(h2[-1])}) with the 14 days before ({short(h1[0])}–{short(h1[-1])}). Using shares instead of raw counts keeps the comparison fair, because the most recent days are still being filled in. Only countries with at least 200 papers in each period are included.

| # | Country | Papers (latest 14 days) | Share growth |
| ---: | --- | ---: | ---: |
{rows}

Short-term changes can come from conferences, special journal issues or holidays, so check a country's page for the longer trend.
""")

    # ---------------------------------------------------------------- 11. top universities in a country
    by_c = {}
    for i, v in it.items():
        c = ic.get(i)
        if c:
            by_c.setdefault(c, []).append((i, v))
    for c, lst in by_c.items():
        if c == "BD" or len(lst) < 8:
            continue
        lst.sort(key=lambda kv: -kv[1])
        nm = names.get(c, c)
        rows = "\n".join(f"| {j} | [{cell(inames.get(i, i))}](../explore/?id={i}) | {v:,} | {v / n:,.0f} |" for j, (i, v) in enumerate(lst[:25], 1))
        write(f"top-universities-in-{slugify(nm)}-by-research",
              f"Top universities in {nm} by research output ({year})",
              f"{inames.get(lst[0][0], lst[0][0])} publishes the most research in {nm}. Ranking of {nm}'s most active universities and institutes, updated daily.",
              f"data guide, universities, {nm}", day, f"""
**{cell(inames.get(lst[0][0], lst[0][0]))} is the most active research institution in {nm}**, with {lst[0][1]:,} papers in the last {n} days.

{upd}

## Most active institutions in {nm}

| Rank | Institution | Papers ({n} days) | Per day |
| ---: | --- | ---: | ---: |
{rows}

This list includes institutions that were among the 200 most active in the world on at least one day. See all of [{cell(nm)}'s research](../country/{slugify(nm)}.html) or search any institution at the top of the page.
""")

    # ---------------------------------------------------------------- 12. Bangladesh universities (from the daily Bangladesh snapshot)
    try:
        bd = json.loads((DATA / "bd_snapshot.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        bd = None
    if bd and bd.get("institutions"):
        lst = sorted(bd["institutions"].items(), key=lambda kv: -kv[1][1])
        rows = "\n".join(f"| {j} | {cell(nm_)} | {v:,} |" for j, (i, (nm_, v)) in enumerate(lst[:40], 1))
        try:
            bh = json.loads((DATA / "bd_history.json").read_text(encoding="utf-8")).get("days", [])
        except (FileNotFoundError, json.JSONDecodeError):
            bh = []
        ok = [x for x in bh if not x.get("flagged")][-14:]
        daily = ""
        if ok:
            daily = "## New Bangladeshi papers, day by day\n\n| Date (Dhaka morning) | New papers | Institutions |\n| --- | ---: | ---: |\n" + "\n".join(
                f"| {short(x['to'][:10])} | +{x['papers_added']:,} | {x['institutions_added']:,} |" for x in reversed(ok))
        write(f"top-universities-in-bangladesh-by-research",
              f"Top universities in Bangladesh by research output ({year})",
              f"{lst[0][1][0]} leads Bangladesh in research papers. Top 40 Bangladeshi universities and institutes by papers since {year - 1}, updated daily.",
              "data guide, Bangladesh, universities", day, f"""
**{cell(lst[0][1][0])} publishes the most research in Bangladesh**, with {lst[0][1][1]:,} papers since January {year - 1}, followed by {cell(lst[1][1][0])} ({lst[1][1][1]:,}) and {cell(lst[2][1][0])} ({lst[2][1][1]:,}). In total, researchers in Bangladesh have published **{bd.get('total', 0):,} papers** since January {year - 1} ({bd.get('articles', 0):,} journal articles).

*Updated automatically every day. Counts: papers published in {year - 1}–{year} with at least one author at each institution. Source: [OpenAlex](https://openalex.org).*

## Top 40 Bangladeshi universities and institutes

| Rank | Institution | Papers ({year - 1}–{year}) |
| ---: | --- | ---: |
{rows}

{daily}

ResearchBoard posts the last 24 hours of Bangladeshi research every morning on Facebook. See [Bangladesh's country page](../country/bangladesh.html) for papers per day and the [South Asia comparison](research-output-south-asia.html).
""")

    print(f"guides: {len(list(OUT.glob('*.md')))} data guides written for {day}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
