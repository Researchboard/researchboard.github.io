/* ResearchBoard homepage — market ticker, world map, summary, previews, trend */
(function () {
  "use strict";

  const S = { history: null, latest: null, day: null, metric: "papers", range: 30, chart: null, world: null };
  const $ = (s) => document.querySelector(s);
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const fmt = (n) => (n == null || Number.isNaN(n) ? "—" : Number(n).toLocaleString("en-US"));
  const compact = (v) => Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(v);
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const slug = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "country";

  // ------------------------------------------------------------------ data helpers
  const keys = () => Object.keys(S.history.days).filter((k) => S.history.days[k].papers != null || S.history.days[k].pubmed_added != null).sort();
  const rec = (d) => S.history.days[d] || {};
  const names = () => (S.latest && S.latest.country_names) || {};
  const countryName = (code) => names()[code] || code;
  function countries(day) {
    const c = rec(day).countries || {};
    if (Array.isArray(c)) return c;
    return Object.entries(c).map(([code, count]) => ({ code, name: countryName(code), count })).sort((a, b) => b.count - a.count);
  }
  const shortDate = (k) => new Date(k + "T00:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  const longDate = (k) => new Date(k + "T00:00:00Z").toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric", timeZone: "UTC" });
  const flag = (code) => { const s = el("span", "fi fi-" + String(code || "").toLowerCase()); s.setAttribute("aria-hidden", "true"); return s; };

  // ------------------------------------------------------------------ tooltip
  const tip = $("#tip");
  function showTip(e, title, line) {
    tip.replaceChildren(el("b", null, title), el("span", null, line));
    tip.hidden = false;
    const pad = 14, r = tip.getBoundingClientRect();
    let x = e.clientX + pad, y = e.clientY + pad;
    if (x + r.width > innerWidth - 8) x = e.clientX - r.width - pad;
    if (y + r.height > innerHeight - 8) y = e.clientY - r.height - pad;
    tip.style.left = x + "px"; tip.style.top = y + "px";
  }
  const hideTip = () => { tip.hidden = true; };

  // ------------------------------------------------------------------ market ticker
  function renderMarket() {
    const m = S.latest && S.latest.market;
    const box = $("#market");
    if (!m) { box.hidden = true; return; }
    box.hidden = false;
    const t0 = new Date(m.from), t1 = new Date(m.to);
    const f = (d) => d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" });
    $("#mWindow").textContent = `${f(t0)} → ${f(t1)} UTC`;
    const hrs = Math.round(m.hours || 24);
    const span = Math.abs(hrs - 24) <= 2 ? "Last 24 hours" : `Last ${hrs} hours`;
    const tag = document.querySelector("#market .market-tag");
    if (tag) tag.lastChild.textContent = "Research trends · " + span;
    const track = $("#mTrack"); track.textContent = "";
    if (m.flagged) {
      box.classList.add("flagged");
      track.appendChild(el("span", "tk", /no growth/.test(m.flagged) ? "No change to show yet — our data source (OpenAlex) has not added new papers since the last update. Check back after the next update." : "Today's 24-hour change is not shown (" + m.flagged + ")."));
    } else {
      box.classList.remove("flagged");
      const items = [];
      const tk = (label, value, code, big) => {
        const s = el("span", "tk" + (big ? " big" : ""));
        if (code) s.appendChild(flag(code));
        s.appendChild(el("span", "lbl", label)); s.appendChild(el("span", "val", value)); return s;
      };
      items.push(tk("New papers added", "▲ +" + fmt(m.papers_added), null, true));
      if (m.pubmed_yesterday) items.push(tk("PubMed records added", "▲ +" + fmt(m.pubmed_yesterday), null, true));
      if (m.countries_active) items.push(tk("Countries contributing", fmt(m.countries_active), null, true));
      (m.countries || []).slice(0, 10).forEach((c) => items.push(tk(countryName(c.code), "▲ +" + fmt(c.added), c.code)));
      (m.institutions || []).slice(0, 5).forEach((i) => items.push(tk(i.name, "▲ +" + fmt(i.added))));
      [0, 1].forEach((copy) => items.forEach((n) => { const x = n.cloneNode(true); if (copy) x.setAttribute("aria-hidden", "true"); track.appendChild(x); }));
    }
    const ld = S.latest.latest_day;
    const note = $("#mNote"); note.textContent = "";
    note.append(`Papers added to the global research record in the ${span.toLowerCase()}, between our two most recent updates. Everything below shows the latest `);
    note.appendChild(el("b", null, "fully counted day"));
    note.append(ld ? ` (${shortDate(ld)}), because journals report papers over several days.` : ".");
  }

  // ------------------------------------------------------------------ summary card
  function setDelta(id, value, prior, absolute) {
    const e = $(id); e.className = ""; e.textContent = "";
    const p = prior.filter((v) => typeof v === "number");
    if (value == null || !p.length) return;
    const avg = p.reduce((a, b) => a + b, 0) / p.length;
    if (!avg) return;
    const up = value >= avg;
    e.className = up ? "up" : "down";
    e.textContent = (up ? "▲ " : "▼ ") + (absolute ? Math.abs(Math.round(value - avg)) : Math.abs(((value - avg) / avg) * 100).toFixed(1) + "%");
    e.title = "Compared with the average of the previous 7 days";
  }
  function renderSummary() {
    const all = keys(), i = all.indexOf(S.day), prior = all.slice(Math.max(0, i - 7), i);
    const r = rec(S.day), series = (k) => prior.map((d) => rec(d)[k]);
    $("#s-papers").textContent = fmt(r.papers); setDelta("#d-papers", r.papers, series("papers"));
    $("#s-pubmed").textContent = fmt(r.pubmed_added); setDelta("#d-pubmed", r.pubmed_added, series("pubmed_added"));
    $("#s-cites").textContent = fmt(r.citations_made); setDelta("#d-cites", r.citations_made, series("citations_made"));
    window.RB_SHARE_TEXT = `Today in global research (${longDate(S.day)}): ${fmt(r.papers)} new papers from ${fmt(r.countries_active)} countries. Where does your country rank? — via ResearchBoard`;
    $("#s-countries").textContent = fmt(r.countries_active); setDelta("#d-countries", r.countries_active, series("countries_active"), true);
    const ld = S.latest && S.latest.latest_day;
    $("#dayTitle").textContent = longDate(S.day);
    $("#dayLabel").textContent = S.day === ld ? "Latest fully counted day" : S.day > ld ? "Still being counted — numbers will rise" : "Earlier day";
    const t3 = $("#top3"); t3.replaceChildren();
    countries(S.day).slice(0, 3).forEach((c, k) => {
      const a = el("a"); a.href = "country/" + slug(c.name) + ".html";
      const left = el("span"); left.append(flag(c.code), `${k + 1}. ${c.name}`);
      a.append(left, el("b", null, fmt(c.count))); t3.appendChild(a);
    });
    const inst = (r.institutions || [])[0], field = (r.fields || [])[0];
    const p = $("#sumText"); p.replaceChildren();
    if (inst) { p.append("Most active institution: "); p.appendChild(el("b", null, inst.name)); p.append(` (${fmt(inst.count)} papers). `); }
    if (field) { p.append("Leading field: "); p.appendChild(el("b", null, field.name)); p.append(` (${fmt(field.count)} papers).`); }
    const rl = $("#reportLink"); rl.href = "blog/daily-" + S.day + ".html";
    fetch(rl.href, { method: "HEAD" }).then((x) => { if (!x.ok) rl.href = "blog/"; }).catch(() => { rl.href = "blog/"; });
  }

  // ------------------------------------------------------------------ map
  async function loadWorld() {
    if (S.world || !window.d3 || !window.topojson) return S.world;
    try {
      const topo = await d3.json("https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json");
      S.world = topojson.feature(topo, topo.objects.countries).features.filter((f) => f.id !== "010");
    } catch (_) { S.world = null; }
    return S.world;
  }
  function renderLegend() {
    const lg = $("#mapLegend"); lg.replaceChildren();
    ["1–9", "10–49", "50–99", "100–249", "250–499", "500–999", "1,000+"].forEach((t, i) => {
      const s = el("span"); const sw = el("i"); sw.style.background = `var(--map-${i + 1})`; s.append(sw, t); lg.appendChild(s);
    });
  }
  async function renderMap() {
    const box = $("#worldMap");
    $("#mapDay").textContent = longDate(S.day);
    const feats = await loadWorld();
    if (!feats) { box.textContent = "Map unavailable (could not load map shapes)."; return; }
    const w = box.clientWidth || 800, h = Math.round(w / 2.0);
    const list = countries(S.day);
    const counts = Object.fromEntries(list.map((c) => [c.code, c.count]));
    const rank = Object.fromEntries(list.map((c, i) => [c.code, i + 1]));
    const iso = window.ISO_NUM_TO_A2 || {};
    const codeOf = (d) => iso[d.id] || (d.properties && d.properties.name === "Kosovo" ? "XK" : null);
    const proj = d3.geoNaturalEarth1().fitExtent([[4, 4], [w - 4, h - 4]], { type: "FeatureCollection", features: feats });
    const path = d3.geoPath(proj);
    let svg = d3.select(box).select("svg");
    if (svg.empty()) { box.textContent = ""; svg = d3.select(box).append("svg"); }
    svg.attr("viewBox", `0 0 ${w} ${h}`);
    svg.selectAll("path.country").data(feats, (d) => d.id).join("path")
      .attr("class", "country")
      .attr("d", path)
      .style("fill", (d) => {
        const v = counts[codeOf(d)];
        if (!v) return "var(--map-0)";
        let b = 1; [10, 50, 100, 250, 500, 1000].forEach((t, i) => { if (v >= t) b = i + 2; });
        return `var(--map-${Math.min(b, 7)})`;
      })
      .on("mousemove", (e, d) => {
        const code = codeOf(d), v = counts[code];
        const name = (code && countryName(code)) || d.properties.name;
        showTip(e, name, v ? `${fmt(v)} papers · #${rank[code]} worldwide — click to open` : "No papers recorded");
      })
      .on("mouseleave", hideTip)
      .on("click", (_e, d) => {
        const code = codeOf(d);
        if (code && counts[code]) location.href = "country/" + slug(countryName(code)) + ".html";
      });
  }

  // ------------------------------------------------------------------ previews
  function card(icon, title, rows, see, href, opts = {}) {
    const a = el("article", "pcard");
    const h = el("h3"); h.append(el("span", "ico", icon), title);
    if (opts.badge) h.appendChild(el("small", null, opts.badge));
    a.appendChild(h);
    if (!rows.length) a.appendChild(el("div", "empty", opts.empty || "Appears after the next daily update."));
    else {
      const ol = el("ol");
      const max = Math.max(...rows.map((r) => r.value || 0)) || 1;
      rows.forEach((r, i) => {
        const li = el("li");
        const nm = el("span", "nm");
        if (r.code) nm.appendChild(flag(r.code));
        if (r.href) { const x = el("a", null, r.name); x.href = r.href; if (r.ext) { x.target = "_blank"; x.rel = "noopener"; } nm.appendChild(x); } else nm.append(r.name);
        if (opts.bars) { const b = el("div", "bar"); b.style.width = (r.value / max) * 100 + "%"; nm.appendChild(b); }
        nm.title = r.name;
        li.append(el("span", "n", String(i + 1)), nm, el("span", "v" + (opts.green ? " g" : ""), (opts.green ? "+" : "") + fmt(r.value)));
        ol.appendChild(li);
      });
      a.appendChild(ol);
    }
    const s = el("a", "see", see + " →"); s.href = href; a.appendChild(s);
    return a;
  }
  function renderPreviews() {
    const r = rec(S.day), L = S.latest || {};
    const box = $("#prev"); box.replaceChildren();
    $("#prevNote").textContent = shortDate(S.day) + " · see all for full rankings, history and downloads";
    const ic = L.inst_country || {};
    box.append(
      card("🌍", "Top countries", countries(S.day).slice(0, 5).map((c) => ({ name: c.name, code: c.code, value: c.count, href: "country/" + slug(c.name) + ".html" })), "See all countries", "country/"),
      card("🏛️", "Top universities", (r.institutions || []).slice(0, 5).map((x) => ({ name: x.name, code: ic[x.id], value: x.count, href: "explore/?id=" + encodeURIComponent(x.id) })), "See all universities", "universities/"),
      card("📚", "Top journals", (r.journals || []).slice(0, 5).map((x) => ({ name: x.name, value: x.count })), "See all journals", "journals/"),
      card("🔬", "Research fields", (r.fields || []).slice(0, 5).map((x) => ({ name: x.name, value: x.count })), "See all fields", "fields/", { bars: true }),
      card("📄", "Most-cited new papers", (L.hot_papers || []).slice(0, 5).map((p) => ({ name: p.title, value: p.citations, href: p.doi || "https://openalex.org/" + p.id, ext: true })), "See all papers", "papers/", { badge: "last 2 years" }),
      (L.gainers && L.gainers.length)
        ? card("🚀", "Scientists gaining citations", L.gainers.slice(0, 5).map((g) => ({ name: g.name, value: g.gain })), "See all scientists", "scientists/", { green: true, badge: "since yesterday" })
        : card("🏆", "Most-cited scientists", (L.top_authors || []).slice(0, 5).map((a) => ({ name: a.name, code: a.country, value: a.citations })), "See all scientists", "scientists/", { badge: "all time" }),
    );
  }

  // ------------------------------------------------------------------ trend
  function renderTrend() {
    if (!window.Chart) return;
    const all = keys(); const ks = S.range ? all.slice(-S.range) : all;
    const m = S.metric, vals = ks.map((k) => rec(k)[m] ?? null);
    const rankIdx = ks.indexOf(S.latest && S.latest.latest_day);
    const color = css("--accent"), grid = css("--grid"), muted = css("--muted"), text = css("--text"), panel = css("--panel"), line = css("--line");
    if (S.chart) S.chart.destroy();
    S.chart = new Chart($("#c-trend"), {
      type: "line",
      data: { labels: ks.map(shortDate), datasets: [{ data: vals, borderColor: color, backgroundColor: css("--accent-fill"), fill: true, borderWidth: 2,
        pointRadius: ks.length <= 31 ? 3 : 0, pointBackgroundColor: color, pointHoverRadius: 5, cubicInterpolationMode: "monotone", spanGaps: true,
        segment: { borderDash: (c) => (m === "papers" && rankIdx >= 0 && c.p1DataIndex > rankIdx ? [5, 4] : undefined) } }] },
      options: {
        responsive: true, maintainAspectRatio: false, animation: { duration: 250 }, interaction: { mode: "index", intersect: false },
        plugins: { legend: { display: false }, tooltip: { backgroundColor: panel, titleColor: text, bodyColor: text, borderColor: line, borderWidth: 1, padding: 10, displayColors: false,
          callbacks: { title: (it) => longDate(ks[it[0].dataIndex]), label: (c) => (m === "papers" ? "Papers: " : "Added to PubMed: ") + fmt(c.parsed.y),
            afterLabel: (c) => (m === "papers" && rankIdx >= 0 && c.dataIndex > rankIdx ? "Still being counted" : "") } } },
        scales: {
          x: { grid: { display: false }, border: { color: line }, ticks: { color: muted, maxRotation: 0, autoSkipPadding: 16, font: { family: "Inter", size: 11 } } },
          y: { beginAtZero: true, grid: { color: grid }, border: { display: false }, ticks: { color: muted, callback: (v) => compact(v), font: { family: "Inter", size: 11 } } },
        },
      },
    });
    $("#trendTitle").textContent = m === "papers" ? "Daily publications worldwide" : "Papers added to PubMed per day";
    $("#trendFoot").textContent = m === "papers"
      ? "Papers by publication date. Dashed = days still being counted; they rise over the following week."
      : "Records entering PubMed each day.";
  }

  // ------------------------------------------------------------------ blog strip
  async function renderBlog() {
    let data;
    try { data = await getJSON("blog/posts.json"); } catch (_) { return; }
    const posts = (data && data.posts) || [];
    if (!posts.length) return;
    // newest daily report + two guides/articles that change every day
    const daily = posts.find((p) => p.kind === "daily");
    const others = posts.filter((p) => p.kind !== "daily" && p.slug !== "welcome");
    const off = others.length ? Math.floor(Date.now() / 864e5) % others.length : 0;
    const pick = [daily, others[off], others[(off + 1) % Math.max(1, others.length)]]
      .filter((p, i, arr) => p && arr.indexOf(p) === i).slice(0, 3);
    const strip = $("#blogStrip"); strip.replaceChildren();
    pick.forEach((p) => {
      const a = el("a", "post-card " + p.kind); a.href = "blog/" + encodeURIComponent(p.slug) + ".html";
      const body = el("div", "post-card-body");
      const kick = el("div", "post-kicker");
      kick.append(el("span", "kind " + p.kind, p.kind === "daily" ? "Research report" : p.kind === "guide" ? "Data guide" : "Article"),
        el("time", null, new Date(p.date + "T00:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" })));
      body.append(kick, el("h2", null, p.title), el("p", null, p.summary));
      a.appendChild(body); strip.appendChild(a);
    });
    $("#blog").hidden = false;
  }

  // ------------------------------------------------------------------ downloads
  function download(name, text) {
    const a = el("a"); a.href = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" })); a.download = name;
    document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }
  const csvCell = (v) => (v == null ? "" : /[",\n]/.test(String(v)) ? '"' + String(v).replace(/"/g, '""') + '"' : String(v));
  $("#dlCsv").addEventListener("click", () => {
    if (!S.history) return;
    const cols = ["date", "papers", "pubmed_added", "citations_made", "countries_active", "institutions_active"];
    download("researchboard-daily-totals.csv", [cols.join(",")].concat(keys().map((k) => cols.map((c) => csvCell(c === "date" ? k : rec(k)[c])).join(","))).join("\n"));
  });
  $("#dlCountries").addEventListener("click", () => {
    if (!S.history) return;
    const rows = ["date,country_code,country,papers"];
    keys().forEach((k) => countries(k).forEach((c) => rows.push([k, c.code, csvCell(c.name), c.count].join(","))));
    download("researchboard-countries-by-day.csv", rows.join("\n"));
  });

  // ------------------------------------------------------------------ init
  async function getJSON(p) { const r = await fetch(p + "?t=" + Date.now(), { cache: "no-store" }); if (!r.ok) throw new Error(p); return r.json(); }
  const renderDay = () => { renderSummary(); renderMap(); renderPreviews(); };
  function renderAll() { if (!S.history) return; renderMarket(); renderDay(); renderTrend(); }
  document.addEventListener("rb-theme", renderAll);

  async function init() {
    renderLegend(); renderBlog();
    try {
      const [h, l] = await Promise.all([getJSON("data/history.json"), getJSON("data/latest.json").catch(() => null)]);
      if (!h || !h.days || !Object.keys(h.days).length) throw new Error("empty");
      S.history = h; S.latest = l;
    } catch (_) { $("#emptyState").hidden = false; return; }
    const all = keys();
    S.day = S.latest && all.includes(S.latest.latest_day) ? S.latest.latest_day : all[all.length - 1];
    const latestDay = S.day;
    const fromURL = new URLSearchParams(location.search).get("day");
    if (fromURL && all.includes(fromURL)) S.day = fromURL;
    const pick = $("#dayPick");
    pick.min = all[0]; pick.max = all[all.length - 1];
    const setDay = (k, push) => {
      if (!all.includes(k)) {                       // a date with no data: jump to the closest day we have
        k = all.reduce((best, x) => (Math.abs(new Date(x) - new Date(k)) < Math.abs(new Date(best) - new Date(k)) ? x : best), all[0]);
      }
      S.day = k; pick.value = k;
      $("#dPrev").disabled = all.indexOf(k) <= 0;
      $("#dNext").disabled = all.indexOf(k) >= all.length - 1;
      $("#dLatest").hidden = k === latestDay;
      try {
        const u = new URL(location.href);
        if (k === latestDay) u.searchParams.delete("day"); else u.searchParams.set("day", k);
        history[push ? "pushState" : "replaceState"]({ day: k }, "", u);
      } catch (_) { /* file:// preview */ }
      renderDay();
    };
    S.setDay = setDay;
    pick.addEventListener("change", () => pick.value && setDay(pick.value, true));
    $("#dPrev").addEventListener("click", () => setDay(all[Math.max(0, all.indexOf(S.day) - 1)], true));
    $("#dNext").addEventListener("click", () => setDay(all[Math.min(all.length - 1, all.indexOf(S.day) + 1)], true));
    $("#dLatest").addEventListener("click", () => setDay(latestDay, true));
    addEventListener("popstate", () => setDay(new URLSearchParams(location.search).get("day") || latestDay, false));
    pick.value = S.day;
    $("#dPrev").disabled = all.indexOf(S.day) <= 0;
    $("#dNext").disabled = all.indexOf(S.day) >= all.length - 1;
    $("#dLatest").hidden = S.day === latestDay;
    document.querySelectorAll("[data-range]").forEach((b) => b.addEventListener("click", () => {
      document.querySelectorAll("[data-range]").forEach((x) => x.classList.toggle("on", x === b)); S.range = Number(b.dataset.range); renderTrend();
    }));
    document.querySelectorAll("[data-metric]").forEach((b) => b.addEventListener("click", () => {
      document.querySelectorAll("[data-metric]").forEach((x) => x.classList.toggle("on", x === b)); S.metric = b.dataset.metric; renderTrend();
    }));
    let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => S.world && renderMap(), 150); });
    renderAll();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
