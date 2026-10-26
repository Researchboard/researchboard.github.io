/* ResearchBoard — renders data/history.json and data/latest.json */
(function () {
  "use strict";

  const state = { history: null, latest: null, range: 30, day: null, country: null, charts: {} };
  const $ = (sel) => document.querySelector(sel);
  const fmt = (n) => (n == null || Number.isNaN(n) ? "—" : Number(n).toLocaleString("en-US"));
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  // ------------------------------------------------------------------ theme
  function storedTheme() { try { return localStorage.getItem("researchboard-theme"); } catch (_) { return null; } }
  function setTheme(t) {
    if (t) document.documentElement.setAttribute("data-theme", t);
    try { if (t) localStorage.setItem("researchboard-theme", t); } catch (_) { /* ignore */ }
  }
  setTheme(storedTheme());
  $("#themeBtn").addEventListener("click", () => {
    const dark = css("color-scheme") === "dark";
    setTheme(dark ? "light" : "dark");
    renderAll();
  });

  // ------------------------------------------------------------------ data
  async function getJSON(path) {
    const res = await fetch(path + "?t=" + Date.now(), { cache: "no-store" });
    if (!res.ok) throw new Error(path + " " + res.status);
    return res.json();
  }

  function dayKeys() { return Object.keys(state.history.days).sort(); }
  function rec(day) { return state.history.days[day] || {}; }
  function inRange(keys) {
    if (!state.range) return keys;
    const last = new Date(keys[keys.length - 1] + "T00:00:00Z");
    const cut = new Date(last.getTime() - (state.range - 1) * 86400000).toISOString().slice(0, 10);
    return keys.filter((k) => k >= cut);
  }
  function shortDate(k) {
    const d = new Date(k + "T00:00:00Z");
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  }
  function longDate(k) {
    const d = new Date(k + "T00:00:00Z");
    return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
  }

  // ------------------------------------------------------------------ charts
  function baseOptions() {
    const grid = css("--grid"), muted = css("--muted"), text = css("--text"), panel = css("--panel"), line = css("--line");
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 300 },
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: panel, titleColor: text, bodyColor: text, borderColor: line, borderWidth: 1,
          padding: 10, displayColors: false,
          callbacks: { label: (c) => fmt(c.parsed[c.chart.options.indexAxis === "y" ? "x" : "y"]) },
        },
      },
      scales: {
        x: { grid: { display: false }, border: { color: line }, ticks: { color: muted, maxRotation: 0, autoSkipPadding: 14 } },
        y: { beginAtZero: true, grid: { color: grid }, border: { display: false },
             ticks: { color: muted, callback: (v) => Intl.NumberFormat("en-US", { notation: "compact" }).format(v) } },
      },
    };
  }

  function draw(id, config) {
    if (state.charts[id]) state.charts[id].destroy();
    const el = document.getElementById(id);
    if (!el || !window.Chart) return;
    state.charts[id] = new Chart(el, config);
  }

  function lineChart(id, keys, values, name) {
    const accent = css("--accent"), fill = css("--accent-fill");
    const opts = baseOptions();
    opts.plugins.tooltip.callbacks.title = (items) => longDate(keys[items[0].dataIndex]);
    opts.plugins.tooltip.callbacks.label = (c) => name + ": " + fmt(c.parsed.y);
    draw(id, {
      type: "line",
      data: {
        labels: keys.map(shortDate),
        datasets: [{ data: values, borderColor: accent, backgroundColor: fill, fill: true, borderWidth: 2,
                     pointRadius: 0, pointHoverRadius: 5, pointHoverBorderWidth: 2, pointHoverBorderColor: css("--panel"),
                     pointHoverBackgroundColor: accent, cubicInterpolationMode: "monotone", spanGaps: true }],
      },
      options: opts,
    });
  }

  function barChart(id, labels, values, name, onClick) {
    const opts = baseOptions();
    opts.indexAxis = "y";
    opts.interaction = { mode: "nearest", axis: "y", intersect: false };
    opts.scales = {
      x: { beginAtZero: true, grid: { color: css("--grid") }, border: { display: false },
           ticks: { color: css("--muted"), callback: (v) => Intl.NumberFormat("en-US", { notation: "compact" }).format(v) } },
      y: { grid: { display: false }, border: { color: css("--line") },
           ticks: { color: css("--text-2"), autoSkip: false, callback: function (v) {
             const s = this.getLabelForValue(v); return s.length > 30 ? s.slice(0, 29) + "…" : s; } } },
    };
    opts.plugins.tooltip.callbacks.label = (c) => name + ": " + fmt(c.parsed.x);
    if (onClick) {
      opts.onClick = (_e, els) => { if (els.length) onClick(els[0].index); };
      opts.onHover = (e, els) => { e.native.target.style.cursor = els.length ? "pointer" : "default"; };
    }
    draw(id, {
      type: "bar",
      data: { labels, datasets: [{ data: values, backgroundColor: css("--accent"), borderRadius: 4, borderSkipped: "start",
                                   barPercentage: 0.78, categoryPercentage: 0.9 }] },
      options: opts,
    });
  }

  // ------------------------------------------------------------------ tiles
  function tile(id, value, prevValues, isText) {
    const el = document.getElementById(id);
    el.querySelector(".value").textContent = isText ? (value || "—") : fmt(value);
    const d = el.querySelector(".delta");
    d.className = "delta";
    if (isText) { d.textContent = prevValues || " "; return; }
    const prev = (prevValues || []).filter((v) => typeof v === "number");
    if (value == null || !prev.length) { d.textContent = " "; return; }
    const avg = prev.reduce((a, b) => a + b, 0) / prev.length;
    if (!avg) { d.textContent = " "; return; }
    const pct = ((value - avg) / avg) * 100;
    d.classList.add(pct >= 0 ? "up" : "down");
    d.textContent = (pct >= 0 ? "▲ " : "▼ ") + Math.abs(pct).toFixed(1) + "% vs 7-day avg";
  }

  function renderTiles() {
    const keys = dayKeys();
    const day = state.day;
    const i = keys.indexOf(day);
    const prior = keys.slice(Math.max(0, i - 7), i);
    const r = rec(day);
    const series = (k) => prior.map((p) => rec(p)[k]);
    tile("t-pubmed", r.pubmed_added, series("pubmed_added"));
    tile("t-papers", r.openalex_published, series("openalex_published"));
    tile("t-cites", r.citations_made, series("citations_made"));
    const c = (r.countries || [])[0];
    tile("t-country", c ? c.name : null, c ? fmt(c.count) + " papers" : null, true);
    const inst = (r.institutions || [])[0];
    tile("t-inst", inst ? inst.name : null, inst ? fmt(inst.count) + " papers" : null, true);
  }

  // ------------------------------------------------------------------ sections
  function renderTrends() {
    const keys = inRange(dayKeys());
    lineChart("c-pubmed", keys, keys.map((k) => rec(k).pubmed_added ?? null), "Added to PubMed");
    lineChart("c-papers", keys, keys.map((k) => rec(k).openalex_published ?? null), "Papers published");
    lineChart("c-cites", keys, keys.map((k) => rec(k).citations_made ?? null), "Citations made");
  }

  function renderRankings() {
    const r = rec(state.day);
    $("#cDay").textContent = "· " + shortDate(state.day);
    $("#iDay").textContent = "· " + shortDate(state.day);
    const countries = (r.countries || []).slice(0, 15);
    barChart("c-countries", countries.map((c) => c.name), countries.map((c) => c.count), "Papers",
      (idx) => { selectCountry(countries[idx].code); document.getElementById("countryCard").scrollIntoView({ behavior: "smooth" }); });
    const insts = (r.institutions || []).slice(0, 15);
    barChart("c-insts", insts.map((x) => x.name), insts.map((x) => x.count), "Papers");
  }

  function countryOptions() {
    const seen = new Map();
    const latestDay = dayKeys().slice(-1)[0];
    (rec(latestDay).countries || []).forEach((c) => seen.set(c.code, c.name));
    Object.entries((state.latest && state.latest.countries_detail) || {}).forEach(([code, d]) => { if (!seen.has(code)) seen.set(code, d.name); });
    return [...seen.entries()];
  }

  function selectCountry(code) {
    state.country = code;
    $("#countrySelect").value = code;
    renderCountry();
  }

  function listInto(ol, rows, render) {
    ol.replaceChildren();
    if (!rows || !rows.length) {
      const li = document.createElement("div"); li.className = "empty"; li.textContent = "No data for this country yet.";
      ol.appendChild(li); return;
    }
    rows.forEach((row) => ol.appendChild(render(row)));
  }

  function rankItem(main, meta, num) {
    const li = document.createElement("li");
    const body = document.createElement("span");
    body.textContent = main;
    if (meta) { const m = document.createElement("span"); m.className = "meta"; m.textContent = meta; body.appendChild(m); }
    const n = document.createElement("span"); n.className = "n"; n.textContent = num;
    li.append(body, n);
    return li;
  }

  function renderCountry() {
    const code = state.country;
    if (!code) return;
    const keys = inRange(dayKeys());
    const dayRec = rec(state.day);
    const countries = dayRec.countries || [];
    const idx = countries.findIndex((c) => c.code === code);
    $("#cv-papers").textContent = idx >= 0 ? fmt(countries[idx].count) : "—";
    $("#cv-rank").textContent = idx >= 0 ? "#" + (idx + 1) : "—";
    const pm = (dayRec.pubmed_by_country || {})[code];
    $("#cv-pubmed").textContent = fmt(pm);
    const name = (countryOptions().find(([c]) => c === code) || [code, code])[1];
    lineChart("c-country", keys, keys.map((k) => {
      const c = (rec(k).countries || []).find((x) => x.code === code);
      return c ? c.count : null;
    }), name + " papers");

    const detail = ((state.latest && state.latest.countries_detail) || {})[code] || {};
    listInto($("#cv-insts"), detail.top_institutions, (x) => rankItem(x.name, null, fmt(x.count)));
    listInto($("#cv-authors"), detail.top_authors, (a) => rankItem(a.name, a.institution, fmt(a.citations)));
    const latestDay = state.latest && state.latest.latest_day;
    $("#cv-note").textContent = "Institutions are for " + (latestDay ? longDate(latestDay) : "the latest day") +
      "; scientists are ranked by all-time citations with a current affiliation in " + name +
      ". PubMed count shows the day selected above (collected for the top countries only).";
  }

  function renderLeaders() {
    const L = state.latest || {};
    const gainers = (L.gainers || []).slice(0, 5);
    if (gainers.length) {
      barChart("c-gainers", gainers.map((g) => g.name), gainers.map((g) => g.gain), "Citations gained");
      const span = L.gainers_days && L.gainers_days > 1 ? " over " + L.gainers_days + " days" : "";
      $("#gainNote").textContent = L.gainers_baseline ? "· since " + shortDate(L.gainers_baseline) + span : "";
    } else {
      if (state.charts["c-gainers"]) { state.charts["c-gainers"].destroy(); delete state.charts["c-gainers"]; }
      $("#gainNote").textContent = "";
      $("#gainFoot").textContent = "Appears after the second daily run (needs yesterday's snapshot to compare). Measured among the 200 most-cited scientists.";
    }

    const tbody = $("#tbl-authors tbody");
    tbody.replaceChildren();
    (L.top_authors || []).forEach((a, i) => {
      const tr = document.createElement("tr");
      const cells = [String(i + 1), a.name, a.institution || "—", fmt(a.citations)];
      cells.forEach((v, j) => {
        const td = document.createElement("td");
        td.textContent = v;
        if (j === 3) td.className = "num";
        if (j === 1 && a.works) { const m = document.createElement("span"); m.className = "meta"; m.textContent = fmt(a.works) + " works"; td.appendChild(m); }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });

    const paper = (p) => {
      const li = document.createElement("li");
      const body = document.createElement("span");
      const a = document.createElement("a");
      a.textContent = p.title;
      a.href = p.doi || "https://openalex.org/" + p.id;
      a.target = "_blank"; a.rel = "noopener";
      const m = document.createElement("span"); m.className = "meta";
      m.textContent = [p.venue, p.date || p.year].filter(Boolean).join(" · ");
      body.append(a, m);
      const n = document.createElement("span"); n.className = "n"; n.textContent = fmt(p.citations);
      li.append(body, n);
      return li;
    };
    listInto($("#hotPapers"), L.hot_papers, paper);
    listInto($("#topPapers"), L.top_papers, paper);
  }

  function renderAll() {
    if (!state.history) return;
    renderTiles(); renderTrends(); renderRankings(); renderCountry(); renderLeaders();
  }

  // ------------------------------------------------------------------ init
  async function init() {
    try {
      const [history, latest] = await Promise.all([getJSON("data/history.json"), getJSON("data/latest.json").catch(() => null)]);
      if (!history || !history.days || !Object.keys(history.days).length) throw new Error("empty");
      state.history = history; state.latest = latest;
    } catch (_) {
      $("#emptyState").hidden = false;
      $("#asof").textContent = "No data yet";
      return;
    }
    const keys = dayKeys();
    state.day = (state.latest && keys.includes(state.latest.latest_day)) ? state.latest.latest_day : keys[keys.length - 1];

    const upd = state.history.updated ? new Date(state.history.updated) : null;
    $("#asof").textContent = "Data for " + longDate(state.day) + (upd ? " · updated " + upd.toLocaleString() : "");

    const daySel = $("#daySelect");
    keys.slice().reverse().forEach((k) => { const o = document.createElement("option"); o.value = k; o.textContent = longDate(k); daySel.appendChild(o); });
    daySel.value = state.day;
    daySel.addEventListener("change", () => { state.day = daySel.value; renderTiles(); renderRankings(); renderCountry(); });

    const cSel = $("#countrySelect");
    countryOptions().forEach(([code, name]) => { const o = document.createElement("option"); o.value = code; o.textContent = name; cSel.appendChild(o); });
    cSel.addEventListener("change", () => selectCountry(cSel.value));
    state.country = cSel.value || null;

    document.querySelectorAll(".seg button").forEach((b) => b.addEventListener("click", () => {
      document.querySelectorAll(".seg button").forEach((x) => x.classList.toggle("on", x === b));
      state.range = Number(b.dataset.range);
      renderTrends(); renderCountry();
    }));

    renderAll();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
