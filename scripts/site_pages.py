#!/usr/bin/env python3
"""
Category pages and site search, rebuilt from the daily data by build_blog.py.

  site_extra/universities/  journals/  fields/  papers/  scientists/  market/  explore/
  blog/_search-index.json   (published as data/search-index.json)

The workflow copies site_extra/* to the site root.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
from pathlib import Path

esc = html.escape
FLAGS = '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flag-icons@7.2.3/css/flag-icons.min.css">'


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "country"


def nice(d: str) -> str:
    x = dt.date.fromisoformat(d)
    return f"{x:%a}, {x:%b} {x.day}, {x.year}"


def f(n) -> str:
    return "—" if n is None else f"{n:,}"


def flag(cc: str | None) -> str:
    return f'<span class="fi fi-{cc.lower()}"></span>' if cc and len(cc) == 2 else ""


def head_block(crumb: str, title: str, lead: str, tabs: str = "") -> str:
    return (f'<div class="crumb"><a href="../">Home</a> › {esc(crumb)}</div>'
            f'<div class="cat-head"><div><h1>{esc(title)}</h1><p>{lead}</p></div>{tabs}</div>')


def tabs_html(csv: str, extra: str = "") -> str:
    return (f'<div class="tabs" data-tabs><button data-tab="d1" class="on">Day</button><button data-tab="d7">7 days</button>'
            f'<button data-tab="d30">30 days</button>{extra}<button data-csv="{csv}">⬇ CSV</button></div>')


def vbars(values: list, labels: list) -> str:
    vals = [v or 0 for v in values]
    if not vals or not max(vals):
        return ""
    w, h, gap = 640, 150, 3
    bw = (w - gap * (len(vals) - 1)) / len(vals)
    top = max(vals)
    out = []
    for i, (v, lab) in enumerate(zip(vals, labels)):
        bh = max(2, v / top * (h - 12))
        cls = ' class="last"' if i == len(vals) - 1 else ""
        out.append(f'<rect{cls} x="{i * (bw + gap):.1f}" y="{h - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="2">'
                   f"<title>{esc(lab)}: {v:,}</title></rect>")
    return f'<svg class="vbars" viewBox="0 0 {w} {h}" role="img" aria-label="Daily values">{"".join(out)}</svg>'


def hbars(rows: list[tuple[str, int]]) -> str:
    if not rows:
        return ""
    top = max(v for _, v in rows) or 1
    return '<div class="hbars">' + "".join(
        f'<div><span title="{esc(n)}">{esc(n)}</span><i style="width:{v / top * 100:.1f}%"></i><b>{v:,}</b></div>' for n, v in rows) + "</div>"


def ranked_table(rows: list[dict], cols: list[tuple[str, str, bool]]) -> str:
    """cols: (header, key, right_aligned). Values are pre-formatted HTML strings."""
    hm = lambda k: " hm" if k in ("j", "y", "i") else ""  # columns hidden on phones
    th = "".join(f'<th class="{"r" if r else ""}{hm(k)}">{esc(h)}</th>' for h, k, r in cols)
    trs = "".join("<tr>" + "".join(f'<td class="{"r" if r else ("nm" if k == "name" else "")}{hm(k)}">{row.get(k, "")}</td>'
                                   for _, k, r in cols) + "</tr>" for row in rows)
    return f'<table class="rt"><thead><tr>{th}</tr></thead><tbody>{trs or "<tr><td>No data yet.</td></tr>"}</tbody></table>'


def build(root: Path, site_url: str, page, out_blog: Path) -> list[tuple[str, str, str, str]]:
    data = root / "data"
    try:
        hist = json.loads((data / "history.json").read_text(encoding="utf-8"))
        latest = json.loads((data / "latest.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    try:
        inst = json.loads((data / "institutions.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        inst = {"days": {}, "names": {}, "country": {}}
    days = hist.get("days", {})
    day = latest.get("latest_day")
    if not day or day not in days:
        return []
    keys = [k for k in sorted(days) if k <= day]
    names = latest.get("country_names", {})
    ic = dict(inst.get("country", {}))
    ic.update({k: v for k, v in (latest.get("inst_country") or {}).items() if v})
    out = root / "site_extra"
    out.mkdir(exist_ok=True)
    urls = []

    def write(name: str, title: str, desc: str, body: str, active: str):
        d = out / name
        d.mkdir(exist_ok=True)
        htm = page(title, desc, f'<div class="page">{body}</div>', f"{site_url}/{name}/", extra_head=FLAGS,
                   active=active, main_class="cat-main")
        (d / "index.html").write_text(htm, encoding="utf-8")
        urls.append((f"{site_url}/{name}/", day, "daily", "0.7"))

    # ------------------------------------------------------------------ universities
    def inst_counts(k: str) -> dict:
        if k in inst.get("days", {}):
            return inst["days"][k]
        return {x["id"]: x["count"] for x in days.get(k, {}).get("institutions", [])}

    inames = dict(inst.get("names", {}))
    for k in keys[-30:]:
        for x in days[k].get("institutions", []):
            inames.setdefault(x["id"], x["name"])

    def period(k_list, getter):
        tot: dict = {}
        for k in k_list:
            for i, v in getter(k).items():
                tot[i] = tot.get(i, 0) + v
        return sorted(tot.items(), key=lambda kv: -kv[1])

    prior7 = keys[-8:-1]
    avg7 = {}
    for k in prior7:
        for i, v in inst_counts(k).items():
            avg7[i] = avg7.get(i, 0) + v / max(1, len(prior7))

    def inst_rows(pairs, with_delta):
        rows = []
        for n, (i, v) in enumerate(pairs[:50], 1):
            row = {"n": n, "name": f'<a href="../explore/?id={esc(i)}">{esc(inames.get(i, i))}</a>',
                   "cc": f'{flag(ic.get(i))}{esc(ic.get(i) or "")}', "v": f"<b>{v:,}</b>"}
            if with_delta:
                a = avg7.get(i)
                if a:
                    ch = (v - a) / a * 100
                    row["dl"] = f'<span class="{"up" if ch >= 0 else "down"}">{"▲" if ch >= 0 else "▼"} {abs(ch):.1f}%</span>'
            rows.append(row)
        return rows

    cols1 = [("#", "n", False), ("Institution", "name", False), ("Country", "cc", False), ("Papers", "v", True), ("vs 7-day avg", "dl", True)]
    colsN = [("#", "n", False), ("Institution", "name", False), ("Country", "cc", False), ("Papers", "v", True)]
    p1 = period([day], inst_counts)
    panels = (f'<div data-panel="d1">{ranked_table(inst_rows(p1, True), cols1)}</div>'
              f'<div data-panel="d7" hidden>{ranked_table(inst_rows(period(keys[-7:], inst_counts), False), colsN)}</div>'
              f'<div data-panel="d30" hidden>{ranked_table(inst_rows(period(keys[-30:], inst_counts), False), colsN)}</div>')
    by_c: dict = {}
    for i, v in p1:
        c = ic.get(i)
        if c:
            by_c[c] = by_c.get(c, 0) + 1
    rec = days[day]
    side = (f'<section class="panel2"><h2>At a glance</h2><div class="kp">'
            f'<div><span>Active institutions</span><b>{f(rec.get("institutions_active"))}</b></div>'
            f'<div><span>Most active</span><b style="font-size:15px">{esc(inames.get(p1[0][0], "—")) if p1 else "—"}</b></div></div>'
            f'<p class="note">Day view: the {min(50, len(p1))} most active of the top {len(p1)} institutions on {nice(day)}. '
            f'7- and 30-day views add up each day\'s top list.</p></section>'
            f'<section class="panel2"><h2>Countries in the day\'s top list</h2>'
            f'{hbars([(names.get(c, c), n) for c, n in sorted(by_c.items(), key=lambda kv: -kv[1])[:8]])}</section>')
    body = head_block("Universities", "Most active universities & institutions",
                      f"Papers with at least one author from each institution · latest fully counted day: <b>{nice(day)}</b>. "
                      f'Click an institution to see its papers day by day. <a href="#udir"><b>Browse all universities ↓</b></a>',
                      tabs_html("researchboard-universities"))
    body += f'<div class="cat-grid"><section class="panel2">{panels}</section><aside>{side}</aside></div>'
    body += ('''<section class="panel2 udir" id="udir"><div class="ud-head"><div><h2>🏛️ All universities</h2>
<p class="note" id="udTotal">Every university with papers in OpenAlex · updated weekly</p></div>
<div class="ud-ctl"><select id="udCountry" aria-label="Country"><option>Loading…</option></select>
<input id="udSearch" type="search" placeholder="Search a university or city…" aria-label="Search universities"></div></div>
<p class="note" id="udInfo"></p>
<div class="ud-wrap"><table class="rt ud"><thead><tr><th>#</th><th data-k="name">University</th><th class="r" data-k="now" id="thNow">This year</th>
<th class="r" data-k="last" id="thLast">Last year</th><th class="r" data-k="pace" title="This year's pace compared with last year">Pace</th>
<th class="r hm" data-k="cites">Citations</th><th class="r hm" data-k="h">h-index</th><th class="r hm" data-k="oa" title="Share of recent papers free to read">Open access</th></tr></thead>
<tbody id="udBody"><tr><td colspan="8">Loading…</td></tr></tbody></table></div>
<button class="ud-more" id="udMore" hidden>Show more</button>
<p class="note">Click a column to sort. “Pace” compares this year so far (scaled to a full year) with last year. ⚠ marks a university where
OpenAlex shows a sudden jump, usually a bulk upload of old records; we rank it by a typical year. Data: OpenAlex.</p></section>
<script src="../assets/unidir.js" defer></script>''')
    write("universities", "Most active universities and research institutions today · ResearchBoard",
          f"Daily ranking of universities and research institutions by papers published. Latest: {nice(day)}.", body, "Universities")

    # ------------------------------------------------------------------ one university (loads live from OpenAlex)
    write("university", "University research output · ResearchBoard",
          "Research output of a university: papers per year, top research fields, researchers, partners and open access.",
          '<div id="uni"><p class="note">Loading…</p></div><script src="../assets/uni.js" defer></script>', "Universities")

    # ------------------------------------------------------------------ journals
    jnames = {}
    def jcounts(k):
        r = {}
        for x in days.get(k, {}).get("journals", []):
            r[x["id"]] = x["count"]; jnames[x["id"]] = x["name"]
        return r
    def jrows(pairs):
        return [{"n": n, "name": esc(jnames.get(i, i)), "v": f"<b>{v:,}</b>"} for n, (i, v) in enumerate(pairs[:40], 1)]
    jc = [("#", "n", False), ("Journal", "name", False), ("Papers", "v", True)]
    pj = period([day], jcounts)
    panels = (f'<div data-panel="d1">{ranked_table(jrows(pj), jc)}</div>'
              f'<div data-panel="d7" hidden>{ranked_table(jrows(period(keys[-7:], jcounts)), jc)}</div>'
              f'<div data-panel="d30" hidden>{ranked_table(jrows(period(keys[-30:], jcounts)), jc)}</div>')
    body = head_block("Journals", "Top journals by papers published",
                      f"Journal articles published each day, by journal · latest fully counted day: <b>{nice(day)}</b>.",
                      tabs_html("researchboard-journals"))
    body += (f'<div class="cat-grid"><section class="panel2">{panels}</section><aside><section class="panel2"><h2>Top 8 today</h2>'
             f'{hbars([(jnames.get(i, i), v) for i, v in pj[:8]])}<p class="note">Counts papers whose main location is a journal. '
             f'7- and 30-day views add up each day\'s top 15.</p></section></aside></div>')
    write("journals", "Top journals by papers published today · ResearchBoard",
          f"Which journals publish the most papers each day? Daily journal ranking, latest {nice(day)}.", body, "Journals")

    # ------------------------------------------------------------------ fields
    fnames = {}
    def fcounts(k):
        r = {}
        for x in days.get(k, {}).get("fields", []):
            r[x["id"]] = x["count"]; fnames[x["id"]] = x["name"]
        return r
    def frows(pairs):
        tot = sum(v for _, v in pairs) or 1
        return [{"n": n, "name": esc(fnames.get(i, i)), "v": f"<b>{v:,}</b>", "s": f"{v / tot * 100:.1f}%"} for n, (i, v) in enumerate(pairs, 1)]
    fc = [("#", "n", False), ("Field", "name", False), ("Papers", "v", True), ("Share", "s", True)]
    pf = period([day], fcounts)
    panels = (f'<div data-panel="d1">{ranked_table(frows(pf), fc)}</div>'
              f'<div data-panel="d7" hidden>{ranked_table(frows(period(keys[-7:], fcounts)), fc)}</div>'
              f'<div data-panel="d30" hidden>{ranked_table(frows(period(keys[-30:], fcounts)), fc)}</div>')
    body = head_block("Fields", "Research fields", f"Papers by main research field · latest fully counted day: <b>{nice(day)}</b>.",
                      tabs_html("researchboard-fields"))
    body += (f'<div class="cat-grid"><section class="panel2">{panels}</section><aside><section class="panel2"><h2>Biggest fields today</h2>'
             f'{hbars([(fnames.get(i, i), v) for i, v in pf[:10]])}<p class="note">Each paper counts once, under its main field (OpenAlex topics).</p>'
             f'</section></aside></div>')
    write("fields", "Research fields: papers published by field today · ResearchBoard",
          f"Daily papers by research field: medicine, engineering, computer science and more. Latest {nice(day)}.", body, "Research fields")

    # ------------------------------------------------------------------ papers
    def prow(p, n, key="citations", plus=False):
        url = p.get("doi") or f"https://openalex.org/{p.get('id')}"
        return {"n": n, "name": f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(p.get("title", ""))}</a>',
                "j": esc(p.get("venue") or "—"), "y": esc(str(p.get("year") or "")),
                "v": f'<b class="{"up" if plus else ""}">{"+" if plus else ""}{f(p.get(key))}</b>'}
    pc = [("#", "n", False), ("Paper", "name", False), ("Journal", "j", False), ("Year", "y", False), ("Citations", "v", True)]
    gains = latest.get("paper_gainers") or []
    body = head_block("Papers", "Most-cited papers", "The most-cited new papers of the last two years, today's biggest citation gains, "
                      "and the most-cited papers of all time.")
    body += (f'<section class="panel2"><h2>📄 Most-cited new papers <span class="muted small">· last 2 years</span></h2>'
             f'{ranked_table([prow(p, n) for n, p in enumerate(latest.get("hot_papers") or [], 1)], pc)}</section>')
    if gains:
        gc = [("#", "n", False), ("Paper", "name", False), ("Journal", "j", False), ("Year", "y", False), ("Gained", "v", True)]
        body += (f'<section class="panel2"><h2>🚀 Biggest citation gains <span class="muted small">· since the previous day</span></h2>'
                 f'{ranked_table([prow(p, n, "gain", True) for n, p in enumerate(gains[:20], 1)], gc)}</section>')
    body += (f'<section class="panel2"><h2>🏆 Most-cited papers of all time</h2>'
             f'{ranked_table([prow(p, n) for n, p in enumerate(latest.get("top_papers") or [], 1)], pc)}</section>')
    write("papers", "Most-cited papers: new, rising and all-time · ResearchBoard",
          "The most-cited research papers of the last two years, daily citation gains and all-time most-cited papers.", body, "")

    # ------------------------------------------------------------------ scientists
    def arow(a, n, key="citations", plus=False):
        return {"n": n, "name": esc(a.get("name", "")), "i": esc(a.get("institution") or "—"),
                "cc": f'{flag(a.get("country"))}{esc(a.get("country") or "")}',
                "v": f'<b class="{"up" if plus else ""}">{"+" if plus else ""}{f(a.get(key))}</b>'}
    ac = [("#", "n", False), ("Scientist", "name", False), ("Institution", "i", False), ("Country", "cc", False), ("Citations", "v", True)]
    body = head_block("Scientists", "Find scientists", "Search active researchers worldwide by name, research topic, country, "
                      "field or university — or find a supervisor for your research interest.")
    body += '<div id="sci"><p class="note">Loading…</p></div><script src="../assets/sci.js" defer></script>'
    body += '<h2 class="mv-h">Citation leaders</h2>'
    g = latest.get("gainers") or []
    if g:
        gc = [("#", "n", False), ("Scientist", "name", False), ("Institution", "i", False), ("Country", "cc", False), ("Gained", "v", True)]
        body += (f'<section class="panel2"><h2>🚀 Gaining citations <span class="muted small">· since the previous day</span></h2>'
                 f'{ranked_table([arow(a, n, "gain", True) for n, a in enumerate(g[:20], 1)], gc)}</section>')
    body += (f'<section class="panel2"><h2>🏆 Most-cited scientists of all time</h2>'
             f'{ranked_table([arow(a, n) for n, a in enumerate(latest.get("top_authors") or [], 1)], ac)}'
             f'<p class="note">Among the 200 most-cited scientists in OpenAlex; daily gains compare today\'s totals with the previous day\'s.</p></section>')
    write("scientists", "Find scientists by name, topic, country, field or university · ResearchBoard",
          "Search active researchers worldwide by name, research topic, country, field or university, and find a supervisor. "
          "Plus the scientists gaining the most citations today.", body, "Scientists")
    write("scientist", "Scientist research profile · ResearchBoard",
          "A scientist's papers per year, citations, h-index, research topics, co-authors and latest papers.",
          '<div id="person"><p class="note">Loading…</p></div><script src="../assets/scientist.js" defer></script>', "Scientists")

    # ------------------------------------------------------------------ market = weekly movers
    import movers as _mv
    mv = _mv.compute(hist, latest, inst)
    (out / "data").mkdir(exist_ok=True)
    (out / "data" / "movers.json").write_text(json.dumps(mv or {}, ensure_ascii=False), encoding="utf-8")
    m = latest.get("market")
    body = head_block("Trends", "Research trends · Weekly pulse", "Which countries, research fields and universities are gaining or "
                      "losing share of the world's new papers this week, compared with last week.")
    if mv:
        wk = lambda w: f"{dt.date.fromisoformat(w[0]):%b} {dt.date.fromisoformat(w[0]).day}–{dt.date.fromisoformat(w[1]):%b} {dt.date.fromisoformat(w[1]).day}"
        pct = lambda x: (f'<b class="up">▲ +{x:.1f}%</b>' if x > 0 else f'<b class="down">▼ −{abs(x):.1f}%</b>')
        w = mv["world"]
        cu, fu = (mv["countries"]["up"] or [{}])[0], (mv["fields"]["up"] or [{}])[0]
        body += (f'<div class="xstats"><div><span>Papers this week</span><b>{f(w["now"])}</b></div>'
                 f'<div><span>vs last week</span>{pct(w["pct"])}</div>'
                 f'<div><span>Fastest-rising country</span><b style="font-size:16px">{flag(cu.get("id"))} {esc(cu.get("name", "—"))}</b></div>'
                 f'<div><span>Fastest-rising field</span><b style="font-size:16px">{esc(fu.get("name", "—"))}</b></div></div>'
                 f'<p class="note">This week: {wk(mv["week"])} · last week: {wk(mv["prev_week"])} · fully counted days only.</p>')
        daily = mv["daily"]
        body += (f'<section class="panel2 mv-chart"><h2>Papers per day, last two weeks</h2>{vbars([x[1] for x in daily], [nice(x[0]) for x in daily])}'
                 '<p class="note">Weekends are always lower: many journals publish on weekdays.</p></section>')

        def mtable(rows, kind):
            def nm(r):
                if kind == "countries":
                    return f'{flag(r["id"])}<a href="../country/{slugify(r["name"])}.html">{esc(r["name"])}</a>'
                if kind == "universities":
                    return f'<a href="../explore/?id={esc(r["id"])}">{esc(r["name"])}</a>'
                return esc(r["name"])
            return ranked_table([{"n": n, "name": nm(r), "v": f(r["now"]), "c": pct(r["pct"])} for n, r in enumerate(rows, 1)],
                                [("#", "n", False), ({"countries": "Country", "fields": "Field", "universities": "University"}[kind], "name", False),
                                 ("Papers this week", "v", True), ("Share change", "c", True)])
        for kind, title, n in (("countries", "Countries", 10), ("fields", "Research fields", 8), ("universities", "Universities", 10)):
            up, down = mv[kind]["up"][:n], mv[kind]["down"][:n]
            body += (f'<h2 class="mv-h">{title}</h2><div class="cat-grid mv"><section class="panel2"><h2>▲ Rising</h2>{mtable(up, kind)}</section>'
                     f'<section class="panel2"><h2>▼ Falling</h2>{mtable(down, kind)}</section></div>')
        body += ('<section class="panel2"><h2>How to read this</h2><p>We add up each country\'s, field\'s and university\'s papers over the '
                 'last 7 fully counted days and compare their <b>share of world papers</b> with the 7 days before. Ranking by share means '
                 'a quiet week for everyone does not look like a fall for everyone. Small producers are left out so a handful of papers '
                 'cannot swing the list. Sudden large jumps are often a batch of journals being added to OpenAlex at once. '
                 '<a href="../about/methods.html">Methods</a></p></section>')
    else:
        body += '<section class="panel2"><p>Weekly trends appear once we have two full weeks of data.</p></section>'
    if m and not m.get("flagged"):
        t1 = dt.datetime.fromisoformat(m["to"])
        body += (f'<section class="panel2"><h2>Last 24 hours</h2><p>OpenAlex added <b>{f(m["papers_added"])}</b> papers to the '
                 f'global record in the 24 hours to {t1:%b} {t1.day}, {t1:%H:%M} UTC, from {f(m.get("countries_active"))} countries.</p></section>')
    write("market", "Research trends · Weekly pulse: rising and falling countries, fields and universities · ResearchBoard",
          "This week's research movers: which countries, research fields and universities are gaining or losing share of the world's new papers.",
          body, "Trends")

    # ------------------------------------------------------------------ explore (search result page)
    body = '''<div class="crumb"><a href="../">Home</a> › Search</div>
<div id="xbox"><p class="note">Loading…</p></div>
<script>
document.addEventListener("DOMContentLoaded", async () => {
  const q = new URLSearchParams(location.search), id = q.get("id"), cc = q.get("c");
  const box = document.getElementById("xbox");
  const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString("en-US"));
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  const I = await window.RBSearchIndex();
  const rows = cc ? I.countries : I.inst, key = cc || id;
  const r = rows.find((x) => x[0] === key);
  if (!r) { box.innerHTML = '<section class="panel2"><h2>Not found</h2><p>This institution is not in our recent daily top-200 lists. Try the search box above.</p></section>'; return; }
  if (cc) { location.replace("../country/" + r[2] + ".html"); return; }
  const dates = I.dates, ser = r.slice(3), last = dates.length - 1;
  const rankOn = (j) => { const v = ser[j]; if (!v) return null; let k = 1; I.inst.forEach((x) => { if ((x[3 + j] || 0) > v) k++; }); return k; };
  let lastIdx = last; while (lastIdx > 0 && ser[lastIdx] == null) lastIdx--;
  const sum = (n) => ser.slice(-n).reduce((a, b) => a + (b || 0), 0);
  const nice = (d) => new Date(d + "T00:00:00Z").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" });
  const flagH = r[2] ? `<span class="fi fi-${r[2].toLowerCase()}" style="font-size:24px;border-radius:3px"></span>` : "";
  let range = 30;
  function chart() {
    const v = ser.slice(-range).map((x) => x || 0), d = dates.slice(-range), W = 680, H = 170, g = 3, bw = (W - g * (v.length - 1)) / v.length, mx = Math.max(1, ...v);
    return `<svg class="vbars" viewBox="0 0 ${W} ${H}">` + v.map((x, i) => `<rect${i === v.length - 1 ? ' class="last"' : ""} x="${(i * (bw + g)).toFixed(1)}" y="${(H - Math.max(2, x / mx * (H - 10))).toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(2, x / mx * (H - 10)).toFixed(1)}" rx="2"><title>${d[i]}: ${fmt(x)} papers</title></rect>`).join("") + "</svg>";
  }
  function draw() {
    const table = dates.map((d, j) => [d, ser[j], j]).filter((x) => x[1] != null).reverse().slice(0, 30)
      .map((x) => `<tr><td>${nice(x[0])}</td><td class="r"><b>${fmt(x[1])}</b></td><td class="r">#${rankOn(x[2]) || "—"}</td></tr>`).join("");
    box.innerHTML = `<div class="cat-head"><div><h1>${flagH} ${esc(r[1])}</h1><p>Institution${r[2] ? " · " + esc(r[2]) : ""} · papers with at least one author from this institution, per day</p></div>
      <div class="tabs" data-x><button data-r="7"${range===7?' class="on"':""}>7 days</button><button data-r="30"${range===30?' class="on"':""}>30 days</button><button data-r="60"${range===60?' class="on"':""}>60 days</button></div></div>
      <div class="cat-grid"><section class="panel2"><div class="xstats"><div><span>Papers on ${nice(dates[lastIdx])}</span><b>${fmt(ser[lastIdx])}</b></div>
      <div><span>Rank that day</span><b>#${rankOn(lastIdx) || "—"}</b></div><div><span>Last 7 days</span><b>${fmt(sum(7))}</b></div><div><span>Last 30 days</span><b>${fmt(sum(30))}</b></div></div>
      ${chart()}<p class="note">Counted on days when the institution was among the 200 most active worldwide; other days show no bar.</p></section>
      <aside><section class="panel2"><h2>Papers per day</h2><table class="rt"><thead><tr><th>Date</th><th class="r">Papers</th><th class="r">Rank</th></tr></thead><tbody>${table}</tbody></table></section></aside></div>`;
    box.querySelectorAll("[data-r]").forEach((b) => b.addEventListener("click", () => { range = +b.dataset.r; draw(); }));
    document.title = r[1] + " — papers per day · ResearchBoard";
  }
  draw();
});
</script>'''
    d = out / "explore"
    d.mkdir(exist_ok=True)
    (d / "index.html").write_text(page("Search · ResearchBoard", "Papers per day for any country or institution.",
                                       f'<div class="page">{body}</div>', f"{site_url}/explore/", extra_head=FLAGS + '<meta name="robots" content="noindex">',
                                       active="", main_class="cat-main"), encoding="utf-8")

    # ------------------------------------------------------------------ search index
    dates = sorted(set(keys[-60:]) | {k for k in inst.get("days", {}) if k <= day})[-60:]
    crow = []
    codes = set()
    for k in dates:
        c = days.get(k, {}).get("countries") or {}
        if isinstance(c, dict):
            codes.update(c)
    for code in codes:
        nm = names.get(code, code)
        crow.append([code, nm, slugify(nm)] + [(days.get(k, {}).get("countries") or {}).get(code) for k in dates])
    irow = []
    ids = set()
    for k in dates:
        ids.update(inst_counts(k))
    for i in ids:
        irow.append([i, inames.get(i, i), ic.get(i)] + [inst_counts(k).get(i) for k in dates])
    (out_blog / "_search-index.json").write_text(
        json.dumps({"dates": dates, "countries": crow, "inst": irow}, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"Site pages: 7 category pages; search index {len(crow)} countries, {len(irow)} institutions, {len(dates)} days")
    # ------------------------------------------------------------------ about
    about = head_block("About", "About ResearchBoard", "A free daily board of the world's research output — "
                       "how much is published, where, by whom, and what is being cited.")
    about += """
<div class="about">
<section class="panel2"><h2>What ResearchBoard is</h2>
<p>ResearchBoard follows global science the way a stock-market board follows prices. Every day it counts the research papers published worldwide and shows them by
country, university, journal and field, together with citations and the most-cited papers and scientists. It is free, has no adverts, and is built entirely on open data.</p>
<p>It is made for researchers, students, librarians, journalists, universities and anyone curious about where science happens.</p></section>

<section class="panel2"><h2>Where the numbers come from</h2>
<ul>
<li><b><a href="https://openalex.org" rel="noopener">OpenAlex</a></b> — a free, open catalogue of the world's research (papers, authors, institutions, journals and topics), run by the non-profit OurResearch. Papers, countries, institutions, journals, fields and citations come from OpenAlex.</li>
<li><b><a href="https://pubmed.ncbi.nlm.nih.gov" rel="noopener">PubMed</a></b> — the database of medical and life-science literature run by the US National Library of Medicine. We count the records added to PubMed each day (by entry date).</li>
</ul>
<p>Both sources are public. We collect from them automatically once a day; nothing is typed in by hand.</p></section>

<section class="panel2"><h2>What we count</h2>
<ul>
<li><b>Papers:</b> journal articles, reviews, preprints, letters, conference papers and book chapters, by their <b>publication date</b>. Datasets, errata, peer reviews and similar records are left out.</li>
<li><b>Countries and institutions:</b> a paper counts for a country or university when at least one of its authors works there. A paper by an international team therefore counts for every country involved, so country totals add up to more than the world total.</li>
<li><b>Fields:</b> each paper is counted once, under its main field (OpenAlex topics).</li>
<li><b>Citations made:</b> the number of references listed in the day's new papers — how many times new research cited earlier work.</li>
<li><b>Most-cited papers and scientists:</b> total citations in OpenAlex; daily gains compare today's totals with the previous day's.</li>
</ul></section>

<section class="panel2"><h2>Why the daily report is about 3 days behind</h2>
<p>Journals and databases keep reporting papers for several days after they are published, so a day's count keeps rising for a while. To avoid showing half-finished numbers,
each <b>Research Report</b> covers the newest day that is <b>fully counted</b> — usually about three days ago. A day counts as complete once it has reached the level that
the same weekday normally reaches. Weekends always have fewer papers than weekdays.</p>
<p>For what happened in the last day, see <a href="../market/">Research trends</a>: it compares the running total of recent papers between two updates about 24 hours apart.
If the source database has not been refreshed, or makes an unusually large correction, that day's change is not shown rather than shown wrongly.</p></section>

<section class="panel2"><h2>What we publish</h2>
<ul>
<li><b>Daily Research Report</b> — papers, PubMed records, citations and top countries for the latest fully counted day (website and social media).</li>
<li><b>Research trends</b> — papers added to the global record in the last 24 hours.</li>
<li><b>Spotlights</b> — themed top-10 rankings: countries, universities, journals, fields, rising countries, papers and scientists.</li>
<li><b>Country and university pages</b>, the <a href="../map/">world research map</a> and site search — papers per day for 200+ countries and hundreds of universities and institutes.</li>
<li><b>Bangladesh daily update</b> on Facebook — the last 24 hours of Bangladeshi research.</li>
<li><b><a href="../blog/">Blog</a></b> — data guides that update every day, and practical guides for researchers and students.</li>
</ul></section>

<section class="panel2"><h2>Full methods</h2><p>Exact definitions, rules, whole and fractional counting, limitations and a change log are on the <a href="methods.html"><b>Methods page</b></a>.</p></section>

<section class="panel2"><h2>Limits to keep in mind</h2>
<ul>
<li>Numbers can change slightly after publication as late records arrive or the source data is corrected.</li>
<li>Matching authors to institutions and countries is automatic and can occasionally be wrong; some papers have no affiliation at all.</li>
<li>Papers known only by their month or year are dated the 1st, so the first day of a month can look unusually large.</li>
<li>Counting papers says nothing about their quality. Use these numbers to see where research happens, not to judge individual work.</li>
</ul></section>

<section class="panel2"><h2>Use and cite the data</h2>
<p>You are welcome to use ResearchBoard's numbers and charts. Please credit <b>ResearchBoard (researchboard.net), data from OpenAlex and PubMed</b>.
Daily totals and country data can be downloaded as CSV from the <a href="../">homepage</a>. OpenAlex data is released under CC0.</p></section>

<section class="panel2"><h2>Contact and follow</h2>
<p>Questions, corrections, ideas or data requests are welcome. Use the email and social links below — we read everything.</p></section>
</div>"""
    write("about", "About ResearchBoard: data sources, methods and what we publish",
          "How ResearchBoard counts the world's research every day: data from OpenAlex and PubMed, what counts as a paper, why reports are fully counted, and how to cite.",
          about, "About")

    # ------------------------------------------------------------------ methods (detailed)
    m_body = head_block("Methods", "Methods: how ResearchBoard counts research",
                        "Exact definitions, sources and rules behind every number on ResearchBoard. "
                        "The code that collects the data is public on <a href=\"https://github.com/Researchboard/researchboard.github.io\" rel=\"noopener\">GitHub</a>.")
    m_body += """
<div class="about">
<section class="panel2"><h2>1. Sources</h2>
<ul>
<li><b>OpenAlex</b> (<a href="https://openalex.org" rel="noopener">openalex.org</a>, CC0 licence) — all counts of papers, countries, institutions, journals, fields and citations, through its public API.</li>
<li><b>PubMed</b> (US National Library of Medicine, via the NCBI E-utilities API) — records added to PubMed per day, by <i>entry date</i>.</li>
</ul>
<p>Data is collected automatically once a day at about 13:07 UTC. Each run re-checks the last 7 days, because counts for recent days keep growing.</p></section>

<section class="panel2"><h2>2. What counts as a paper</h2>
<p>Works of type <b>article, review, preprint, letter, conference paper or book chapter</b>, by <b>publication date</b>. Other record types
(datasets, errata, editorials, peer reviews, etc.) are excluded; on some days a single repository adds tens of thousands of dataset records, which would distort the totals.
Papers known only by their month or year are dated the 1st by the source, so the 1st of a month can show a spike.</p></section>

<section class="panel2"><h2>3. Countries and institutions</h2>
<ul>
<li><b>Whole counting (default):</b> a paper counts once for every country (or institution) of its authors' affiliations. A paper by authors in Bangladesh and Japan counts 1 for each. This answers "how many papers did researchers in this country take part in?". Because of international co-authorship, country totals add up to more than the world total.</li>
<li><b>Fractional counting:</b> a paper with authors from <i>k</i> different countries adds <b>1/<i>k</i></b> to each of them (2 countries: ½ each; 3 countries: ⅓ each). Country fractional counts add up to the number of papers with a known country, so nothing is counted twice. We calculate it for the 30 most active countries each day (plus Bangladesh), from OpenAlex's count of distinct countries per paper. Shown on country pages and in the country ranking from October 28, 2026.</li>
<li><b>Institutions</b> are OpenAlex institutions, including their parent organisations: a paper from an institute that belongs to a larger organisation (for example a national academy of sciences) also counts for the parent. We list the day's top institutions and keep the 200 most active per day for search.</li>
<li>Country and institution are taken from the authors' affiliations as matched by OpenAlex. Papers with no affiliation information cannot be assigned to a country.</li>
</ul></section>

<section class="panel2"><h2>4. Journals, fields and citations</h2>
<ul>
<li><b>Journals:</b> papers whose main location is a journal, grouped by that journal (top 15 per day).</li>
<li><b>Fields:</b> each paper counted once, under the field of its primary topic (OpenAlex topic classification, 26 fields).</li>
<li><b>Citations made:</b> the sum of the reference counts of the day's papers — how many times the day's new research cited earlier work.</li>
<li><b>Most-cited papers:</b> all-time leaders, and the most-cited papers published in the last two years, by total citations in OpenAlex.</li>
<li><b>Most-cited scientists:</b> the 200 authors with the most citations in OpenAlex. <b>Daily gains</b> compare each paper's or author's citation total with the previous day's snapshot.</li>
<li><b>Active institutions:</b> the number of distinct institutions with at least one paper that day.</li>
</ul></section>

<section class="panel2"><h2>5. When a day is "fully counted"</h2>
<p>A day is treated as complete when its paper count has reached at least <b>40% of the usual count for the same weekday</b>
(the median of the same weekday in the previous five weeks, using only days that are at least a week old). The daily Research Report moves forward
one complete day per run, so it is usually about three days behind. Weekends are naturally lower than weekdays.</p></section>

<section class="panel2"><h2>6. Research trends (last 24 hours)</h2>
<p>Each run records the running total of papers published this year and last year — overall, by country and by institution. Research trends shows the
<b>difference between two runs 12 to 36 hours apart</b>, i.e. what was added to the database in between, labelled with the actual time window.
The change is <b>not shown</b> when nothing was added (the source has not refreshed yet) or when the change is more than 4 times or less than a quarter of the usual
daily change (a sign of a bulk import or a database clean-up). The Bangladesh daily update uses the same method for Bangladeshi papers and institutions.</p></section>

<section class="panel2"><h2>7. Known limitations</h2>
<ul>
<li>Counts can change after publication as late records arrive or the source corrects its data.</li>
<li>Automatic affiliation matching can be wrong or missing, especially for small institutions and some regions.</li>
<li>Author name disambiguation is automatic: a few author totals may merge or split different people.</li>
<li>Paper counts measure volume, not quality or impact.</li>
<li>Coverage follows OpenAlex; some journals, languages and regions are better covered than others.</li>
</ul></section>

<section class="panel2"><h2>8. Related resources</h2>
<p>Other open or widely used views of research output, with different aims and update cycles:</p>
<ul>
<li><a href="https://www.leidenranking.com" rel="noopener">CWTS Leiden Ranking Open Edition</a> — yearly, transparent university indicators built on OpenAlex.</li>
<li><a href="https://openknowledge.community/dashboards/coki-open-access-dashboard/" rel="noopener">COKI Open Access Dashboard</a> — open-access status by country and institution.</li>
<li><a href="https://www.scimagojr.com" rel="noopener">SCImago Journal &amp; Country Rank</a> — yearly journal and country indicators (Scopus data).</li>
<li><a href="https://www.nature.com/nature-index" rel="noopener">Nature Index</a> — output in a selected group of high-quality journals, with fractional counting.</li>
<li><a href="https://www.crossref.org" rel="noopener">Crossref</a> and <a href="https://datacite.org" rel="noopener">DataCite</a> — DOI registries for papers and for data and software.</li>
</ul>
<p>ResearchBoard differs by being <b>daily</b>, counting <b>all</b> published research, and being written for a general audience.</p></section>

<section class="panel2"><h2>9. Change log</h2>
<ul>
<li><b>Oct 28, 2026</b> — fractional counting for the top countries; this Methods page.</li>
<li><b>Oct 27, 2026</b> — daily reports renamed "Research Report — fully counted"; Research trends; world research map; top-200 institutions per day; Bangladesh daily update; data guides.</li>
<li><b>Oct 26, 2026</b> — 24-hour change ("Research trends") added; reports move forward one complete day per run.</li>
</ul></section>

<section class="panel2"><h2>10. Cite and reuse</h2>
<p>Please cite as: <i>ResearchBoard (researchboard.net). Daily global research statistics, data from OpenAlex and PubMed. Accessed [date].</i>
Corrections and questions are welcome by email.</p></section>
</div>"""
    md = out / "about"
    md.mkdir(exist_ok=True)
    (md / "methods.html").write_text(page("Methods: how ResearchBoard counts research · ResearchBoard",
        "Exact definitions behind ResearchBoard: sources, what counts as a paper, whole and fractional counting, fully counted days, the 24-hour trend, limitations and change log.",
        f'<div class="page">{m_body}</div>', f"{site_url}/about/methods.html", extra_head=FLAGS, active="About", main_class="cat-main"),
        encoding="utf-8")
    urls.append((f"{site_url}/about/methods.html", day, "weekly", "0.6"))

    return urls
