/* US universities for master's and PhD study: map + search + details.
   Mounts into <div id="usUnis" data-base="data/"> (homepage) or data-base="../data/" (/us-universities/).
   Data: data/us-unis.json (IPEDS, US Department of Education), research numbers live from OpenAlex. */
(function () {
  const box = document.getElementById("usUnis");
  if (!box) return;
  const BASE = box.dataset.base || "data/";
  const SITE = box.dataset.site || "";               // prefix for links to other ResearchBoard pages
  const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString("en-US"));
  const money = (n) => (n == null || n === 0 ? null : "$" + Number(n).toLocaleString("en-US"));
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const url = (u) => (!u ? "" : /^https?:\/\//i.test(u) ? u : "https://" + u);
  const CIP = { 1: "Agriculture", 3: "Natural resources & conservation", 4: "Architecture & planning", 5: "Area, ethnic & gender studies",
    9: "Communication & journalism", 10: "Communications technology", 11: "Computer & information sciences", 12: "Culinary & personal services",
    13: "Education", 14: "Engineering", 15: "Engineering technology", 16: "Languages & linguistics", 19: "Family & consumer sciences",
    22: "Law", 23: "English", 24: "Liberal arts", 25: "Library science", 26: "Biological & biomedical sciences", 27: "Mathematics & statistics",
    28: "Military science", 29: "Military technologies", 30: "Interdisciplinary studies", 31: "Recreation & kinesiology", 38: "Philosophy & religion",
    39: "Theology", 40: "Physical sciences", 41: "Science technologies", 42: "Psychology", 43: "Criminal justice & security",
    44: "Public administration & social work", 45: "Social sciences", 46: "Construction", 47: "Mechanics & repair", 48: "Precision production",
    49: "Transportation", 50: "Visual & performing arts", 51: "Health professions", 52: "Business & management", 54: "History", 60: "Medical residency" };
  const STATE = { AL: "Alabama", AK: "Alaska", AZ: "Arizona", AR: "Arkansas", CA: "California", CO: "Colorado", CT: "Connecticut", DE: "Delaware",
    DC: "District of Columbia", FL: "Florida", GA: "Georgia", HI: "Hawaii", ID: "Idaho", IL: "Illinois", IN: "Indiana", IA: "Iowa", KS: "Kansas",
    KY: "Kentucky", LA: "Louisiana", ME: "Maine", MD: "Maryland", MA: "Massachusetts", MI: "Michigan", MN: "Minnesota", MS: "Mississippi",
    MO: "Missouri", MT: "Montana", NE: "Nebraska", NV: "Nevada", NH: "New Hampshire", NJ: "New Jersey", NM: "New Mexico", NY: "New York",
    NC: "North Carolina", ND: "North Dakota", OH: "Ohio", OK: "Oklahoma", OR: "Oregon", PA: "Pennsylvania", RI: "Rhode Island", SC: "South Carolina",
    SD: "South Dakota", TN: "Tennessee", TX: "Texas", UT: "Utah", VT: "Vermont", VA: "Virginia", WA: "Washington", WV: "West Virginia",
    WI: "Wisconsin", WY: "Wyoming" };
  // research category from the Carnegie classification
  const CAT = { r1: ["R1 · very high research", "#1d4ed8"], r2: ["R2 · high research", "#0ea5e9"], doc: ["Other doctoral", "#10b981"],
    ms: ["Master's universities", "#f59e0b"], oth: ["Specialized", "#a78bfa"] };
  const catOf = (u) => (u.cc === 15 ? "r1" : u.cc === 16 ? "r2" : u.cc === 17 ? "doc" : u.cc >= 18 && u.cc <= 20 ? "ms" : (u.phd || 0) > 0 ? "doc" : "oth");
  const CTL = { 1: "Public", 2: "Private nonprofit", 3: "Private for-profit" };
  const LOC = (l) => (!l ? "" : l < 20 ? "City" : l < 30 ? "Suburb" : l < 40 ? "Town" : "Rural");
  const TOEFL = { 1: "Required", 2: "Recommended", 3: "Not required", 5: "Considered" };

  box.innerHTML = `<section class="usm">
    <div class="usm-head"><div><h2>🎓 US universities for master's &amp; PhD</h2>
      <p class="sub" id="usmSub">Every US university that awards master's or doctoral degrees · tap a dot or search · application fee, tuition for international students, TOEFL, programs and more</p></div>
      <div class="usm-legend" id="usmLegend"></div></div>
    <div class="usm-bar">
      <div class="usm-search"><input id="usmQ" type="search" placeholder="Search a university or city…" aria-label="Search a US university" autocomplete="off"><div class="usm-sugg" id="usmSugg" hidden></div></div>
      <select id="usmState" aria-label="State"><option value="">All states</option>${Object.entries(STATE).sort((a, b) => a[1].localeCompare(b[1])).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select>
      <select id="usmCat" aria-label="Type"><option value="">All types</option><option value="r1">R1 · very high research</option><option value="r2">R2 · high research</option><option value="doc">Other doctoral</option><option value="ms">Master's universities</option><option value="oth">Specialized</option><option value="phd">Offers PhDs</option></select>
      <select id="usmCtl" aria-label="Public or private"><option value="">Public &amp; private</option><option value="1">Public</option><option value="2">Private nonprofit</option></select>
      <label class="usm-chk"><input type="checkbox" id="usmIntl"> 10%+ international grad students</label>
      <span class="usm-count" id="usmCount"></span></div>
    <div class="usm-grid"><div class="usm-left">
      <div class="usm-map" id="usmMap"><p class="note">Loading the map…</p>
        <div class="usm-zoom"><button type="button" data-z="in" aria-label="Zoom in">+</button><button type="button" data-z="out" aria-label="Zoom out">−</button><button type="button" data-z="reset" aria-label="Reset map">⟲</button></div>
        <div class="usm-tip" id="usmTip" hidden></div></div>
      <div class="usm-ins" id="usmIns"></div></div>
      <aside class="usm-panel" id="usmPanel"><p class="note">Loading universities…</p></aside>
    </div>
    <p class="usm-src" id="usmSrc"></p></section>`;
  const $ = (s) => box.querySelector(s);

  let U = [], META = {}, sel = null, svg, g, zoom, proj, W = 960, H = 600;

  async function load() {
    const [d, topo] = await Promise.all([
      fetch(BASE + "us-unis.json").then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
      fetch("https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-10m.json").then((r) => r.json()).catch(() => null)]);
    META = d;
    U = d.rows.map((r) => Object.fromEntries(d.keys.map((k, i) => [k, r[i]])));
    U.forEach((u) => { u.cat = catOf(u); u.ip = u.ge ? (u.gi || 0) / u.ge : 0; u.key = `${u.n} ${u.alias || ""} ${u.city} ${STATE[u.st] || ""} ${u.st}`.toLowerCase(); });
    const nPhd = U.filter((u) => u.phd > 0).length;
    $("#usmSub").innerHTML = `<b>${fmt(U.length)}</b> US universities that award master's degrees (${fmt(nPhd)} also award PhDs) · tap a dot or search · application fee, tuition for international students, TOEFL, programs and more`;
    $("#usmLegend").innerHTML = Object.values(CAT).map(([l, c]) => `<span><i style="background:${c}"></i>${l}</span>`).join("") + `<span class="muted">· dot size = graduate students</span>`;
    $("#usmSrc").innerHTML = `Source: IPEDS, US Department of Education (directory ${META.years.directory}, tuition ${META.years.tuition}-${String(META.years.tuition + 1).slice(2)}, fees ${META.years.fees}-${String(META.years.fees + 1).slice(2)}); research numbers from OpenAlex. Fees and deadlines change every year — always confirm on the university's website.`;
    drawMap(topo);
    bind();
    filter();
    const want = new URLSearchParams(location.search).get("unitid");
    if (want) { const u = U.find((x) => String(x.id) === want); if (u) select(u, true); }
  }

  function drawMap(topo) {
    const m = $("#usmMap");
    m.querySelector(".note")?.remove();
    W = 960; H = 600;
    proj = d3.geoAlbersUsa().scale(1250).translate([W / 2, H / 2]);
    const path = d3.geoPath(proj);
    svg = d3.select(m).insert("svg", ":first-child").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img").attr("aria-label", "Map of US universities");
    g = svg.append("g");
    if (topo && window.topojson) {
      const states = topojson.feature(topo, topo.objects.states).features;
      g.append("g").attr("class", "usm-states").selectAll("path").data(states).join("path").attr("d", path);
      g.append("path").attr("class", "usm-borders").attr("d", path(topojson.mesh(topo, topo.objects.states, (a, b) => a !== b)));
    }
    const px = W / Math.max(300, m.clientWidth || 800);          // map units per screen pixel
    const rad = d3.scaleSqrt().domain([0, 20000]).range([2.2 * px, 10 * px]).clamp(true);
    U.forEach((u) => { const p = proj([u.lon, u.lat]); u.x = p ? p[0] : null; u.y = p ? p[1] : null; u.r = rad(u.ge || 0); });
    const pts = U.filter((u) => u.x != null).sort((a, b) => b.r - a.r);
    g.append("g").attr("class", "usm-dots").selectAll("circle").data(pts, (u) => u.id).join("circle")
      .attr("cx", (u) => u.x).attr("cy", (u) => u.y).attr("r", (u) => u.r).attr("fill", (u) => CAT[u.cat][1])
      .on("mousemove", (e, u) => tip(e, u)).on("mouseleave", () => ($("#usmTip").hidden = true))
      .on("click", (e, u) => { e.stopPropagation(); select(u); });
    g.append("circle").attr("class", "usm-ring").attr("r", 0);
    zoom = d3.zoom().scaleExtent([1, 14]).translateExtent([[0, 0], [W, H]]).on("zoom", (e) => {
      g.attr("transform", e.transform);
      const k = e.transform.k;
      g.selectAll(".usm-dots circle").attr("r", (u) => u.r / Math.sqrt(k)).attr("stroke-width", 0.6 / k);
      g.selectAll(".usm-states path, .usm-borders").attr("stroke-width", 0.8 / k);
      g.select(".usm-ring").attr("stroke-width", 2.5 / k).attr("r", sel ? (sel.r / Math.sqrt(k)) + 5 / k : 0);
    });
    svg.call(zoom).on("dblclick.zoom", null);
    box.querySelectorAll(".usm-zoom button").forEach((b) => b.addEventListener("click", () => {
      if (b.dataset.z === "reset") svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity);
      else svg.transition().duration(300).call(zoom.scaleBy, b.dataset.z === "in" ? 1.8 : 1 / 1.8);
    }));
  }

  function tip(e, u) {
    const t = $("#usmTip"), r = $("#usmMap").getBoundingClientRect();
    t.innerHTML = `<b>${esc(u.n)}</b><br>${esc(u.city)}, ${u.st} · ${fmt(u.ge)} graduate students${u.gi ? ` · ${Math.round(u.ip * 100)}% international` : ""}`;
    t.hidden = false;
    const x = e.clientX - r.left, y = e.clientY - r.top;
    t.style.left = Math.min(x + 12, r.width - 240) + "px"; t.style.top = (y + 14) + "px";
  }

  function visible(u) {
    const st = $("#usmState").value, c = $("#usmCat").value, ctl = $("#usmCtl").value;
    if (st && u.st !== st) return false;
    if (c === "phd" ? !(u.phd > 0) : c && u.cat !== c) return false;
    if (ctl && String(u.ctl) !== ctl) return false;
    if ($("#usmIntl").checked && !(u.ip >= 0.1 && u.gi >= 20)) return false;
    return true;
  }
  let shown = [];
  function filter() {
    shown = U.filter(visible);
    g && g.selectAll(".usm-dots circle").attr("display", (u) => (visible(u) ? null : "none"));
    $("#usmCount").textContent = `${fmt(shown.length)} universities`;
    const st = $("#usmState").value;
    if (st && svg) zoomToState(st);
    if (!sel) overview();
    insights();
  }
  function zoomToState(st) {
    const pts = U.filter((u) => u.st === st && u.x != null);
    if (!pts.length) return;
    const [x0, x1] = d3.extent(pts, (u) => u.x), [y0, y1] = d3.extent(pts, (u) => u.y);
    const k = Math.max(1, Math.min(10, 0.8 / Math.max((x1 - x0 + 40) / W, (y1 - y0 + 40) / H)));
    svg.transition().duration(600).call(zoom.transform, d3.zoomIdentity.translate(W / 2, H / 2).scale(k).translate(-(x0 + x1) / 2, -(y0 + y1) / 2));
  }

  // panel before a university is chosen: the universities with most international graduate students in the current filter
  function overview() {
    const st = $("#usmState").value;
    const top = shown.slice().sort((a, b) => (b.gi || 0) - (a.gi || 0)).slice(0, 25);
    const fees = shown.map((u) => u.afg).filter((x) => x > 0).sort((a, b) => a - b);
    const tu = shown.map((u) => u.gtu).filter((x) => x > 0).sort((a, b) => a - b);
    const med = (a) => (a.length ? a[Math.floor(a.length / 2)] : null);
    const free = shown.filter((u) => u.afg === 0 || (u.afg == null && false)).length;
    $("#usmPanel").innerHTML = `<h3>${st ? esc(STATE[st]) : "United States"}: quick facts</h3>
      <div class="usm-kpis"><div><span>Universities</span><b>${fmt(shown.length)}</b></div><div><span>Typical grad application fee</span><b>${money(med(fees)) || "—"}</b></div>
        <div><span>Typical grad tuition / year</span><b>${money(med(tu)) || "—"}</b></div><div><span>International grad students</span><b>${fmt(shown.reduce((s, u) => s + (u.gi || 0), 0))}</b></div></div>
      <h4>Most international graduate students${st ? "" : " in the US"}</h4>
      <ol class="usm-top">${top.map((u) => `<li><button type="button" data-id="${u.id}"><b>${esc(u.n)}</b><span>${esc(u.city)}, ${u.st} · ${fmt(u.gi)} international (${Math.round(u.ip * 100)}%)</span></button></li>`).join("")}</ol>
      <p class="note">Tap any dot on the map, or search above, to see application fees, tuition, programs and links.</p>`;
    $("#usmPanel").querySelectorAll("[data-id]").forEach((b) => b.addEventListener("click", () => select(U.find((u) => String(u.id) === b.dataset.id), true)));
  }

  // cards under the map: quick lists for the current filter (and universities near the one selected)
  const miles = (a, b) => { const R = 3959, r = Math.PI / 180, dLa = (b.lat - a.lat) * r, dLo = (b.lon - a.lon) * r;
    const h = Math.sin(dLa / 2) ** 2 + Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin(dLo / 2) ** 2; return 2 * R * Math.asin(Math.sqrt(h)); };
  function card(icon, title, note, list, val) {
    if (!list.length) return "";
    return `<div class="usm-card"><h4>${icon} ${title}</h4>${note ? `<p class="usm-cnote">${note}</p>` : ""}<ol>${list.map((u) =>
      `<li><button type="button" data-id="${u.id}"><span class="nm">${esc(u.n)}<small>${esc(u.city)}, ${u.st}</small></span><b>${val(u)}</b></button></li>`).join("")}</ol></div>`;
  }
  function insights() {
    const el = $("#usmIns"); if (!el) return;
    const st = $("#usmState").value, where = st ? ` in ${STATE[st]}` : "";
    const L = shown, cards = [];
    if (sel) {
      const near = U.filter((u) => u !== sel && visible(u)).map((u) => [u, miles(sel, u)]).filter(([, d]) => d <= 100).sort((a, b) => a[1] - b[1]).slice(0, 5);
      if (near.length) cards.push(card("📍", `Near ${esc(sel.alias ? sel.alias.split(/[|,]/)[0] : sel.n)}`, "Other universities within 100 miles", near.map(([u, d]) => Object.assign(Object.create(u), { _d: d })),
        (u) => `${Math.round(u._d)} mi`));
    }
    const research = (arr) => { const r = arr.filter((u) => u.cat === "r1" || u.cat === "r2"); return r.length >= 5 ? [r, true] : [arr.filter((u) => u.phd > 0), false]; };
    const [rt, isR] = research(L.filter((u) => u.gtu > 0));
    cards.push(card("💰", `Lowest graduate tuition${where}`, isR ? "Research universities (R1 & R2), per year" : "Universities with PhD programs, per year",
      rt.slice().sort((a, b) => a.gtu - b.gtu).slice(0, 5), (u) => money(u.gtu)));
    const free = L.filter((u) => u.afg === 0), [rf, isRf] = research(free);
    cards.push(card("🆓", `No graduate application fee${where}`, `${fmt(free.length)} universities charge no fee — ${isRf ? "research universities" : "the biggest"}:`,
      (rf.length ? rf : free).slice().sort((a, b) => (b.ge || 0) - (a.ge || 0)).slice(0, 5), (u) => `${fmt(u.ge)} grads`));
    if (!sel) {
      const [ri, isRi] = research(L.filter((u) => (u.ge || 0) >= 300));
      cards.push(card("🌍", `Highest share of international students${where}`, isRi ? "Research universities (R1 & R2), graduate students" : "Graduate students",
        ri.slice().sort((a, b) => b.ip - a.ip).slice(0, 5), (u) => `${Math.round(u.ip * 100)}%`));
    }
    if (!st) {
      const by = {};
      L.forEach((u) => { by[u.st] = (by[u.st] || 0) + (u.gi || 0); });
      const top = Object.entries(by).sort((a, b) => b[1] - a[1]).slice(0, 7), mx = top.length ? top[0][1] : 1;
      cards.push(`<div class="usm-card"><h4>🗺️ States with most international grad students</h4><p class="usm-cnote">Tap a state to explore it</p>
        <div class="usm-sbars">${top.map(([k, v]) => `<button type="button" data-st="${k}"><span>${esc(STATE[k])}</span><i style="width:${Math.max(4, Math.round(v / mx * 100))}%"></i><b>${fmt(v)}</b></button>`).join("")}</div></div>`);
    } else {
      cards.push(card("🎓", `Most PhDs awarded${where}`, "Research doctorates per year",
        L.filter((u) => u.phd > 0).sort((a, b) => b.phd - a.phd).slice(0, 5), (u) => fmt(u.phd)));
    }
    el.innerHTML = cards.filter(Boolean).join("");
    el.querySelectorAll("[data-id]").forEach((b) => b.addEventListener("click", () => select(U.find((u) => String(u.id) === b.dataset.id), true)));
    el.querySelectorAll("[data-st]").forEach((b) => b.addEventListener("click", () => { $("#usmState").value = b.dataset.st; $("#usmState").dispatchEvent(new Event("input")); }));
    fit();
  }
  // the details panel is as tall as the map + cards, so the two columns end together
  function fit() {
    const p = $("#usmPanel"), l = $(".usm-left");
    p.style.maxHeight = window.innerWidth > 900 ? l.offsetHeight + "px" : "";
  }
  window.addEventListener("resize", () => { clearTimeout(fit.t); fit.t = setTimeout(fit, 200); });

  function select(u, fly) {
    if (!u) return;
    sel = u;
    const k = d3.zoomTransform(svg.node()).k;
    g.select(".usm-ring").attr("cx", u.x).attr("cy", u.y).attr("r", u.r / Math.sqrt(k) + 5 / k).attr("stroke-width", 2.5 / k);
    if (fly && u.x != null) {
      const kk = Math.max(k, 4);
      svg.transition().duration(700).call(zoom.transform, d3.zoomIdentity.translate(W / 2, H / 2).scale(kk).translate(-u.x, -u.y));
    }
    details(u);
    insights();
    if (window.innerWidth < 900) $("#usmPanel").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function bars(list) {
    if (!list || !list.length) return `<p class="note">No degrees reported.</p>`;
    const mx = list[0][1];
    return `<div class="usm-bars">${list.map(([c, n]) => `<div><span>${esc(CIP[c] || "Other")}</span><i style="width:${Math.max(4, Math.round(n / mx * 100))}%"></i><b>${fmt(n)}</b></div>`).join("")}</div>`;
  }
  function tile(label, value, sub) {
    return `<div><span>${label}</span><b>${value == null || value === "" ? "—" : value}</b>${sub ? `<em>${sub}</em>` : ""}</div>`;
  }

  function details(u) {
    const cost = u.gtu ? u.gtu + (u.rb || 0) : null;
    const badges = [CAT[u.cat][0], CTL[u.ctl], u.hbcu ? "HBCU" : "", u.lg ? "Land-grant" : "", LOC(u.loc)].filter(Boolean);
    const links = [[u.app, "Apply ↗", "primary"], [u.web, "Website ↗"], [u.aid, "Financial aid ↗"], [u.np, "Cost calculator ↗"],
      [`https://nces.ed.gov/collegenavigator/?id=${u.id}`, "Official profile ↗"]].filter((x) => x[0]);
    $("#usmPanel").innerHTML = `<button type="button" class="usm-back" id="usmBack">← All universities</button>
      <h3>${esc(u.n)}</h3><p class="usm-where">${esc(u.city)}, ${esc(STATE[u.st] || u.st)}${u.alias ? ` · also known as ${esc(u.alias.split("|")[0].split(",")[0])}` : ""}</p>
      <div class="usm-badges">${badges.map((b, i) => `<span${i === 0 ? ` style="background:${CAT[u.cat][1]};color:#fff"` : ""}>${esc(b)}</span>`).join("")}</div>
      <div class="usm-links">${links.map(([h, l, c]) => `<a href="${esc(url(h))}" target="_blank" rel="noopener"${c ? ` class="${c}"` : ""}>${l}</a>`).join("")}</div>
      <h4>For international graduate students</h4>
      <div class="usm-kpis">
        ${tile("Graduate application fee", u.afg === 0 ? "No fee" : money(u.afg))}
        ${tile("Graduate tuition / year", money(u.gtu), u.ctl === 1 ? "out-of-state rate" : "full-time")}
        ${tile("Estimated cost / year", money(cost), cost ? "tuition + room & board" : "")}
        ${tile("International grad students", u.gi != null ? fmt(u.gi) : null, u.ge ? `${Math.round(u.ip * 100)}% of ${fmt(u.ge)}` : "")}
        ${tile("Master's degrees / year", fmt(u.ms || 0))}
        ${tile("PhDs / year", fmt(u.phd || 0), u.prof ? `+ ${fmt(u.prof)} professional doctorates` : "")}
        ${tile("Room &amp; board / year", money(u.rb))}
        ${tile("Student–faculty ratio", u.sfr ? `${u.sfr} : 1` : null)}
      </div>
      <h4>Top master's programs <small>(degrees per year)</small></h4>${bars(u.mf)}
      ${u.phd ? `<h4>Top PhD fields <small>(PhDs per year)</small></h4>${bars(u.pf)}` : ""}
      <h4>Undergraduate</h4>
      <div class="usm-kpis small">
        ${tile("Application fee", u.afu === 0 ? "No fee" : money(u.afu))}
        ${tile("Tuition / year", money(u.utu), u.ctl === 1 ? "out-of-state rate" : "")}
        ${tile("Acceptance rate", u.ar != null ? Math.round(u.ar * 100) + "%" : null)}
        ${tile("TOEFL / English test", TOEFL[u.toefl] || null)}
      </div>
      <h4>Research</h4><div id="usmOA" class="usm-oa"><p class="note">Loading research output…</p></div>`;
    $("#usmBack").addEventListener("click", () => { sel = null; g.select(".usm-ring").attr("r", 0); overview(); insights(); });
    research(u);
  }

  // research output from OpenAlex (matched by name and state)
  const oaCache = {};
  async function research(u) {
    const el = () => $("#usmOA");
    try {
      let inst = oaCache[u.id];
      if (inst === undefined) {
        const clean = u.n.replace(/-(Main Campus|Main|Campus).*$/i, "").replace(/\s*-\s*/g, " ").replace(/[^\w\s&'.]/g, " ").trim();
        const r = await fetch(`https://api.openalex.org/institutions?search=${encodeURIComponent(clean)}&filter=country_code:US&per_page=5&mailto=researchboardlive@gmail.com`).then((x) => x.json());
        const city = (u.city || "").toLowerCase();
        inst = (r.results || []).find((x) => ((x.geo || {}).city || "").toLowerCase() === city) || (r.results || [])[0] || null;
        oaCache[u.id] = inst;
      }
      if (sel !== u || !el()) return;
      if (!inst) { el().innerHTML = `<p class="note">No research profile found.</p>`; return; }
      const id = String(inst.id).split("/").pop(), s = inst.summary_stats || {};
      el().innerHTML = `<div class="usm-kpis small">${tile("Research papers", fmt(inst.works_count))}${tile("Citations", fmt(inst.cited_by_count))}${tile("h-index", fmt(s.h_index))}${tile("Papers last year", fmt(((inst.counts_by_year || []).find((c) => c.year === new Date().getFullYear() - 1) || {}).works_count))}</div>
        <div class="usm-links"><a href="${SITE}university/?id=${id}">Research profile →</a><a href="${SITE}scientists/?i=${id}&in=${encodeURIComponent(inst.display_name)}">Find professors &amp; supervisors →</a></div>
        <p class="note">Matched to “${esc(inst.display_name)}” in OpenAlex.</p>`;
    } catch (e) {
      if (el()) el().innerHTML = `<p class="note">Research numbers could not be loaded right now.</p>`;
    }
  }

  function bind() {
    const q = $("#usmQ"), sg = $("#usmSugg");
    let hits = [];
    const run = () => {
      const t = q.value.trim().toLowerCase();
      if (t.length < 2) { sg.hidden = true; return; }
      const words = t.split(/\s+/);
      hits = U.filter((u) => words.every((w) => u.key.includes(w))).sort((a, b) => (b.n.toLowerCase().startsWith(t) - a.n.toLowerCase().startsWith(t)) || (b.ge || 0) - (a.ge || 0)).slice(0, 8);
      sg.innerHTML = hits.length ? hits.map((u, i) => `<button type="button" data-i="${i}"><b>${esc(u.n)}</b><span>${esc(u.city)}, ${u.st}</span></button>`).join("") : `<p class="note">No university found.</p>`;
      sg.hidden = false;
      sg.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { pick(hits[+b.dataset.i]); }));
    };
    const pick = (u) => { if (!u) return; sg.hidden = true; q.value = u.n; select(u, true); };
    q.addEventListener("input", run);
    q.addEventListener("focus", run);
    q.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); run(); pick(hits[0]); } if (e.key === "Escape") sg.hidden = true; });
    document.addEventListener("click", (e) => { if (!$(".usm-search").contains(e.target)) sg.hidden = true; });
    ["#usmState", "#usmCat", "#usmCtl", "#usmIntl"].forEach((k) => $(k).addEventListener("input", () => {
      if (k !== "#usmState" || !$("#usmState").value) { if (k === "#usmState") svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity); }
      if (sel && !visible(sel)) { sel = null; g.select(".usm-ring").attr("r", 0); }
      filter();
    }));
  }

  // start when the section comes near the screen (keeps the homepage fast)
  const start = () => load().catch((e) => { $("#usmPanel").innerHTML = `<p class="note">The university map could not be loaded (${esc(e.message)}).</p>`; });
  const waitD3 = () => (window.d3 ? start() : setTimeout(waitD3, 200));
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((en) => { if (en.some((x) => x.isIntersecting)) { io.disconnect(); waitD3(); } }, { rootMargin: "600px" });
    io.observe(box);
  } else waitD3();
})();
