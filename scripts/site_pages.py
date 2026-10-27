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
                      f"Click an institution to see its papers day by day.", tabs_html("researchboard-universities"))
    body += f'<div class="cat-grid"><section class="panel2">{panels}</section><aside>{side}</aside></div>'
    write("universities", "Most active universities and research institutions today · ResearchBoard",
          f"Daily ranking of universities and research institutions by papers published. Latest: {nice(day)}.", body, "Universities")

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
          f"Daily papers by research field: medicine, engineering, computer science and more. Latest {nice(day)}.", body, "Fields")

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
    body = head_block("Scientists", "Scientists", "Scientists gaining the most citations since the previous day, and the most-cited scientists of all time.")
    g = latest.get("gainers") or []
    if g:
        gc = [("#", "n", False), ("Scientist", "name", False), ("Institution", "i", False), ("Country", "cc", False), ("Gained", "v", True)]
        body += (f'<section class="panel2"><h2>🚀 Gaining citations <span class="muted small">· since the previous day</span></h2>'
                 f'{ranked_table([arow(a, n, "gain", True) for n, a in enumerate(g[:20], 1)], gc)}</section>')
    body += (f'<section class="panel2"><h2>🏆 Most-cited scientists of all time</h2>'
             f'{ranked_table([arow(a, n) for n, a in enumerate(latest.get("top_authors") or [], 1)], ac)}'
             f'<p class="note">Among the 200 most-cited scientists in OpenAlex; daily gains compare today\'s totals with the previous day\'s.</p></section>')
    write("scientists", "Most-cited scientists and daily citation gains · ResearchBoard",
          "Which scientists gained the most citations today? Plus the most-cited scientists of all time.", body, "")

    # ------------------------------------------------------------------ market
    hist_m = [m for m in hist.get("market", []) if not m.get("flagged")]
    m = latest.get("market")
    body = head_block("Market", "Research Market", "What was added to the global research record in the last 24 hours, "
                      "like a share-price change, and how it has moved day by day.")
    if m and not m.get("flagged"):
        t1 = dt.datetime.fromisoformat(m["to"])
        body += (f'<div class="xstats"><div><span>New papers added</span><b class="up">▲ +{f(m["papers_added"])}</b></div>'
                 f'<div><span>PubMed records</span><b>+{f(m.get("pubmed_yesterday"))}</b></div>'
                 f'<div><span>Countries contributing</span><b>{f(m.get("countries_active"))}</b></div>'
                 f'<div><span>Window ends</span><b style="font-size:16px">{t1:%b} {t1.day}, {t1:%H:%M} UTC</b></div></div>')
        mc = [("#", "n", False), ("Country", "name", False), ("Added", "v", True)]
        mi = [("#", "n", False), ("Institution", "name", False), ("Added", "v", True)]
        body += ('<div class="cat-grid"><section class="panel2"><h2>Top countries, last 24 hours</h2>' +
                 ranked_table([{"n": n, "name": flag(c["code"]) + esc(names.get(c["code"], c["code"])), "v": f'<b class="up">▲ +{c["added"]:,}</b>'}
                               for n, c in enumerate(m.get("countries", []), 1)], mc) +
                 '</section><aside><section class="panel2"><h2>Top institutions, last 24 hours</h2>' +
                 ranked_table([{"n": n, "name": esc(i["name"]), "v": f'<b class="up">▲ +{i["added"]:,}</b>'}
                               for n, i in enumerate(m.get("institutions", []), 1)], mi) + '</section></aside></div>')
    else:
        body += '<section class="panel2"><p>The first 24-hour comparison appears after the next daily update.</p></section>'
    if hist_m:
        labels = [dt.datetime.fromisoformat(x["to"]).date().isoformat() for x in hist_m[-60:]]
        body += (f'<section class="panel2"><h2>New papers added per day</h2>{vbars([x["papers_added"] for x in hist_m[-60:]], labels)}'
                 + ranked_table([{"d": esc(nice(dt.datetime.fromisoformat(x["to"]).date().isoformat())), "v": f'<b>+{x["papers_added"]:,}</b>',
                                  "p": f(x.get("pubmed_yesterday")), "c": f(x.get("countries_active")),
                                  "t": (flag((x.get("countries") or [{}])[0].get("code")) + esc(names.get((x.get("countries") or [{}])[0].get("code", ""), "")))}
                                 for x in reversed(hist_m[-30:])],
                                [("Day", "d", False), ("Papers added", "v", True), ("PubMed", "p", True), ("Countries", "c", True), ("Top mover", "t", False)])
                 + '</section>')
    write("market", "Research Market: papers added in the last 24 hours · ResearchBoard",
          "How much research was added to the global record in the last 24 hours, by country and institution.", body, "Market")

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
    return urls
