#!/usr/bin/env python3
"""
ResearchBoard blog builder.

  python scripts/build_blog.py            build the blog from posts/
  python scripts/build_blog.py --daily    also write today's automatic
                                          "Today in Research" post from data/

Posts are Markdown files in posts/ (your own articles) and posts/daily/
(automatic reports). Each starts with a small header:

    ---
    title: My first post
    date: 2026-10-26
    author: Your Name
    summary: One sentence shown on the blog page.
    tags: analysis, PubMed
    image: images/my-picture.png      (optional; put the file in posts/images/)
    ---

    Then write the post in Markdown...

Output goes to blog/: index.html, one page per post, feed.xml (RSS) and
posts.json (used by the homepage). Needs the "markdown" package.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
import shutil
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "posts"
DAILY = POSTS / "daily"
OUT = ROOT / "blog"
DATA = ROOT / "data"
import os
SITE_URL = (os.environ.get("SITE_URL", "").strip().rstrip("/") or "https://researchboard.net")
SITE_NAME = "ResearchBoard"
TAGLINE = "Every Paper. Every Citation. Every Discovery."

esc = html.escape


# --------------------------------------------------------------------------- reading posts

def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:80] or "post"


def parse(path: Path, kind: str) -> dict | None:
    raw = path.read_text(encoding="utf-8").lstrip("﻿")
    meta, body = {}, raw
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip().strip('"').strip("'")
        body = m.group(2)
    if meta.get("draft", "").lower() in ("true", "yes", "1"):
        return None
    title = meta.get("title") or path.stem.replace("-", " ").title()
    try:
        date = dt.date.fromisoformat(meta.get("date", "")[:10])
    except ValueError:
        date = dt.date.fromtimestamp(path.stat().st_mtime)
    html_body = markdown.markdown(body, extensions=["tables", "fenced_code", "sane_lists", "toc"])
    # images written as images/x.png are served from blog/images/
    html_body = re.sub(r'src="(?:\.\./)?(?:posts/)?images/', 'src="images/', html_body)
    text = re.sub(r"<[^>]+>", " ", html_body)
    words = len(text.split())
    summary = meta.get("summary") or (" ".join(text.split()[:32]) + ("…" if words > 32 else ""))
    tags = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
    slug = meta.get("slug") or (f"daily-{date.isoformat()}" if kind == "daily" else slugify(title))
    image = meta.get("image", "")
    image = re.sub(r"^(?:\.\./)?(?:posts/)?", "", image) if image else ""
    social = image
    if kind == "daily" and (POSTS / "images" / "cards" / f"daily-{date.isoformat()}.png").exists():
        social = f"images/cards/daily-{date.isoformat()}.png"
    return {"title": title, "date": date, "author": meta.get("author") or SITE_NAME, "summary": summary,
            "tags": tags, "kind": kind, "slug": slug, "html": html_body, "minutes": max(1, round(words / 220)),
            "image": image, "social": social}


def load_posts() -> list[dict]:
    posts = []
    for p in sorted(POSTS.glob("*.md")):
        if p.name.lower() in ("readme.md", "_template.md"):
            continue
        r = parse(p, "article")
        if r:
            posts.append(r)
    guides = POSTS / "guides"
    for p in sorted(guides.glob("*.md")) if guides.exists() else []:
        r = parse(p, "guide")
        if r:
            posts.append(r)
    for p in sorted(DAILY.glob("*.md")) if DAILY.exists() else []:
        r = parse(p, "daily")
        if r:
            posts.append(r)
    seen = set()
    for p in posts:  # make slugs unique
        base, n = p["slug"], 2
        while p["slug"] in seen:
            p["slug"] = f"{base}-{n}"; n += 1
        seen.add(p["slug"])
    posts.sort(key=lambda p: (p["date"], p["kind"] == "article"), reverse=True)
    return posts


# --------------------------------------------------------------------------- page template

LOGO = "../assets/logo.svg"


NAV = [("Map", "../map/"), ("Countries", "../country/"), ("Universities", "../universities/"), ("Scientists", "../scientists/"), ("Study Abroad", "../study/"),
       ("Trends", "../market/"), ("Blog", "../blog/"), ("About", "../about/")]
NAV_LABEL = {"Map": "Research Map"}
# "Research Trends" dropdown: (active name, label, link, icon, one-line description)
TRENDS_MENU = [("Trends", "Weekly pulse", "../market/", "📈", "What is rising and falling this week"),
               ("Research fields", "Research fields", "../fields/", "🧪", "Papers and growth by research field"),
               ("Journals", "Journals", "../journals/", "📚", "The most active journals today")]
NAV_JS = """<script>(function(){document.querySelectorAll('.topnav .nd').forEach(function(n){var b=n.querySelector('.nd-top'),d=n.querySelector('.dd'),t;
function place(){var r=b.getBoundingClientRect(),w=Math.min(320,innerWidth-24);d.style.width=w+'px';d.style.top=(r.bottom+8)+'px';d.style.left=Math.max(12,Math.min(r.left,innerWidth-w-12))+'px';}
function open(){place();n.classList.add('open');b.setAttribute('aria-expanded','true');}
function close(){n.classList.remove('open');b.setAttribute('aria-expanded','false');}
b.addEventListener('click',function(e){if(!n.classList.contains('open')){e.preventDefault();open();}});
if(window.matchMedia&&matchMedia('(hover:hover)').matches){n.addEventListener('mouseenter',function(){clearTimeout(t);open();});n.addEventListener('mouseleave',function(){t=setTimeout(close,200);});}
document.addEventListener('click',function(e){if(!n.contains(e.target))close();});
document.addEventListener('keydown',function(e){if(e.key==='Escape')close();});
addEventListener('scroll',close,{passive:true});addEventListener('resize',close);});})();</script>"""


def nav_html(active: str = "", prefix: str = "../") -> str:
    """Top menu: plain links plus the "Research Trends" dropdown (Weekly pulse, Research fields, Journals)."""
    HL, ON = ' class="hl"', ' class="on"'
    fix = lambda h: prefix + h[3:] if h.startswith("../") else h
    out = []
    for n, h in NAV:
        if n == "Trends":
            group_on = active in {x[0] for x in TRENDS_MENU}
            items = "".join(f'<a href="{fix(link)}"{HL if a == active else ""}><span class="ic">{ic}</span>'
                            f'<span><b>{label}</b><small>{d}</small></span></a>' for a, label, link, ic, d in TRENDS_MENU)
            out.append(f'<div class="nd{" on" if group_on else ""}"><a href="{fix(h)}" class="nd-top{" on" if group_on else ""}" aria-haspopup="true" '
                       f'aria-expanded="false">Research Trends <span class="car" aria-hidden="true">▾</span></a><div class="dd">{items}</div></div>')
        else:
            out.append(f'<a href="{fix(h)}"{ON if n == active else ""}>{NAV_LABEL.get(n, n)}</a>')
    return "\n      ".join(out)


def page(title: str, description: str, body: str, canonical: str, extra_head: str = "", image: str = "",
         active: str = "Blog", main_class: str = "blog-main") -> str:
    image = image or f"{SITE_URL}/assets/og-card.png"
    nav = nav_html(active)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:type" content="article">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="{esc(image)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{LOGO}" type="image/svg+xml">
<link rel="alternate" type="application/rss+xml" title="{SITE_NAME} blog" href="feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../assets/style.css">
<link rel="stylesheet" href="../assets/blog.css">
<link rel="stylesheet" href="../assets/v2.css">
{extra_head}
<script>try{{var t=localStorage.getItem("researchboard-theme");if(t)document.documentElement.setAttribute("data-theme",t)}}catch(e){{}}</script>
<script data-goatcounter="https://researchboard.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
</head>
<body data-root="../">
<header class="topbar">
  <div class="topbar-inner">
    <a class="brand" href="../" aria-label="{SITE_NAME} home">
      <img src="{LOGO}" alt="" width="54" height="54">
      <span class="brand-text"><span class="brand-name">Research<span class="b2">Board</span></span><span class="brand-tag">{TAGLINE}</span></span>
    </a>
    <nav class="topnav" aria-label="Sections">
      {nav}
    </nav>{NAV_JS}
    <div class="gsearch" role="search">
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
      <input type="search" placeholder="Search a country or institution…" aria-label="Search a country or institution" autocomplete="off">
      <div class="gdrop" hidden></div>
    </div>
    <button id="themeBtn" class="icon-btn" type="button" aria-label="Switch light or dark theme" title="Light / dark">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
    </button>
  </div>
</header>
<main class="{main_class}">
{body}
</main>
<footer class="blog-foot">
  <img src="{LOGO}" alt="" width="22" height="22">
  <span><b>{SITE_NAME}</b> · Global Scientific Research &amp; Citation Analytics</span>
  <span class="muted"><a href="feed.xml">RSS feed</a> · Data: <a href="https://openalex.org" rel="noopener">OpenAlex</a> · <a href="https://pubmed.ncbi.nlm.nih.gov/" rel="noopener">PubMed</a></span>
</footer>
<script src="../assets/site.js" defer></script>
<script src="../assets/blog.js" defer></script>
</body>
</html>
"""


def nice_date(d: dt.date) -> str:
    return f"{d:%B} {d.day}, {d.year}"


def card(p: dict) -> str:
    kind_label = {"daily": "Research report", "guide": "Data guide"}.get(p["kind"], "Article")
    img = f'<img class="post-thumb" src="{esc(p["image"])}" alt="" loading="lazy">' if p["image"] else ""
    tags = "".join(f'<span class="chip">{esc(t)}</span>' for t in p["tags"][:3])
    return f"""<a class="post-card {p['kind']}" href="{esc(p['slug'])}.html" data-kind="{p['kind']}">
  {img}
  <div class="post-card-body">
    <div class="post-kicker"><span class="kind {p['kind']}">{kind_label}</span><time datetime="{p['date'].isoformat()}">{nice_date(p['date'])}</time></div>
    <h2>{esc(p['title'])}</h2>
    <p>{esc(p['summary'])}</p>
    <div class="post-meta">{tags}<span class="muted">{p['minutes']} min read</span></div>
  </div>
</a>"""


def build_index(posts: list[dict]) -> str:
    n_art = sum(1 for p in posts if p["kind"] == "article")
    n_guide = sum(1 for p in posts if p["kind"] == "guide")
    n_daily = len(posts) - n_art - n_guide
    cards = "\n".join(card(p) for p in posts) or '<p class="muted">No posts yet.</p>'
    body = f"""
<section class="blog-hero">
  <h1>The ResearchBoard Blog</h1>
  <p>Analysis, stories and daily reports on the world's research output.</p>
  <div class="seg blog-filter" role="group" aria-label="Filter posts">
    <button type="button" class="on" data-filter="all">All <span>{len(posts)}</span></button>
    <button type="button" data-filter="guide">Data guides <span>{n_guide}</span></button>
    <button type="button" data-filter="article">Articles <span>{n_art}</span></button>
    <button type="button" data-filter="daily">Research reports <span>{n_daily}</span></button>
  </div>
</section>
<section class="post-grid" id="postGrid">
{cards}
</section>"""
    return page(f"Blog · {SITE_NAME}", "Analysis, stories and daily reports on global research output.", body, f"{SITE_URL}/blog/")


def build_post(p: dict, prev: dict | None, nxt: dict | None) -> str:
    url = f"{SITE_URL}/blog/{p['slug']}.html"
    kind_label = {"daily": "Research report", "guide": "Data guide"}.get(p["kind"], "Article")
    tags = "".join(f'<span class="chip">{esc(t)}</span>' for t in p["tags"])
    hero = f'<img class="post-hero-img" src="{esc(p["image"])}" alt="">' if p["image"] else ""
    share_text = esc(p["title"])
    from urllib.parse import quote
    q_url, q_text = quote(url, safe=""), quote(p["title"], safe="")
    nav = '<nav class="post-nav">'
    nav += f'<a href="{esc(prev["slug"])}.html"><span class="muted">← Newer</span>{esc(prev["title"])}</a>' if prev else "<span></span>"
    nav += f'<a class="right" href="{esc(nxt["slug"])}.html"><span class="muted">Older →</span>{esc(nxt["title"])}</a>' if nxt else "<span></span>"
    nav += "</nav>"
    ld = json.dumps({"@context": "https://schema.org", "@type": "BlogPosting", "headline": p["title"],
                     "datePublished": p["date"].isoformat(), "author": {"@type": "Person" if p["author"] != SITE_NAME else "Organization", "name": p["author"]},
                     "publisher": {"@type": "Organization", "name": SITE_NAME}, "description": p["summary"], "url": url})
    body = f"""
<article class="post">
  <a class="back" href="./">← All posts</a>
  <div class="post-kicker"><span class="kind {p['kind']}">{kind_label}</span><time datetime="{p['date'].isoformat()}">{nice_date(p['date'])}</time><span>· {p['minutes']} min read</span></div>
  <h1>{esc(p['title'])}</h1>
  <p class="byline">By <b>{esc(p['author'])}</b></p>
  {hero}
  <div class="prose">
{p['html']}
  </div>
  <div class="post-tags">{tags}</div>
  <div class="share">
    <span class="muted">Share</span>
    <a class="btn" href="https://twitter.com/intent/tweet?text={q_text}&amp;url={q_url}" target="_blank" rel="noopener">X / Twitter</a>
    <a class="btn" href="https://www.linkedin.com/sharing/share-offsite/?url={q_url}" target="_blank" rel="noopener">LinkedIn</a>
    <a class="btn" href="https://www.facebook.com/sharer/sharer.php?u={q_url}" target="_blank" rel="noopener">Facebook</a>
    <button class="btn" type="button" data-copy="{esc(url)}" title="{share_text}">Copy link</button>
  </div>
  {nav}
</article>"""
    img = f"{SITE_URL}/blog/{p['social']}" if p.get("social") else ""
    return page(f"{p['title']} · {SITE_NAME}", p["summary"], body, url,
                f'<script type="application/ld+json">{ld}</script>', img)


def build_feed(posts: list[dict]) -> str:
    items = []
    for p in posts[:30]:
        url = f"{SITE_URL}/blog/{p['slug']}.html"
        pub = dt.datetime.combine(p["date"], dt.time(6, 0), dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        items.append(f"<item><title>{esc(p['title'])}</title><link>{url}</link><guid>{url}</guid>"
                     f"<pubDate>{pub}</pubDate><description>{esc(p['summary'])}</description></item>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
            f"<title>{SITE_NAME} blog</title><link>{SITE_URL}/blog/</link>"
            f"<description>{esc(TAGLINE)}</description>{''.join(items)}</channel></rss>\n")


def build() -> None:
    posts = load_posts()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    if (POSTS / "images").exists():
        shutil.copytree(POSTS / "images", OUT / "images")
    (OUT / "index.html").write_text(build_index(posts), encoding="utf-8")
    for i, p in enumerate(posts):
        prev = posts[i - 1] if i > 0 else None
        nxt = posts[i + 1] if i + 1 < len(posts) else None
        (OUT / f"{p['slug']}.html").write_text(build_post(p, prev, nxt), encoding="utf-8")
    (OUT / "feed.xml").write_text(build_feed(posts), encoding="utf-8")
    # sitemap + robots for search engines (the workflow copies these to the site root)
    today = dt.date.today().isoformat()
    urls = [(f"{SITE_URL}/", today, "daily", "1.0"), (f"{SITE_URL}/blog/", today, "daily", "0.8")]
    urls += [(f"{SITE_URL}/blog/{p['slug']}.html", p["date"].isoformat(), "monthly",
              {"guide": "0.9", "article": "0.7"}.get(p["kind"], "0.5")) for p in posts]
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import seo_pages
        urls += seo_pages.build(ROOT, SITE_URL, page, OUT)
    except Exception as e:  # noqa: BLE001 - SEO pages must never break the blog
        print("WARN seo pages:", e)
    try:
        import site_pages
        urls += site_pages.build(ROOT, SITE_URL, page, OUT)
        urls.append((f"{SITE_URL}/map/", today, "daily", "0.9"))
        urls.append((f"{SITE_URL}/quiz/", today, "monthly", "0.8"))
    except Exception as e:  # noqa: BLE001 - category pages must never break the blog
        import traceback; traceback.print_exc()
        print("WARN site pages:", e)
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{u}</loc><lastmod>{m}</lastmod><changefreq>{c}</changefreq><priority>{pr}</priority></url>\n"
                  for u, m, c, pr in urls) + "</urlset>\n", encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
    (OUT / "llms.txt").write_text(build_llms(posts), encoding="utf-8")
    try:
        from indexnow import KEY as _INDEXNOW_KEY
        (OUT / f"{_INDEXNOW_KEY}.txt").write_text(_INDEXNOW_KEY, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    summary =[{"title": p["title"], "slug": p["slug"], "date": p["date"].isoformat(), "kind": p["kind"],
                "summary": p["summary"], "minutes": p["minutes"], "author": p["author"],
                "image": ("blog/" + p["image"]) if p["image"] else ""} for p in posts[:12]]
    (OUT / "posts.json").write_text(json.dumps({"posts": summary}, ensure_ascii=False), encoding="utf-8")
    print(f"Blog built: {len(posts)} posts ({sum(p['kind'] == 'article' for p in posts)} articles)")


def build_llms(posts: list[dict]) -> str:
    """llms.txt: a plain-language map of the site for AI assistants and search tools."""
    stats = ""
    try:
        hist = json.loads((ROOT / "data" / "history.json").read_text(encoding="utf-8"))
        latest = json.loads((ROOT / "data" / "latest.json").read_text(encoding="utf-8"))
        days = hist.get("days", {})
        keys = [k for k in sorted(days) if k <= (latest.get("latest_day") or "9999")]
        ks = [k for k in keys if not k.endswith("-01")][-30:]
        if ks:
            pp = sorted(days[k].get("papers") or 0 for k in ks)
            cc = sorted(days[k].get("citations_made") or 0 for k in ks)
            stats = (f"- On a typical day in the last 30 days, about {pp[len(pp) // 2]:,} new research papers were published "
                     f"worldwide, citing earlier work about {cc[len(cc) // 2]:,} times.\n"
                     f"- Latest fully counted day: {keys[-1]}.\n")
    except Exception:  # noqa: BLE001
        pass
    guides = [p for p in posts if p["kind"] in ("guide", "article")][:40]
    lines = "\n".join(f"- [{p['title']}]({SITE_URL}/blog/{p['slug']}.html): {p['summary']}" for p in guides)
    return f"""# ResearchBoard

> ResearchBoard ({SITE_URL}) is a free website that tracks the world's research output every day, like a stock-market board for science: papers published, PubMed additions, citations, and rankings of countries, universities, journals, research fields and scientists. It also helps students find a research supervisor. No sign-up. Data comes from OpenAlex (an open index of over 250 million research works) and PubMed.

{stats}- Updated automatically every day. Daily figures are shown once a day is "fully counted", because journals report papers over several days.
- Citations, h-index and i10-index shown on ResearchBoard are OpenAlex figures. Google Scholar usually reports higher numbers; Scopus and Web of Science usually lower.
- Countries can be counted two ways: whole counting (a paper counts for every country of its authors) and fractional counting (a paper is shared between countries).

## Main pages

- [Live dashboard]({SITE_URL}/): today's papers, citations and the top countries, universities and journals, with a day picker.
- [World research map]({SITE_URL}/map/): tap any country to see its papers, world rank and top university.
- [Countries]({SITE_URL}/country/): a page for every country with daily papers, top universities and the top 5 most-cited scientists.
- [Universities]({SITE_URL}/universities/): the most active universities each day, plus a searchable list of about 30,000 universities by country with papers, citations, h-index, open-access share and website.
- [US universities for master's and PhD]({SITE_URL}/us-universities/): map and search of every US university that awards master's or doctoral degrees, with graduate application fee, tuition for international students, international student numbers, TOEFL, top programs and research output (IPEDS data).
- [Scientists and "Find a supervisor"]({SITE_URL}/scientists/): search active researchers by name, research topic, country, field or university, ranked by OpenAlex citations (career and last 5 years), h-index or i10-index.
- [Research trends (Weekly pulse)]({SITE_URL}/market/): countries, research fields and universities gaining or losing share of world research this week.
- [Research fields]({SITE_URL}/fields/) and [Journals]({SITE_URL}/journals/): daily papers by field and by journal.
- [Research Compass quiz]({SITE_URL}/quiz/): a free 2-minute picture quiz that suggests research fields that fit a student's interests.
- [Methods]({SITE_URL}/about/methods.html): exactly how every number is counted.

## Guides and articles

{lines}

## Contact

Email: researchboardlive@gmail.com · Facebook, LinkedIn and Bluesky: ResearchBoard
"""


# --------------------------------------------------------------------------- automatic daily post

def pct(v, prior) -> str:
    vals = [x for x in prior if isinstance(x, (int, float))]
    if v is None or not vals:
        return ""
    avg = sum(vals) / len(vals)
    if not avg:
        return ""
    ch = (v - avg) / avg * 100
    return f"{'up' if ch >= 0 else 'down'} {abs(ch):.1f}% on the 7-day average"


def write_daily() -> Path | None:
    hist = json.loads((DATA / "history.json").read_text(encoding="utf-8"))
    latest = json.loads((DATA / "latest.json").read_text(encoding="utf-8"))
    day = latest.get("latest_day")
    days = hist.get("days", {})
    if not day or day not in days:
        print("No complete day to report on.")
        return None
    rec = days[day]
    keys = sorted(days)
    prior = keys[max(0, keys.index(day) - 7):keys.index(day)]
    series = lambda k: [days[d].get(k) for d in prior]  # noqa: E731
    names = latest.get("country_names", {})
    inst_cc = latest.get("inst_country", {})
    d = dt.date.fromisoformat(day)
    nice = nice_date(d)
    f = lambda n: "—" if n is None else f"{n:,}"  # noqa: E731

    papers, pubmed, cites = rec.get("papers"), rec.get("pubmed_added"), rec.get("citations_made")
    countries = rec.get("countries", {})
    top_c = list(countries.items())[:5]
    lines = [
        "---",
        f"title: Research Report: {d:%A}, {d:%B} {d.day}, {d.year} — fully counted",
        f"date: {day}",
        "author: ResearchBoard",
        f"summary: {f(papers)} new papers from {len(countries)} countries"
        + (f", led by {names.get(top_c[0][0], top_c[0][0])}" if top_c else "")
        + (f"; {f(pubmed)} records added to PubMed." if pubmed is not None else "."),
        "tags: daily report",
        "---",
        "",
        f"![Research Report — {nice}](images/cards/daily-{day}.png)",
        "",
        f"Here is the research world on **{d:%A}, {d:%B} {d.day}, {d.year}**, now fully counted. "
        "Journals report new papers over several days, so we publish each day once all its papers are counted. "
        "All numbers come straight from OpenAlex and PubMed and may still rise slightly as late records arrive.",
        "",
        "## The day in numbers",
        "",
        "| Measure | Count | Trend |",
        "|---|---:|---|",
        f"| New papers published | {f(papers)} | {pct(papers, series('papers'))} |",
        f"| Records added to PubMed | {f(pubmed)} | {pct(pubmed, series('pubmed_added'))} |",
        f"| New citations made | {f(cites)} | {pct(cites, series('citations_made'))} |",
        f"| Countries publishing | {f(rec.get('countries_active'))} | |",
        f"| Active institutions | {f(rec.get('institutions_active'))} | |",
        "",
    ]
    if top_c:
        lines += ["## Top countries", "", "| # | Country | Papers | Share |", "|---:|---|---:|---:|"]
        for i, (code, n) in enumerate(top_c, 1):
            share = f"{n / papers * 100:.1f}%" if papers else ""
            lines.append(f"| {i} | {names.get(code, code)} | {n:,} | {share} |")
        lines.append("")
    insts = rec.get("institutions", [])[:5]
    if insts:
        lines += ["## Most active institutions", "", "| # | Institution | Country | Papers |", "|---:|---|---|---:|"]
        for i, x in enumerate(insts, 1):
            cc = inst_cc.get(x["id"]) or ""
            lines.append(f"| {i} | {x['name']} | {names.get(cc, cc)} | {x['count']:,} |")
        lines.append("")
    js = rec.get("journals", [])[:5]
    if js:
        lines += ["## Busiest journals", ""] + [f"{i}. **{x['name']}** — {x['count']:,} papers" for i, x in enumerate(js, 1)] + [""]
    fl = rec.get("fields", [])[:5]
    if fl:
        lines += ["## Leading research fields", ""] + [f"- {x['name']}: {x['count']:,} papers" for x in fl] + [""]
    pg = latest.get("paper_gainers", [])[:3]
    if pg:
        lines += ["## Papers gaining the most citations", ""]
        for x in pg:
            link = x.get("doi") or f"https://openalex.org/{x['id']}"
            lines.append(f"- [{x['title']}]({link}) ({x.get('venue') or 'journal n/a'}) — **+{x['gain']:,}** citations")
        lines.append("")
    ag = latest.get("gainers", [])[:3]
    if ag:
        lines += ["## Scientists gaining the most citations", ""]
        lines += [f"- **{x['name']}**{' (' + x['institution'] + ')' if x.get('institution') else ''} — +{x['gain']:,}" for x in ag] + [""]
    lines += ["---", "", "*Explore every number on the [live board](../#overview). "
              "Papers = articles, reviews, preprints, letters, conference papers and book chapters.*", ""]
    DAILY.mkdir(parents=True, exist_ok=True)
    out = DAILY / f"{day}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print("Daily post written:", out.relative_to(ROOT))
    return out


if __name__ == "__main__":
    if "--daily" in sys.argv:
        try:
            write_daily()
        except Exception as e:  # noqa: BLE001 - never block the blog build
            print("Daily post skipped:", e, file=sys.stderr)
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from social_card import make_daily_card
            make_daily_card(SITE_URL.split("://", 1)[-1])
        except Exception as e:  # noqa: BLE001
            print("Image card skipped:", e, file=sys.stderr)
    build()
