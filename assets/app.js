/* ResearchBoard — renders data/history.json and data/latest.json */
(function () {
  "use strict";

  const S = { history: null, latest: null, day: null, metric: "papers", range: 30, crange: 7, country: null, charts: {}, world: null };
  const $ = (s) => document.querySelector(s);
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const fmt = (n) => (n == null || Number.isNaN(n) ? "—" : Number(n).toLocaleString("en-US"));
  const compact = (v) => Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(v);
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

  // ------------------------------------------------------------------ theme
  function storedTheme() { try { return localStorage.getItem("researchboard-theme"); } catch (_) { return null; } }
  function setTheme(t) {
    if (t) document.documentElement.setAttribute("data-theme", t);
    try { if (t) localStorage.setItem("researchboard-theme", t); } catch (_) { /* private mode */ }
  }
  setTheme(storedTheme());
  $("#themeBtn").addEventListener("click", () => { setTheme(css("color-scheme") === "dark" ? "light" : "dark"); renderAll(); });

  // ------------------------------------------------------------------ data helpers
  const keys = () => Object.keys(S.history.days).filter((k) => S.history.days[k].papers != null || S.history.days[k].pubmed_added != null).sort();
  const rec = (d) => S.history.days[d] || {};
  const names = () => (S.latest && S.latest.country_names) || {};
  const countryName = (code) => names()[code] || (S.latest && S.latest.countries_detail && S.latest.countries_detail[code] && S.latest.countries_detail[code].name) || code;
  function countries(day) {
    const c = rec(day).countries || {};
    if (Array.isArray(c)) return c; // old format
    return Object.entries(c).map(([code, count]) => ({ code, name: countryName(code), count })).sort((a, b) => b.count - a.count);
  }
  function windowKeys(endDay, n) {
    const all = keys(); const i = all.indexOf(endDay);
    return all.slice(Math.max(0, i - n + 1), i + 1);
  }
  function rangeKeys(n) {
    const all = keys();
    if (!n) return all;
    return all.slice(-n);
  }
  const shortDate = (k) => new Date(k + "T00:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  const longDate = (k) => new Date(k + "T00:00:00Z").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });

  function flag(code) {
    const s = el("span", "fi fi-" + String(code || "").toLowerCase());
    s.setAttribute("aria-hidden", "true");
    return s;
  }

  function sparkline(values, w = 64, h = 22) {
    const pts = values.map((v, i) => [i, v]).filter((p) => typeof p[1] === "number");
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`); svg.setAttribute("width", w); svg.setAttribute("height", h);
    svg.classList.add("spark");
    if (pts.length < 2) return svg;
    const min = Math.min(...pts.map((p) => p[1])), max = Math.max(...pts.map((p) => p[1]));
    const x = (i) => 2 + (i / (values.length - 1)) * (w - 4);
    const y = (v) => (max === min ? h / 2 : h - 3 - ((v - min) / (max - min)) * (h - 6));
    const up = pts[pts.length - 1][1] >= pts[0][1];
    const path = document.createElementNS(ns, "polyline");
    path.setAttribute("points", pts.map((p) => `${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" "));
    path.setAttribute("fill", "none"); path.setAttribute("stroke", css(up ? "--up" : "--down"));
    path.setAttribute("stroke-width", "1.8"); path.setAttribute("stroke-linejoin", "round"); path.setAttribute("stroke-linecap", "round");
    svg.appendChild(path);
    const last = pts[pts.length - 1];
    const dot = document.createElementNS(ns, "circle");
    dot.setAttribute("cx", x(last[0])); dot.setAttribute("cy", y(last[1])); dot.setAttribute("r", 2.2);
    dot.setAttribute("fill", css(up ? "--up" : "--down"));
    svg.appendChild(dot);
    const t = document.createElementNS(ns, "title"); t.textContent = up ? "Rising over the period" : "Falling over the period";
    svg.appendChild(t);
    return svg;
  }

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

  // ------------------------------------------------------------------ charts
  function base() {
    const grid = css("--grid"), muted = css("--muted"), text = css("--text"), panel = css("--panel"), line = css("--line");
    return {
      responsive: true, maintainAspectRatio: false, animation: { duration: 250 },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: { backgroundColor: panel, titleColor: text, bodyColor: text, borderColor: line, borderWidth: 1, padding: 10, displayColors: false,
          titleFont: { family: "Inter", weight: "600" }, bodyFont: { family: "Inter" } },
      },
      scales: {
        x: { grid: { display: false }, border: { color: line }, ticks: { color: muted, maxRotation: 0, autoSkipPadding: 16, font: { family: "Inter", size: 11 } } },
        y: { beginAtZero: true, grid: { color: grid }, border: { display: false }, ticks: { color: muted, callback: (v) => compact(v), font: { family: "Inter", size: 11 } } },
      },
    };
  }
  function draw(id, cfg) {
    if (S.charts[id]) S.charts[id].destroy();
    const c = document.getElementById(id);
    if (!c || !window.Chart) return;
    S.charts[id] = new Chart(c, cfg);
  }
  function hbar(id, labels, values, label, color, onClick) {
    const o = base();
    o.indexAxis = "y";
    o.interaction = { mode: "nearest", axis: "y", intersect: false };
    o.scales = {
      x: { beginAtZero: true, grid: { color: css("--grid") }, border: { display: false }, ticks: { color: css("--muted"), callback: (v) => compact(v) } },
      y: { grid: { display: false }, border: { color: css("--line") }, ticks: { color: css("--text-2"), autoSkip: false,
        callback: function (v) { const s = this.getLabelForValue(v); return s.length > 28 ? s.slice(0, 27) + "…" : s; } } },
    };
    o.plugins.tooltip.callbacks = { label: (c) => label + ": " + fmt(c.parsed.x) };
    if (onClick) {
      o.onClick = (_e, els) => { if (els.length) onClick(els[0].index); };
      o.onHover = (e, els) => { e.native.target.style.cursor = els.length ? "pointer" : "default"; };
    }
    draw(id, { type: "bar", data: { labels, datasets: [{ data: values, backgroundColor: color, borderRadius: 4, borderSkipped: "start", barPercentage: 0.78, categoryPercentage: 0.9 }] }, options: o });
  }

  // ------------------------------------------------------------------ KPIs
  function delta(elm, value, prior, absolute) {
    elm.className = "kpi-delta"; elm.textContent = "";
    const p = prior.filter((v) => typeof v === "number");
    if (value == null || !p.length) return;
    const avg = p.reduce((a, b) => a + b, 0) / p.length;
    if (!avg) return;
    const up = value >= avg;
    elm.classList.add(up ? "up" : "down");
    elm.textContent = (up ? "↑ " : "↓ ") + (absolute ? (up ? "+" : "−") + Math.abs(Math.round(value - avg)) : Math.abs(((value - avg) / avg) * 100).toFixed(1) + "%");
    elm.title = "Compared with the average of the previous 7 days";
  }
  function renderKpis() {
    const all = keys(), i = all.indexOf(S.day), prior = all.slice(Math.max(0, i - 7), i);
    const r = rec(S.day), series = (k) => prior.map((d) => rec(d)[k]);
    const set = (id, k, abs) => {
      const box = document.getElementById(id);
      box.querySelector(".kpi-value").textContent = fmt(r[k]);
      delta(box.querySelector(".kpi-delta"), r[k], series(k), abs);
    };
    set("k-papers", "papers"); set("k-pubmed", "pubmed_added"); set("k-countries", "countries_active", true);
    set("k-insts", "institutions_active"); set("k-cites", "citations_made");
    const lab = $("#dayLabel");
    const ld = S.latest && S.latest.latest_day;
    lab.textContent = S.day === ld ? "Latest fully counted day" : S.day > ld ? "Still being indexed" : "Selected day";
  }

  // ------------------------------------------------------------------ trend
  function renderTrend() {
    const ks = rangeKeys(S.range);
    const m = S.metric;
    const vals = ks.map((k) => rec(k)[m] ?? null);
    const rankIdx = ks.indexOf(S.latest && S.latest.latest_day);
    const o = base();
    o.plugins.tooltip.callbacks = {
      title: (it) => longDate(ks[it[0].dataIndex]),
      label: (c) => (m === "papers" ? "Papers: " : "Added to PubMed: ") + fmt(c.parsed.y),
      afterLabel: (c) => (m === "papers" && rankIdx >= 0 && c.dataIndex > rankIdx ? "Still being indexed" : ""),
    };
    const color = css("--accent");
    draw("c-trend", {
      type: "line",
      data: { labels: ks.map(shortDate), datasets: [{ data: vals, borderColor: color, backgroundColor: css("--accent-fill"), fill: true, borderWidth: 2,
        pointRadius: ks.length <= 31 ? 3 : 0, pointBackgroundColor: color, pointHoverRadius: 5, cubicInterpolationMode: "monotone", spanGaps: true,
        segment: { borderDash: (c) => (m === "papers" && rankIdx >= 0 && c.p1DataIndex > rankIdx ? [5, 4] : undefined) } }] },
      options: o,
    });
    $("#trendTitle").textContent = m === "papers" ? "Daily Publications Worldwide" : "Papers Added to PubMed per Day";
    $("#trendFoot").textContent = m === "papers"
      ? "Scholarly papers by publication date. Dashed = days still being indexed; they rise over the following week."
      : "Records entering PubMed each day (Entrez date).";
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
    const labels = ["1–9", "10–49", "50–99", "100–249", "250–499", "500–999", "1,000+"];
    labels.forEach((t, i) => { const s = el("span"); const sw = el("i"); sw.style.background = `var(--map-${i + 1})`; s.append(sw, t); lg.appendChild(s); });
  }
  async function renderMap() {
    const box = $("#worldMap");
    $("#mapDay").textContent = shortDate(S.day);
    const feats = await loadWorld();
    if (!feats) { box.textContent = "Map unavailable (could not load map shapes)."; return; }
    const w = box.clientWidth || 600, h = Math.round(w / 1.9);
    const counts = Object.fromEntries(countries(S.day).map((c) => [c.code, c.count]));
    const iso = window.ISO_NUM_TO_A2 || {};
    const codeOf = (d) => iso[d.id] || (d.properties && d.properties.name === "Kosovo" ? "XK" : null);
    const proj = d3.geoNaturalEarth1().fitExtent([[4, 4], [w - 4, h - 4]], { type: "FeatureCollection", features: feats });
    const path = d3.geoPath(proj);
    let svg = d3.select(box).select("svg");
    if (svg.empty()) { box.textContent = ""; svg = d3.select(box).append("svg"); }
    svg.attr("viewBox", `0 0 ${w} ${h}`);
    const sel = svg.selectAll("path.country").data(feats, (d) => d.id);
    sel.join("path")
      .attr("class", (d) => "country" + (codeOf(d) === S.country ? " sel" : ""))
      .attr("d", path)
      .style("fill", (d) => {
        const v = counts[codeOf(d)];
        if (!v) return "var(--map-0)";
        let b = 1; [10, 50, 100, 250, 500, 1000].forEach((t, i) => { if (v >= t) b = i + 2; });
        return `var(--map-${Math.min(b, 7)})`;
      })
      .on("mousemove", (e, d) => {
        const code = codeOf(d); const v = counts[code];
        showTip(e, (code && countryName(code)) || d.properties.name, v ? fmt(v) + " papers" : "No papers recorded");
      })
      .on("mouseleave", hideTip)
      .on("click", (_e, d) => { const code = codeOf(d); if (code && counts[code]) { selectCountry(code); scrollToId("country-view"); } });
  }

  // ------------------------------------------------------------------ tables
  function rowCells(tr, cells) { cells.forEach((c) => tr.appendChild(c)); return tr; }
  function td(text, cls) { return el("td", cls, text); }
  function nameCell(label, icon) {
    const c = el("td", "name"); const t = el("div", "t");
    if (icon) t.appendChild(icon);
    const s = el("span", "lbl", label); s.title = label; t.appendChild(s); c.appendChild(t); return c;
  }
  function ccCell(code) {
    const c = el("td");
    if (code) { const s = el("span", "cc"); s.append(flag(code), document.createTextNode(code)); s.title = countryName(code); c.appendChild(s); }
    else c.textContent = "—";
    return c;
  }
  function fillTable(tbody, rows, build, emptyText) {
    tbody.replaceChildren();
    if (!rows.length) { const tr = el("tr"); const c = el("td", "empty", emptyText || "No data for this day yet."); c.colSpan = 6; tr.appendChild(c); tbody.appendChild(tr); return; }
    rows.forEach((r, i) => tbody.appendChild(build(r, i)));
  }

  function countryRow(c, i, total, trend) {
    const tr = el("tr", "clickable"); tr.dataset.code = c.code;
    rowCells(tr, [td(String(i + 1), "rank"), nameCell(c.name, flag(c.code)), td(fmt(c.count), "num"),
      td(total ? ((c.count / total) * 100).toFixed(1) + "%" : "—", "num")]);
    if (trend) { const t = el("td"); t.appendChild(sparkline(trend)); tr.appendChild(t); }
    tr.addEventListener("click", () => { selectCountry(c.code); scrollToId("country-view"); });
    return tr;
  }
  function instTrend(id) { return windowKeys(S.day, 14).map((k) => { const x = (rec(k).institutions || []).find((r) => r.id === id); return x ? x.count : null; }); }
  function countryTrend(code) { return windowKeys(S.day, 14).map((k) => { const c = rec(k).countries || {}; return Array.isArray(c) ? (c.find((x) => x.code === code) || {}).count ?? null : c[code] ?? null; }); }
  const instCountry = (id) => ((S.latest && S.latest.inst_country) || {})[id] || null;

  function renderTables() {
    const r = rec(S.day), total = r.papers;
    fillTable($("#tbl-countries tbody"), countries(S.day).slice(0, 10), (c, i) => countryRow(c, i, total, countryTrend(c.code)));
    fillTable($("#tbl-insts tbody"), (r.institutions || []).slice(0, 10), (x, i) => {
      const tr = el("tr"); tr.dataset.name = x.name;
      rowCells(tr, [td(String(i + 1), "rank"), nameCell(x.name), td(fmt(x.count), "num"), ccCell(instCountry(x.id))]);
      const t = el("td"); t.appendChild(sparkline(instTrend(x.id))); tr.appendChild(t);
      return tr;
    });
    fillTable($("#tbl-journals tbody"), (r.journals || []).slice(0, 10), (x, i) => {
      const tr = el("tr"); tr.dataset.name = x.name;
      return rowCells(tr, [td(String(i + 1), "rank"), nameCell(x.name), td(fmt(x.count), "num")]);
    });
  }

  // "View all" dialog
  const dlg = $("#moreDialog");
  $("#moreClose").addEventListener("click", () => dlg.close());
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
  function openMore(kind, highlight) {
    const r = rec(S.day), thead = $("#moreTable thead"), tbody = $("#moreTable tbody");
    const head = (cols) => { const tr = el("tr"); cols.forEach(([t, c]) => tr.appendChild(el("th", c, t))); thead.replaceChildren(tr); };
    if (kind === "countries") {
      $("#moreTitle").textContent = "All countries · " + shortDate(S.day);
      head([["#"], ["Country"], ["Papers", "num"], ["Share", "num"]]);
      fillTable(tbody, countries(S.day), (c, i) => { const tr = countryRow(c, i, r.papers); tr.addEventListener("click", () => dlg.close()); return tr; });
    } else if (kind === "universities") {
      $("#moreTitle").textContent = "Top universities & institutes · " + shortDate(S.day);
      head([["#"], ["Institution"], ["Papers", "num"], ["Country"]]);
      fillTable(tbody, r.institutions || [], (x, i) => { const tr = el("tr"); tr.dataset.name = x.name; return rowCells(tr, [td(String(i + 1), "rank"), nameCell(x.name), td(fmt(x.count), "num"), ccCell(instCountry(x.id))]); });
    } else {
      $("#moreTitle").textContent = "Top journals · " + shortDate(S.day);
      head([["#"], ["Journal"], ["Papers", "num"]]);
      fillTable(tbody, r.journals || [], (x, i) => { const tr = el("tr"); tr.dataset.name = x.name; return rowCells(tr, [td(String(i + 1), "rank"), nameCell(x.name), td(fmt(x.count), "num")]); });
    }
    if (typeof dlg.showModal === "function") dlg.showModal(); else dlg.setAttribute("open", "");
    if (highlight) {
      const row = [...tbody.querySelectorAll("tr")].find((t) => t.dataset.name === highlight || t.dataset.code === highlight);
      if (row) { row.classList.add("hl"); row.scrollIntoView({ block: "center" }); }
    }
  }
  document.querySelectorAll("[data-more]").forEach((b) => b.addEventListener("click", () => openMore(b.dataset.more)));

  // ------------------------------------------------------------------ citations
  function renderCitations() {
    const ks = rangeKeys(S.crange);
    const o = base();
    o.interaction = { mode: "nearest", axis: "x", intersect: false };
    o.plugins.tooltip.callbacks = { title: (it) => longDate(ks[it[0].dataIndex]), label: (c) => "Citations made: " + fmt(c.parsed.y) };
    draw("c-cites", { type: "bar", data: { labels: ks.map(shortDate), datasets: [{ data: ks.map((k) => rec(k).citations_made ?? null),
      backgroundColor: css("--violet"), borderRadius: 4, borderSkipped: "start", barPercentage: 0.7, categoryPercentage: 0.85 }] }, options: o });

    const L = S.latest || {};
    const gains = (L.paper_gainers || []).slice(0, 8);
    const fallback = !gains.length;
    const rows = fallback ? (L.hot_papers || []).slice(0, 8) : gains;
    const card = $("#tbl-paper-gains").closest(".card");
    const sub = card && card.querySelector("h2 .muted");
    if (sub) sub.textContent = fallback ? "· most cited, last 2 years" : "· largest increase";
    const lastTh = $("#tbl-paper-gains thead th:last-child"); if (lastTh) lastTh.textContent = fallback ? "Citations" : "Increase";
    $("#paperGainNote").textContent = fallback ? "daily increase starts tomorrow" : (L.paper_gainers_baseline ? "since " + shortDate(L.paper_gainers_baseline) : "");
    fillTable($("#tbl-paper-gains tbody"), rows, (p, i) => {
      const tr = el("tr");
      const t = el("td", "name"); const a = el("a", null, p.title); a.href = p.doi || "https://openalex.org/" + p.id; a.target = "_blank"; a.rel = "noopener";
      const wrap = el("div", "t"); const lbl = el("span", "lbl"); lbl.appendChild(a); lbl.title = p.title; wrap.appendChild(lbl); t.appendChild(wrap);
      const j = el("td", "muted", p.venue || "—"); j.style.whiteSpace = "nowrap"; j.style.maxWidth = "160px"; j.style.overflow = "hidden"; j.style.textOverflow = "ellipsis"; j.title = p.venue || "";
      return rowCells(tr, [td(String(i + 1), "rank"), t, j, fallback ? td(fmt(p.citations), "num") : td("+" + fmt(p.gain), "num gain")]);
    }, "No data yet.");
  }

  // ------------------------------------------------------------------ fields + scientists
  function renderFields() {
    const f = (rec(S.day).fields || []).slice(0, 12);
    $("#fieldDay").textContent = shortDate(S.day);
    hbar("c-fields", f.map((x) => x.name), f.map((x) => x.count), "Papers", css("--accent"));
  }
  function renderScientists() {
    const L = S.latest || {};
    const g = (L.gainers || []).slice(0, 5);
    if (g.length) {
      hbar("c-gainers", g.map((x) => x.name), g.map((x) => x.gain), "Citations gained", css("--up"));
      const sub0 = $("#c-gainers").closest(".card").querySelector("h2 .muted"); if (sub0) sub0.textContent = "· citations gained";
      const span = L.gainers_days && L.gainers_days > 1 ? ` (${L.gainers_days} days)` : "";
      $("#gainNote").textContent = L.gainers_baseline ? "since " + shortDate(L.gainers_baseline) + span : "";
    } else {
      // Until there is a day-to-day comparison, show the most-cited scientists instead of an empty chart.
      const top = (L.top_authors || []).slice(0, 5);
      const sub = $("#c-gainers").closest(".card").querySelector("h2 .muted");
      if (top.length) {
        hbar("c-gainers", top.map((x) => x.name), top.map((x) => x.citations), "Total citations", css("--accent"));
        if (sub) sub.textContent = "· most cited (total)";
        $("#gainNote").textContent = "daily gains start tomorrow";
        $("#gainFoot").textContent = "Daily citation gains appear once two daily snapshots exist. Until then: the most-cited scientists by total citations.";
      } else {
        if (S.charts["c-gainers"]) { S.charts["c-gainers"].destroy(); delete S.charts["c-gainers"]; }
        $("#gainFoot").textContent = "Appears after the second daily update (needs yesterday's snapshot). Measured among the 200 most-cited scientists.";
      }
    }
    fillTable($("#tbl-authors tbody"), L.top_authors || [], (a, i) => {
      const tr = el("tr");
      const n = nameCell(a.name, a.country ? flag(a.country) : null);
      const inst = el("td", "muted", a.institution || "—"); inst.style.maxWidth = "200px"; inst.style.overflow = "hidden"; inst.style.textOverflow = "ellipsis"; inst.style.whiteSpace = "nowrap"; inst.title = a.institution || "";
      return rowCells(tr, [td(String(i + 1), "rank"), n, inst, td(fmt(a.citations), "num")]);
    });
  }

  // ------------------------------------------------------------------ country view
  function selectCountry(code) {
    S.country = code;
    const sel = $("#countrySelect");
    if (![...sel.options].some((o) => o.value === code)) { const o = el("option", null, countryName(code)); o.value = code; sel.appendChild(o); }
    sel.value = code;
    renderCountry();
    if (S.world) renderMap();
  }
  function listInto(ol, rows, render) {
    ol.replaceChildren();
    if (!rows || !rows.length) { ol.appendChild(el("div", "empty", "No data for this country yet.")); return; }
    rows.forEach((r) => ol.appendChild(render(r)));
  }
  function rankItem(main, meta, num) {
    const li = el("li"); const body = el("span", null, main);
    if (meta) body.appendChild(el("span", "meta", meta));
    li.append(body, el("span", "n", num)); return li;
  }
  function renderCountry() {
    const code = S.country; if (!code) return;
    const list = countries(S.day), idx = list.findIndex((c) => c.code === code), r = rec(S.day);
    const c = idx >= 0 ? list[idx] : null;
    $("#cv-papers").textContent = c ? fmt(c.count) : "—";
    $("#cv-rank").textContent = c ? "#" + (idx + 1) : "—";
    $("#cv-share").textContent = c && r.papers ? ((c.count / r.papers) * 100).toFixed(1) + "%" : "—";
    $("#cv-pubmed").textContent = fmt((r.pubmed_by_country || {})[code]);
    const ks = rangeKeys(S.range), name = countryName(code);
    const o = base();
    o.plugins.tooltip.callbacks = { title: (it) => longDate(ks[it[0].dataIndex]), label: (x) => name + ": " + fmt(x.parsed.y) + " papers" };
    draw("c-country", { type: "line", data: { labels: ks.map(shortDate), datasets: [{ data: ks.map((k) => { const v = countryTrendFor(k, code); return v; }),
      borderColor: css("--accent"), backgroundColor: css("--accent-fill"), fill: true, borderWidth: 2, pointRadius: 0, pointHoverRadius: 5, cubicInterpolationMode: "monotone", spanGaps: true }] }, options: o });
    const d = ((S.latest && S.latest.countries_detail) || {})[code] || {};
    listInto($("#cv-insts"), d.top_institutions, (x) => rankItem(x.name, null, fmt(x.count)));
    listInto($("#cv-authors"), d.top_authors, (a) => rankItem(a.name, a.institution, fmt(a.citations)));
    const ld = S.latest && S.latest.latest_day;
    $("#cv-note").textContent = `Institutions and PubMed counts are for ${ld ? longDate(ld) : "the latest day"} (collected for the top ${Object.keys((S.latest && S.latest.countries_detail) || {}).length} countries). Scientists are ranked by all-time citations with a current affiliation in ${name}.`;
  }
  function countryTrendFor(k, code) { const c = rec(k).countries || {}; return Array.isArray(c) ? ((c.find((x) => x.code === code) || {}).count ?? null) : (c[code] ?? null); }

  // ------------------------------------------------------------------ papers
  function renderPapers() {
    const L = S.latest || {};
    const item = (p) => {
      const li = el("li"); const body = el("span");
      const a = el("a", null, p.title); a.href = p.doi || "https://openalex.org/" + p.id; a.target = "_blank"; a.rel = "noopener";
      body.append(a, el("span", "meta", [p.venue, p.year].filter(Boolean).join(" · ")));
      li.append(body, el("span", "n", fmt(p.citations))); return li;
    };
    listInto($("#hotPapers"), L.hot_papers, item);
    listInto($("#topPapers"), L.top_papers, item);
  }

  // ------------------------------------------------------------------ downloads
  function download(name, text) {
    const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
    const a = el("a"); a.href = URL.createObjectURL(blob); a.download = name;
    document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }
  const csvCell = (v) => (v == null ? "" : /[",\n]/.test(String(v)) ? '"' + String(v).replace(/"/g, '""') + '"' : String(v));
  $("#dlCsv").addEventListener("click", () => {
    const cols = ["date", "papers", "pubmed_added", "citations_made", "countries_active", "institutions_active"];
    const rows = [cols.join(",")].concat(keys().map((k) => cols.map((c) => csvCell(c === "date" ? k : rec(k)[c])).join(",")));
    download("researchboard-daily-totals.csv", rows.join("\n"));
  });
  $("#dlCountries").addEventListener("click", () => {
    const rows = ["date,country_code,country,papers"];
    keys().forEach((k) => countries(k).forEach((c) => rows.push([k, c.code, csvCell(c.name), c.count].join(","))));
    download("researchboard-countries-by-day.csv", rows.join("\n"));
  });

  // ------------------------------------------------------------------ search
  function buildSearch() {
    const dl = $("#searchList"); dl.replaceChildren();
    const r = rec(S.day), seen = new Set();
    const add = (v) => { if (!seen.has(v)) { seen.add(v); const o = el("option"); o.value = v; dl.appendChild(o); } };
    countries(S.day).forEach((c) => add(c.name));
    (r.institutions || []).forEach((x) => add(x.name));
    (r.journals || []).forEach((x) => add(x.name));
  }
  function runSearch(q) {
    q = (q || "").trim().toLowerCase(); if (!q) return;
    const r = rec(S.day);
    const c = countries(S.day).find((x) => x.name.toLowerCase() === q) || countries(S.day).find((x) => x.name.toLowerCase().startsWith(q));
    if (c) { selectCountry(c.code); scrollToId("country-view"); return; }
    const inst = (r.institutions || []).find((x) => x.name.toLowerCase().includes(q));
    if (inst) { openMore("universities", inst.name); return; }
    const j = (r.journals || []).find((x) => x.name.toLowerCase().includes(q));
    if (j) { openMore("journals", j.name); return; }
    const inp = $("#search"); inp.setCustomValidity("Not found in today's rankings"); inp.reportValidity(); setTimeout(() => inp.setCustomValidity(""), 1500);
  }
  $(".search").addEventListener("submit", (e) => { e.preventDefault(); runSearch($("#search").value); });
  $("#search").addEventListener("change", (e) => runSearch(e.target.value));

  // ------------------------------------------------------------------ nav highlighting
  function scrollToId(id) { const t = document.getElementById(id); if (t) t.scrollIntoView({ behavior: "smooth", block: "start" }); }
  function setupNav() {
    const links = [...document.querySelectorAll(".side-nav a, .topnav a")];
    const ids = [...new Set(links.map((a) => a.getAttribute("href").slice(1)))];
    const targets = ids.map((id) => document.getElementById(id)).filter(Boolean);
    if (!("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (!en.isIntersecting) return;
        links.forEach((a) => a.classList.toggle("on", a.getAttribute("href") === "#" + en.target.id));
      });
    }, { rootMargin: "-90px 0px -65% 0px" });
    targets.forEach((t) => io.observe(t));
  }

  // ------------------------------------------------------------------ render all
  function renderDayParts() { renderKpis(); renderTables(); renderFields(); renderCountry(); renderMap(); buildSearch(); }
  // ------------------------------------------------------------------ research market (last 24 hours)
  function renderMarket() {
    const m = S.latest && S.latest.market;
    const box = $("#market");
    if (!m) { box.hidden = true; return; }
    box.hidden = false;
    const t0 = new Date(m.from), t1 = new Date(m.to);
    const f = (d) => d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" });
    $("#mWindow").textContent = `${f(t0)} → ${f(t1)} UTC`;
    const hrs = Math.round(m.hours || 24);
    const tag = document.querySelector("#market .market-tag");
    if (tag) tag.lastChild.textContent = "Research Market · " + (Math.abs(hrs - 24) <= 2 ? "Last 24 hours" : `Last ${hrs} hours`);
    const track = $("#mTrack"); track.textContent = "";
    const ld = S.latest.latest_day;
    if (m.flagged) {
      box.classList.add("flagged");
      track.appendChild(el("span", "tk", "Today's 24-hour change is not shown: " + m.flagged + "."));
    } else {
      box.classList.remove("flagged");
      const items = [];
      const tk = (label, value, code, big) => {
        const s = el("span", "tk" + (big ? " big" : ""));
        if (code) { const fl = el("span", "fi fi-" + code.toLowerCase()); s.appendChild(fl); }
        s.appendChild(el("span", "lbl", label)); s.appendChild(el("span", "val", value)); return s;
      };
      items.push(tk("New papers added", "▲ +" + fmt(m.papers_added), null, true));
      if (m.pubmed_yesterday) items.push(tk("PubMed records added", "▲ +" + fmt(m.pubmed_yesterday), null, true));
      if (m.countries_active) items.push(tk("Countries contributing", fmt(m.countries_active), null, true));
      (m.countries || []).slice(0, 10).forEach((c) => items.push(tk(countryName(c.code), "▲ +" + fmt(c.added), c.code)));
      (m.institutions || []).slice(0, 5).forEach((i) => items.push(tk(i.name, "▲ +" + fmt(i.added))));
      // two copies so the scroll loops seamlessly
      [0, 1].forEach((copy) => items.forEach((n) => { const x = n.cloneNode(true); if (copy) x.setAttribute("aria-hidden", "true"); track.appendChild(x); }));
    }
    const note = $("#mNote"); note.textContent = "";
    note.append(`Papers added to the global research record in the ${Math.abs(hrs - 24) <= 2 ? "last 24 hours" : "last " + hrs + " hours"}, between our two most recent updates. `);
    note.append("The dashboard below shows the latest ");
    note.appendChild(el("b", null, "fully counted day"));
    note.append(ld ? ` (${longDate(ld)}), because journals report papers over several days.` : ".");
  }

  function renderAll() {
    if (!S.history) return;
    renderMarket(); renderDayParts(); renderTrend(); renderCitations(); renderScientists(); renderPapers();
  }

  // ------------------------------------------------------------------ blog strip
  async function renderBlog() {
    let data;
    try { data = await getJSON("blog/posts.json"); } catch (_) { return; }
    const posts = (data && data.posts) || [];
    if (!posts.length) return;
    // newest article first, then the newest posts of any kind
    const firstArticle = posts.find((p) => p.kind === "article");
    const pick = [...new Set([firstArticle, ...posts].filter(Boolean))].slice(0, 3);
    const strip = $("#blogStrip"); strip.replaceChildren();
    pick.forEach((p) => {
      const a = el("a", "post-card " + p.kind); a.href = "blog/" + encodeURIComponent(p.slug) + ".html";
      const body = el("div", "post-card-body");
      const kick = el("div", "post-kicker");
      kick.append(el("span", "kind " + p.kind, p.kind === "daily" ? "Daily report" : "Article"),
        el("time", null, new Date(p.date + "T00:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" })));
      body.append(kick, el("h2", null, p.title), el("p", null, p.summary));
      a.appendChild(body); strip.appendChild(a);
    });
    $("#blog").hidden = false;
  }

  async function getJSON(p) { const r = await fetch(p + "?t=" + Date.now(), { cache: "no-store" }); if (!r.ok) throw new Error(p); return r.json(); }

  async function init() {
    renderLegend(); setupNav(); renderBlog();
    try {
      const [h, l] = await Promise.all([getJSON("data/history.json"), getJSON("data/latest.json").catch(() => null)]);
      if (!h || !h.days || !Object.keys(h.days).length) throw new Error("empty");
      S.history = h; S.latest = l;
    } catch (_) {
      $("#emptyState").hidden = false; $("#sideStatus").lastChild.textContent = "No data yet"; return;
    }
    const all = keys();
    S.day = S.latest && all.includes(S.latest.latest_day) ? S.latest.latest_day : all[all.length - 1];

    const upd = S.history.updated ? new Date(S.history.updated) : null;
    if (upd) {
      $("#sideUpdated").textContent = upd.toLocaleString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) + " UTC";
      const stale = Date.now() - upd.getTime() > 36 * 3600 * 1000;
      const pill = $("#sideStatus"); pill.classList.toggle("stale", stale);
      pill.lastChild.textContent = stale ? "Update delayed" : "Up to date";
    }

    const daySel = $("#daySelect");
    all.slice().reverse().forEach((k) => { const o = el("option", null, longDate(k)); o.value = k; daySel.appendChild(o); });
    daySel.value = S.day;
    daySel.addEventListener("change", () => { S.day = daySel.value; renderDayParts(); });

    const cSel = $("#countrySelect");
    const opts = new Map(countries(S.day).map((c) => [c.code, c.name]));
    Object.keys((S.latest && S.latest.countries_detail) || {}).forEach((code) => { if (!opts.has(code)) opts.set(code, countryName(code)); });
    [...opts.entries()].sort((a, b) => a[1].localeCompare(b[1])).forEach(([code, name]) => { const o = el("option", null, name); o.value = code; cSel.appendChild(o); });
    cSel.addEventListener("change", () => selectCountry(cSel.value));
    S.country = (countries(S.day)[0] || {}).code || cSel.value || null;
    if (S.country) cSel.value = S.country;

    document.querySelectorAll("[data-range]").forEach((b) => b.addEventListener("click", () => {
      document.querySelectorAll("[data-range]").forEach((x) => x.classList.toggle("on", x === b));
      S.range = Number(b.dataset.range); renderTrend(); renderCountry();
    }));
    document.querySelectorAll("[data-metric]").forEach((b) => b.addEventListener("click", () => {
      document.querySelectorAll("[data-metric]").forEach((x) => x.classList.toggle("on", x === b));
      S.metric = b.dataset.metric; renderTrend();
    }));
    document.querySelectorAll("[data-crange]").forEach((b) => b.addEventListener("click", () => {
      document.querySelectorAll("[data-crange]").forEach((x) => x.classList.toggle("on", x === b));
      S.crange = Number(b.dataset.crange); renderCitations();
    }));

    let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => S.world && renderMap(), 150); });
    renderAll();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
