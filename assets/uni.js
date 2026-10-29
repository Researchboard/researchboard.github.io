/* University profile (/university/?id=I...) — numbers load live from OpenAlex */
(function () {
  const box = document.getElementById("uni");
  if (!box) return;
  const id = (new URLSearchParams(location.search).get("id") || "").replace(/[^A-Za-z0-9]/g, "");
  const OA = "https://api.openalex.org/";
  const T = "type:article|review|preprint|letter|book-chapter";
  const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString("en-US"));
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const sid = (u) => String(u || "").split("/").pop();
  const get = (p) => fetch(OA + p + (p.includes("?") ? "&" : "?") + "mailto=researchboardlive@gmail.com").then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
  const flag = (c) => c ? `<span class="fi fi-${c.toLowerCase()}"></span>` : "";
  if (!/^I\d+$/.test(id)) { box.innerHTML = `<p>Choose a university from the <a href="../universities/">universities list</a>.</p>`; return; }

  const d0 = new Date(Date.now() - 365 * 864e5).toISOString().slice(0, 10);
  const W = `works?filter=authorships.institutions.lineage:${id},${T},from_publication_date:${d0}`;

  (async () => {
    let ins;
    try { ins = await get(`institutions/${id}`); }
    catch (_) { box.innerHTML = `<p>We couldn't load this university right now. Please try again in a minute.</p>`; return; }
    const cc = (ins.country_code || "").toUpperCase();
    const name = ins.display_name;
    document.title = `${name} research output ${new Date().getFullYear()} · ResearchBoard`;
    window.RB_SHARE_TEXT = `${name}: research output, top fields and researchers — via ResearchBoard`;
    const cby = (ins.counts_by_year || []).slice().sort((a, b) => a.year - b.year).slice(-6);
    const year = new Date().getFullYear();
    const yNow = (cby.find((c) => c.year === year) || {}).works_count;
    const oaNow = cby.filter((c) => c.year >= year - 1).reduce((s, c) => [s[0] + c.oa_works_count, s[1] + c.works_count], [0, 0]);
    const mx = Math.max(1, ...cby.map((c) => c.works_count));
    const geo = ins.geo || {};

    box.innerHTML = `
      <div class="crumb"><a href="../">Home</a> › <a href="../universities/">Universities</a> › <a href="../universities/?c=${cc}#udir">${esc(geo.country || cc)}</a> › ${esc(name)}</div>
      <div class="u-head"><div class="u-logo">🏛️</div><div><h1>${esc(name)} research output ${year}</h1>
        <div class="muted">${flag(cc)} ${esc([geo.city, geo.country].filter(Boolean).join(", "))} · live from OpenAlex <span id="uRank"></span>
        ${ins.homepage_url ? ` · <a href="${esc(ins.homepage_url)}" rel="nofollow noopener" target="_blank">website ↗</a>` : ""}</div></div></div>
      <div class="xstats"><div><span>Papers in ${year} so far</span><b>${fmt(yNow)}</b></div>
        <div><span>Papers, last 12 months</span><b id="u12">…</b></div>
        <div><span>Total citations (all time)</span><b>${fmt(ins.cited_by_count)}</b></div>
        <div><span>h-index</span><b>${fmt((ins.summary_stats || {}).h_index)}</b></div></div>
      <div class="u-grid3">
        <section class="panel2"><h2>Papers per year</h2><div class="u-bars">${cby.map((c) => `<div class="${c.year === year ? "cur" : ""}"><i style="height:${Math.max(3, c.works_count / mx * 110)}px"></i>${c.year}${c.year === year ? "*" : ""}<br><b>${fmt(c.works_count)}</b></div>`).join("")}</div>
          <p class="note">*${year} so far. Journals keep adding papers for a while, so recent years grow.</p></section>
        <section class="panel2"><h2>Top research fields (12 months)</h2><div id="uFields" class="note">Loading…</div></section>
        <section class="panel2"><h2>Rank in ${esc(geo.country || cc)}</h2><div id="uRankT" class="note">Loading…</div></section>
      </div>
      <div class="u-grid3">
        <section class="panel2"><h2>Top 5 most-cited scientists</h2><div id="uAuth" class="note">Loading…</div></section>
        <section class="panel2"><h2>Hot topics here (12 months)</h2><div id="uTopics" class="note">Loading…</div></section>
        <section class="panel2"><h2>Works most with</h2><div id="uCo" class="note">Loading…</div></section>
      </div>
      <div class="u-grid2">
        <section class="panel2"><h2>Most-cited papers of the last 12 months</h2><div id="uPapers" class="note">Loading…</div></section>
        <section class="panel2"><h2>Free to read (open access)</h2>${oaNow[1] ? `<div class="u-oa"><div class="u-ring" style="--p:${Math.round(oaNow[0] / oaNow[1] * 100)}"><div>${Math.round(oaNow[0] / oaNow[1] * 100)}%</div></div>
          <p class="muted">${fmt(oaNow[0])} of ${fmt(oaNow[1])} papers from ${year - 1}–${year} can be read free by anyone.</p></div>` : `<p class="note">No data yet.</p>`}</section>
      </div>
      <p class="note">Numbers come live from <a href="https://openalex.org/institutions/${id}" target="_blank" rel="noopener">OpenAlex</a> and include papers with at least one author from ${esc(name)} or its departments. <a href="../about/methods.html">Methods</a></p>`;

    const fill = (sel, html) => { const e = box.querySelector(sel); if (e) { e.classList.remove("note"); e.innerHTML = html; } };
    const safe = async (fn, sel) => { try { await fn(); } catch (_) { fill(sel, `<p class="note">Couldn't load this part.</p>`); } };
    const table = (rows) => `<table class="rt"><tbody>${rows.join("")}</tbody></table>`;

    safe(async () => {
      const f = await get(`${W}&group_by=primary_topic.field.id`);
      const g = (f.group_by || []).slice(0, 6), m = Math.max(1, ...g.map((x) => x.count));
      fill("#uFields", g.map((x) => `<div class="u-hb"><span>${esc(x.key_display_name)}</span><i style="width:${x.count / m * 100}px"></i><b>${fmt(x.count)}</b></div>`).join("") || "No papers in the last 12 months.");
      document.getElementById("u12").textContent = fmt(f.meta && f.meta.count);
    }, "#uFields");
    safe(async () => {
      const a = await get(`authors?filter=last_known_institutions.id:${id}&sort=cited_by_count:desc&per_page=5&select=id,display_name,cited_by_count,summary_stats,works_count`);
      fill("#uAuth", table(a.results.map((x) => `<tr><td><a href="https://openalex.org/${sid(x.id)}" target="_blank" rel="noopener">${esc(x.display_name)}</a><div class="muted">${fmt(x.works_count)} papers · h-index ${fmt((x.summary_stats || {}).h_index)}</div></td><td class="r">${fmt(x.cited_by_count)}<div class="muted">OpenAlex citations</div></td></tr>`)));
    }, "#uAuth");
    safe(async () => {
      const t = await get(`${W}&group_by=primary_topic.id`);
      fill("#uTopics", (t.group_by || []).slice(0, 8).map((x) => `<span class="u-pill">${esc(x.key_display_name)} · ${fmt(x.count)}</span>`).join(" ") || "—");
    }, "#uTopics");
    safe(async () => {
      const c = await get(`${W}&group_by=authorships.countries`);
      const dn = new Intl.DisplayNames(["en"], { type: "region" });
      const rows = (c.group_by || []).filter((x) => sid(x.key).toUpperCase() !== cc).slice(0, 6);
      fill("#uCo", table(rows.map((x) => { const k = sid(x.key).toUpperCase(); let n = k; try { n = dn.of(k); } catch (_) {} return `<tr><td>${flag(k)} ${esc(n)}</td><td class="r">${fmt(x.count)} papers</td></tr>`; })) || "—");
    }, "#uCo");
    safe(async () => {
      const p = await get(`${W}&sort=cited_by_count:desc&per_page=5&select=id,doi,display_name,cited_by_count,publication_date`);
      fill("#uPapers", table(p.results.map((x) => `<tr><td><a href="${esc(x.doi || "https://openalex.org/" + sid(x.id))}" target="_blank" rel="noopener">${esc(x.display_name)}</a><div class="muted">${esc(x.publication_date)}</div></td><td class="r"><b>${fmt(x.cited_by_count)}</b><div class="muted">cites</div></td></tr>`)));
    }, "#uPapers");
    safe(async () => {   // rank inside the country, from our weekly directory
      const rows = await fetch(`../data/universities/${cc}.json`).then((r) => { if (!r.ok) throw 0; return r.json(); });
      const i = rows.findIndex((r) => r[0] === id);
      if (i >= 0) document.getElementById("uRank").innerHTML = ` · <span class="u-pill g">#${i + 1} of ${fmt(rows.length)} in ${esc(geo.country || cc)}</span>`;
      const lo = Math.max(0, Math.min(i - 2, rows.length - 5)), sl = rows.slice(i < 0 ? 0 : lo, (i < 0 ? 0 : lo) + 5);
      fill("#uRankT", table(sl.map((r) => `<tr><td>${rows.indexOf(r) + 1}</td><td>${r[0] === id ? `<b>${esc(r[1])}</b>` : `<a href="?id=${r[0]}">${esc(r[1])}</a>`}</td><td class="r">${fmt(r[4])}</td></tr>`)) +
        `<p class="note">Papers in ${year - 1}. <a href="../universities/?c=${cc}#udir">All ${fmt(rows.length)} →</a></p>`);
    }, "#uRankT");
  })();
})();
