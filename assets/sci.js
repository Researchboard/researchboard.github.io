/* Scientist finder on /scientists/ — searches OpenAlex live.
   Filters: name, topic (find a supervisor), country, research field, institution, sort. State lives in the URL. */
(function () {
  const box = document.getElementById("sci");
  if (!box) return;
  const OA = "https://api.openalex.org/";
  const MAILTO = "mailto=researchboardlive@gmail.com";
  const BLOCK_INST = new Set(["I4210096394"]);   // OpenAlex places this one in the wrong country
  const FIELDS = [["11", "Agricultural and Biological Sciences"], ["12", "Arts and Humanities"], ["13", "Biochemistry, Genetics and Molecular Biology"],
    ["14", "Business, Management and Accounting"], ["15", "Chemical Engineering"], ["16", "Chemistry"], ["17", "Computer Science"], ["18", "Decision Sciences"],
    ["19", "Earth and Planetary Sciences"], ["20", "Economics, Econometrics and Finance"], ["21", "Energy"], ["22", "Engineering"], ["23", "Environmental Science"],
    ["24", "Immunology and Microbiology"], ["25", "Materials Science"], ["26", "Mathematics"], ["27", "Medicine"], ["28", "Neuroscience"], ["29", "Nursing"],
    ["30", "Pharmacology, Toxicology and Pharmaceutics"], ["31", "Physics and Astronomy"], ["32", "Psychology"], ["33", "Social Sciences"], ["34", "Veterinary"],
    ["35", "Dentistry"], ["36", "Health Professions"]];
  const FNAME = Object.fromEntries(FIELDS);
  const YEAR = new Date().getFullYear(), Y5 = [0, 1, 2, 3, 4].map((k) => YEAR - k);
  const FROM5 = `${YEAR - 4}-01-01`;
  const $ = (s) => box.querySelector(s);
  const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString("en-US"));
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const sid = (u) => String(u || "").split("/").pop();
  const flag = (c) => (c ? `<span class="fi fi-${String(c).toLowerCase()}"></span>` : "");
  const get = (p) => fetch(OA + p + (p.includes("?") ? "&" : "?") + MAILTO).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
  const dn = (() => { try { return new Intl.DisplayNames(["en"], { type: "region" }); } catch (_) { return null; } })();
  const cname = (c) => { try { return (dn && dn.of(c)) || c; } catch (_) { return c; } };

  // ------------------------------------------------------------------ state <-> URL
  const P = new URLSearchParams(location.search);
  const st = { mode: P.get("mode") === "topic" ? "topic" : "name", q: P.get("q") || "", c: (P.get("c") || "").toUpperCase(),
    f: P.get("f") || "", i: P.get("i") || "", iname: P.get("in") || "", s: P.get("s") || "cited_by_count", page: 1 };
  if (!["cited_by_count", "c5", "summary_stats.h_index", "summary_stats.i10_index"].includes(st.s)) st.s = "cited_by_count";
  const METRICS = [
    ["cited_by_count", "Citations", "total influence", "How many times other research papers have cited this scientist's work, across the whole career."],
    ["c5", `Citations ${YEAR - 4}–${YEAR}`, "recent impact", `Citations received in ${YEAR - 4}–${YEAR} only. Shows who is influential now, and is fairer to younger researchers.`],
    ["summary_stats.h_index", "h-index", "impact depth", "A scientist has an h-index of 40 when 40 of their papers have each been cited at least 40 times."],
    ["summary_stats.i10_index", "i10-index", "consistent output", "The number of papers that have each been cited at least 10 times."]];
  function pushURL() {
    const u = new URL(location.href);
    ["mode", "q", "c", "f", "i", "in", "s"].forEach((k) => u.searchParams.delete(k));
    if (st.q) u.searchParams.set("q", st.q);
    if (st.mode === "topic") u.searchParams.set("mode", "topic");
    if (st.c) u.searchParams.set("c", st.c);
    if (st.f) u.searchParams.set("f", st.f);
    if (st.i) { u.searchParams.set("i", st.i); u.searchParams.set("in", st.iname); }
    if (st.s !== "cited_by_count") u.searchParams.set("s", st.s);
    try { history.replaceState(null, "", u); } catch (_) {}
  }

  // ------------------------------------------------------------------ controls
  const loadedAt = new Date().toLocaleString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
  box.innerHTML = `
    <div class="sh">
      <h2 class="sh-t"><span id="hWhere">World</span> <em id="hN">…</em> Scientists <span class="sh-m" id="hMetric">Citations</span> Rankings</h2>
      <div class="sh-badges"><span class="sh-live">● Live · data loaded ${esc(loadedAt)}</span><span class="sh-pill">Career &amp; last 5 years</span></div>
      <p class="sh-p">Live rankings of researchers <span id="hScope">worldwide</span>, built from <b>OpenAlex</b> — the free, open index of over 250 million
        research papers, which also covers PubMed. <b>Career totals and the last 5 years are shown side by side, never mixed.</b>
        Filter by country, research field or university, or search a name or topic.</p>
      <div class="sh-tabs">${METRICS.map(([k, n, sub, tip]) => `<button data-s="${k}" title="${esc(tip)}"><b>${esc(n)}</b> <span>${esc(sub)}</span> <i aria-hidden="true">i</i></button>`).join("")}</div>
      <p class="sh-explain" id="hExplain"></p>
      <p class="sh-src"><b>Source &amp; scale:</b> OpenAlex open data, refreshed daily · scientists with 3+ papers and at least one paper since ${YEAR - 4} ·
        numbers are usually <b>lower than Google Scholar-based rankings</b> (which also count theses, slides and duplicate copies) and <b>higher than Scopus or Web of Science</b> (which count selected journals only). <a href="../about/methods.html">How we count →</a></p>
    </div>
    <div class="sf">
      <div class="sf-mode" role="tablist"><button data-m="name">👤 Name</button><button data-m="topic">🔎 Topic (find a supervisor)</button></div>
      <div class="sf-row">
        <div class="sf-q"><input id="sQ" type="search" autocomplete="off" aria-label="Search"><div class="sf-drop" id="sQd" hidden></div></div>
        <select id="sC" aria-label="Country"><option value="">🌍 All countries</option></select>
        <select id="sF" aria-label="Research field"><option value="">All research fields</option>${FIELDS.slice().sort((a, b) => a[1].localeCompare(b[1])).map(([k, n]) => `<option value="${k}">${esc(n)}</option>`).join("")}</select>
        <div class="sf-q"><input id="sI" type="search" autocomplete="off" placeholder="University or institute…" aria-label="Institution"><div class="sf-drop" id="sId" hidden></div></div>
        <button class="sf-go" id="sGo">Search</button>
      </div>
      <div class="sf-chips" id="sChips"></div>
    </div>
    <div class="sci-grid"><section class="panel2"><h2 id="sTitle">Scientists</h2><p class="note" id="sInfo"></p>
      <div class="sci-wrap"><table class="rt sci"><thead><tr><th>#</th><th>Scientist</th><th class="hm">Main topic</th>
        <th class="r" id="sCol5">Papers (5 yrs)</th><th class="r" data-col="cited_by_count">Citations</th><th class="r" data-col="c5">Citations<br>${YEAR - 4}–${String(YEAR).slice(2)}</th><th class="r" data-col="summary_stats.h_index">h-index</th><th class="r hm" data-col="summary_stats.i10_index">i10</th></tr></thead><tbody id="sBody"></tbody></table></div>
      <button class="ud-more" id="sMore" hidden>Load more</button>
      <p class="note">Data: OpenAlex, live. Only scientists with a paper in ${YEAR - 4}–${YEAR} are shown. A few profiles in OpenAlex mix up two people with the same name or list an old university.</p></section>
      <aside id="sSide"></aside></div>`;
  const C = $("#sC");
  fetch("../data/latest.json").then((r) => r.json()).then((l) => {
    const names = l.country_names || {};
    const codes = Object.keys(names).length ? Object.keys(names) : [];
    const all = [...new Set(codes.concat(st.c ? [st.c] : []))].map((c) => [c, names[c] || cname(c)]).sort((a, b) => a[1].localeCompare(b[1]));
    C.innerHTML = `<option value="">🌍 All countries</option>` + all.map(([c, n]) => `<option value="${c}">${esc(n)}</option>`).join("");
    C.value = st.c;
  }).catch(() => { if (st.c) C.innerHTML += `<option value="${st.c}">${esc(cname(st.c))}</option>`; C.value = st.c; });
  $("#sQ").value = st.q; $("#sF").value = st.f; $("#sI").value = st.iname;
  function setMetric(k) {
    st.s = k;
    const m = METRICS.find((x) => x[0] === k);
    box.querySelectorAll(".sh-tabs button").forEach((b) => b.classList.toggle("on", b.dataset.s === k));
    box.querySelectorAll("th[data-col]").forEach((th) => th.classList.toggle("on", th.dataset.col === k));
    $("#hMetric").textContent = m[1].startsWith("Citations ") ? "Recent Citations" : m[1];
    $("#hExplain").innerHTML = `<b>${esc(m[1])}:</b> ${esc(m[3])}`;
  }
  setMetric(st.s);
  box.querySelectorAll(".sh-tabs button").forEach((b) => b.addEventListener("click", () => { setMetric(b.dataset.s); run(); }));
  function setMode(m) {
    st.mode = m;
    box.querySelectorAll(".sf-mode button").forEach((b) => b.classList.toggle("on", b.dataset.m === m));
    $("#sQ").placeholder = m === "topic" ? 'A research topic, e.g. "arsenic groundwater", "dengue", "solar cells"' : 'A scientist\'s name, e.g. "Firdausi Qadri"';
  }
  setMode(st.mode);
  box.querySelectorAll(".sf-mode button").forEach((b) => b.addEventListener("click", () => { setMode(b.dataset.m); if (st.q) run(); }));

  // autocomplete: names and institutions
  function auto(input, drop, kind, onPick) {
    let t = null;
    input.addEventListener("input", () => {
      clearTimeout(t);
      const q = input.value.trim();
      if (kind === "authors" && st.mode !== "name") { drop.hidden = true; return; }
      if (q.length < 3) { drop.hidden = true; if (kind === "institutions" && !q) { st.i = ""; st.iname = ""; } return; }
      t = setTimeout(async () => {
        try {
          const r = await get(`autocomplete/${kind}?q=${encodeURIComponent(q)}`);
          drop.innerHTML = (r.results || []).slice(0, 8).map((x) => `<button data-id="${sid(x.id)}" data-n="${esc(x.display_name)}">${esc(x.display_name)}<span>${esc(x.hint || "")}</span></button>`).join("");
          drop.hidden = !drop.innerHTML;
        } catch (_) { drop.hidden = true; }
      }, 220);
    });
    drop.addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; drop.hidden = true; onPick(b.dataset.id, b.dataset.n); });
    document.addEventListener("click", (e) => { if (!drop.contains(e.target) && e.target !== input) drop.hidden = true; });
  }
  auto($("#sQ"), $("#sQd"), "authors", (id) => { location.href = `../scientist/?id=${id}`; });
  auto($("#sI"), $("#sId"), "institutions", (id, n) => { st.i = id; st.iname = n; $("#sI").value = n; run(); });
  const go = () => { st.q = $("#sQ").value.trim(); st.c = C.value; st.f = $("#sF").value; if (!$("#sI").value.trim()) { st.i = ""; st.iname = ""; } run(); };
  $("#sGo").addEventListener("click", go);
  $("#sQ").addEventListener("keydown", (e) => { if (e.key === "Enter") { $("#sQd").hidden = true; go(); } });
  [C, $("#sF")].forEach((el) => el.addEventListener("change", go));
  $("#sMore").addEventListener("click", () => { st.page += 1; run(true); });

  // ------------------------------------------------------------------ search
  const cites5 = (a) => { const c = Object.fromEntries((a.counts_by_year || []).map((z) => [z.year, z.cited_by_count])); return Y5.reduce((s, y) => s + (c[y] || 0), 0); };
  const recent5 = (a) => { const c = Object.fromEntries((a.counts_by_year || []).map((z) => [z.year, z.works_count])); return Y5.reduce((s, y) => s + (c[y] || 0), 0); };
  function okAuthor(a) {
    const L = (a.last_known_institutions || []).filter((i) => !BLOCK_INST.has(sid(i.id)));
    if ((a.last_known_institutions || []).length > 8) return false;     // usually several people merged into one profile
    if (st.c && L.length && L.filter((i) => (i.country_code || "").toUpperCase() === st.c).length < L.length / 2) return false;
    if (st.c && !L.length) return false;
    return recent5(a) > 0;
  }
  function instOf(a) {
    const L = (a.last_known_institutions || []).filter((i) => !BLOCK_INST.has(sid(i.id)));
    const pick = (st.c && L.find((i) => (i.country_code || "").toUpperCase() === st.c)) || L[0];
    return pick ? `<a href="../university/?id=${sid(pick.id)}">${esc(pick.display_name)}</a>${st.c ? "" : " " + flag(pick.country_code)}` : "—";
  }
  const SEL = "id,display_name,orcid,last_known_institutions,topics,counts_by_year,summary_stats,works_count,cited_by_count";
  let shownRows = 0, loaded = [];
  function row(a, extra) {
    const t = (a.topics || [])[0];
    return `<tr><td>${++shownRows}</td><td class="nm"><a href="../scientist/?id=${sid(a.id)}"><b>${esc(a.display_name)}</b></a>${a.orcid ? ` <a class="orc" href="${esc(a.orcid)}" target="_blank" rel="noopener" title="ORCID iD">iD</a>` : ""}
      <div class="ud-city">${instOf(a)}</div></td><td class="hm"><span class="muted">${t ? esc(t.display_name) : "—"}</span>${t ? `<div class="ud-city">${esc(t.field.display_name)}</div>` : ""}</td>
      <td class="r">${extra != null ? `<b>${fmt(extra)}</b><div class="ud-city">on topic</div>` : fmt(recent5(a))}</td><td class="r${st.s === "cited_by_count" ? " on" : ""}">${fmt(a.cited_by_count)}</td><td class="r${st.s === "c5" ? " on" : ""}">${fmt(cites5(a))}</td>
      <td class="r${st.s.includes("h_index") ? " on" : ""}">${fmt((a.summary_stats || {}).h_index)}</td><td class="r hm${st.s.includes("i10") ? " on" : ""}">${fmt((a.summary_stats || {}).i10_index)}</td></tr>`;
  }
  function chips() {
    const c = [];
    if (st.q) c.push([st.mode === "topic" ? `Topic: ${st.q}` : `Name: ${st.q}`, "q"]);
    if (st.c) c.push([`${cname(st.c)}`, "c"]);
    if (st.f) c.push([FNAME[st.f], "f"]);
    if (st.i) c.push([st.iname, "i"]);
    $("#sChips").innerHTML = c.map(([t, k]) => `<button data-k="${k}">${esc(t)} ✕</button>`).join("") + (c.length ? `<button data-k="all" class="clr">Clear all</button>` : "");
    $("#sChips").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
      const k = b.dataset.k;
      if (k === "q" || k === "all") { st.q = ""; $("#sQ").value = ""; }
      if (k === "c" || k === "all") { st.c = ""; C.value = ""; }
      if (k === "f" || k === "all") { st.f = ""; $("#sF").value = ""; }
      if (k === "i" || k === "all") { st.i = ""; st.iname = ""; $("#sI").value = ""; }
      run();
    }));
  }
  function title() {
    const parts = [st.f ? FNAME[st.f] : "", st.mode === "topic" && st.q ? `“${st.q}”` : ""].filter(Boolean).join(" · ");
    const where = st.i ? `at ${st.iname}` : st.c ? `in ${cname(st.c)}` : "worldwide";
    return `${st.mode === "topic" && st.q ? "Who publishes on" : "Active scientists"} ${parts ? parts + " " : ""}${where}`;
  }

  let token = 0;
  async function run(more) {
    const my = ++token;
    if (!more) { st.page = 1; shownRows = 0; $("#sBody").innerHTML = `<tr><td colspan="8">Searching…</td></tr>`; }
    pushURL(); chips();
    $("#sTitle").textContent = title();
    $("#hWhere").textContent = st.i ? st.iname : st.c ? cname(st.c) : "World";
    $("#hScope").textContent = st.i ? "at " + st.iname : st.c ? "in " + cname(st.c) : "worldwide";
    if (!more) $("#hN").textContent = "…";
    $("#sCol5").textContent = st.mode === "topic" && st.q ? "Papers on topic" : `Papers (${YEAR - 4}–${YEAR})`;
    try {
      if (st.mode === "topic" && st.q) await runTopic(my, more);
      else await runAuthors(my, more);
    } catch (e) {
      if (my === token) $("#sBody").innerHTML = `<tr><td colspan="8">OpenAlex didn't answer just now. Please try again in a minute.</td></tr>`;
    }
    if (!more) side(my);
  }

  async function runAuthors(my, more) {
    const f = ["works_count:>2"];
    if (st.c) f.push(`last_known_institutions.country_code:${st.c}`);
    if (st.i) f.push(`last_known_institutions.id:${st.i}`);
    if (st.f) f.push(`topics.field.id:fields/${st.f}`);
    const q = st.q && st.mode === "name" ? `&search=${encodeURIComponent(st.q)}` : "";
    // OpenAlex sorts by career citations, h-index and i10; "last 5 years" is sorted here among the most-cited loaded so far
    const sort = `&sort=${st.s === "c5" ? "cited_by_count" : st.s}:desc`;
    const per = st.s === "c5" ? 200 : 50;
    const r = await get(`authors?filter=${f.join(",")}${q}${sort}&per_page=${per}&page=${st.page}&select=${SEL}`);
    if (my !== token) return;
    if (!more) loaded = [];
    loaded = loaded.concat((r.results || []).filter(okAuthor));
    const list = st.s === "c5" ? loaded.slice().sort((x, y) => cites5(y) - cites5(x)) : loaded;
    shownRows = 0;
    $("#sBody").innerHTML = list.map((a) => row(a)).join("") || `<tr><td colspan="8">No active scientists found. Try fewer filters or another spelling.</td></tr>`;
    const total = (r.meta || {}).count || 0;
    $("#hN").textContent = fmt(total);
    const mname = METRICS.find((x) => x[0] === st.s)[1];
    $("#sInfo").textContent = st.s === "c5"
      ? `${fmt(total)} scientist profiles match. Ranked by ${mname} among the ${fmt(st.page * per)} most-cited — load more to look deeper.`
      : `${fmt(total)} scientist profiles match. Showing the active ones, ranked by ${mname}.`;
    $("#sMore").hidden = st.page * per >= total || st.page >= (st.s === "c5" ? 5 : 20);
  }

  let topicIds = [];
  async function runTopic(my, more) {
    if (!more) {
      const f = [`from_publication_date:${FROM5}`, "type:article|review|preprint"];
      if (st.c) f.push(`authorships.institutions.country_code:${st.c}`);
      if (st.i) f.push(`authorships.institutions.lineage:${st.i}`);
      if (st.f) f.push(`primary_topic.field.id:fields/${st.f}`);
      const g = await get(`works?search=${encodeURIComponent(st.q)}&filter=${f.join(",")}&group_by=authorships.author.id`);
      if (my !== token) return;
      topicIds = (g.group_by || []).filter((x) => x.key && x.count > 0).map((x) => [sid(x.key), x.count]);
      $("#hN").textContent = fmt(topicIds.length) + (topicIds.length >= 200 ? "+" : "");
      const n = (g.meta || {}).count;
      $("#sInfo").textContent = `${fmt(n)} papers on this topic since ${YEAR - 4}${st.c ? " with an author in " + cname(st.c) : ""}. Researchers ranked by how many of them they wrote.`;
    }
    const slice = topicIds.slice((st.page - 1) * 40, st.page * 40);
    if (!slice.length) { if (!more) $("#sBody").innerHTML = `<tr><td colspan="8">No papers found on this topic. Try a broader word.</td></tr>`; $("#sMore").hidden = true; return; }
    const r = await get(`authors?filter=openalex:${slice.map((x) => x[0]).join("|")}&per_page=50&select=${SEL}`);
    if (my !== token) return;
    const byId = Object.fromEntries((r.results || []).map((a) => [sid(a.id), a]));
    const inCountry = (a) => !st.c || (a.last_known_institutions || []).some((i) => (i.country_code || "").toUpperCase() === st.c && !BLOCK_INST.has(sid(i.id)));
    const html = slice.map(([id, n]) => { const a = byId[id]; return a && (a.last_known_institutions || []).length <= 8 && inCountry(a) ? row(a, n) : ""; }).join("");
    if (more) $("#sBody").insertAdjacentHTML("beforeend", html); else $("#sBody").innerHTML = html;
    $("#sMore").hidden = st.page * 40 >= topicIds.length;
  }

  async function side(my) {
    const S = $("#sSide");
    if (st.mode === "topic" && st.q) {
      try {
        const f = [`from_publication_date:${FROM5}`, "type:article|review|preprint"];
        if (st.c) f.push(`authorships.institutions.country_code:${st.c}`);
        if (st.f) f.push(`primary_topic.field.id:fields/${st.f}`);
        const g = await get(`works?search=${encodeURIComponent(st.q)}&filter=${f.join(",")}&group_by=authorships.institutions.lineage`);
        if (my !== token) return;
        S.innerHTML = `<section class="panel2"><h2>Institutions working on it</h2><table class="rt"><tbody>${(g.group_by || []).filter((x) => !BLOCK_INST.has(sid(x.key))).slice(0, 10).map((x) =>
          `<tr><td><a href="#" data-i="${sid(x.key)}" data-n="${esc(x.key_display_name)}">${esc(x.key_display_name)}</a></td><td class="r">${fmt(x.count)}</td></tr>`).join("")}</tbody></table>
          <p class="note">Click to see only that institution.</p></section>` + tip();
      } catch (_) { S.innerHTML = tip(); }
    } else {
      try {
        const f = ["works_count:>4"];
        if (st.c) f.push(`last_known_institutions.country_code:${st.c}`);
        if (st.i) f.push(`last_known_institutions.id:${st.i}`);
        const [gf, gi] = await Promise.all([get(`authors?filter=${f.join(",")}&group_by=topics.field.id`),
          st.i ? Promise.resolve(null) : get(`authors?filter=${f.concat(st.f ? [`topics.field.id:fields/${st.f}`] : []).join(",")}&group_by=last_known_institutions.id`)]);
        if (my !== token) return;
        if (gi && st.c) {   // keep institutions that are really in the chosen country
          const ids = (gi.group_by || []).slice(0, 16).map((x) => sid(x.key)).filter(Boolean);
          try {
            const r = await get(`institutions?filter=openalex:${ids.join("|")}&per_page=50&select=id,country_code`);
            const ok = new Set((r.results || []).filter((x) => (x.country_code || "").toUpperCase() === st.c).map((x) => sid(x.id)));
            gi.group_by = gi.group_by.filter((x) => ok.has(sid(x.key)));
          } catch (_) {}
          if (my !== token) return;
        }
        const fl = (gf.group_by || []).slice(0, 10), mx = Math.max(1, ...fl.map((x) => x.count));
        S.innerHTML = `<section class="panel2"><h2>Fields${st.i ? " here" : st.c ? " in " + esc(cname(st.c)) : ""}</h2>${fl.map((x) =>
          `<a class="sb" href="#" data-f="${sid(x.key)}"><span>${esc(x.key_display_name)}</span><i style="width:${x.count / mx * 90}px"></i><b>${fmt(x.count)}</b></a>`).join("")}
          <p class="note">Scientists with 5+ papers. One person can work in several fields. Click to filter.</p></section>` +
          (gi ? `<section class="panel2"><h2>Most scientists by institution</h2><table class="rt"><tbody>${(gi.group_by || []).filter((x) => !BLOCK_INST.has(sid(x.key))).slice(0, 8).map((x) =>
            `<tr><td><a href="#" data-i="${sid(x.key)}" data-n="${esc(x.key_display_name)}">${esc(x.key_display_name)}</a></td><td class="r">${fmt(x.count)}</td></tr>`).join("")}</tbody></table></section>` : "") + tip();
      } catch (_) { S.innerHTML = tip(); }
    }
    S.querySelectorAll("[data-f]").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); st.f = a.dataset.f; $("#sF").value = st.f; run(); }));
    S.querySelectorAll("[data-i]").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); st.i = a.dataset.i; st.iname = a.dataset.n; $("#sI").value = st.iname; run(); }));
  }
  const tip = () => `<section class="panel2 tipbox"><h2>💡 Looking for a supervisor?</h2><p>Switch to <b>Topic</b>, type your research interest and pick a country.
    Open a researcher's profile, read 2–3 of their recent papers, then write a short email that mentions one of them.</p></section>`;

  run();
})();
