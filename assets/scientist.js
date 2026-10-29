/* One scientist (/scientist/?id=A...) — loads live from OpenAlex */
(function () {
  const box = document.getElementById("person");
  if (!box) return;
  const id = (new URLSearchParams(location.search).get("id") || "").replace(/[^A-Za-z0-9]/g, "");
  const OA = "https://api.openalex.org/";
  const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString("en-US"));
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const sid = (u) => String(u || "").split("/").pop();
  const flag = (c) => (c ? `<span class="fi fi-${String(c).toLowerCase()}"></span>` : "");
  const get = (p) => fetch(OA + p + (p.includes("?") ? "&" : "?") + "mailto=researchboardlive@gmail.com").then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
  if (!/^A\d+$/.test(id)) { box.innerHTML = `<p>Find a scientist on the <a href="../scientists/">Scientists page</a>.</p>`; return; }
  const YEAR = new Date().getFullYear();

  (async () => {
    let a;
    try { a = await get(`authors/${id}`); }
    catch (_) { box.innerHTML = `<p>We couldn't load this profile right now. Please try again in a minute.</p>`; return; }
    const name = a.display_name;
    document.title = `${name} — research profile · ResearchBoard`;
    window.RB_SHARE_TEXT = `${name}: papers, citations and research topics — via ResearchBoard`;
    const L = a.last_known_institutions || [];
    const cby = (a.counts_by_year || []).slice().sort((x, y) => x.year - y.year).slice(-10);
    const mx = Math.max(1, ...cby.map((c) => c.works_count));
    const p5 = cby.filter((c) => c.year >= YEAR - 4).reduce((s, c) => s + c.works_count, 0);
    const c5 = cby.filter((c) => c.year >= YEAR - 4).reduce((s, c) => s + (c.cited_by_count || 0), 0);
    const topics = (a.topics || []).slice(0, 8);
    const fields = {};
    (a.topics || []).forEach((t) => { const f = t.field && t.field.display_name; if (f) fields[f] = (fields[f] || 0) + (t.count || 1); });
    const fl = Object.entries(fields).sort((x, y) => y[1] - x[1]).slice(0, 5), fmx = Math.max(1, ...fl.map((x) => x[1]));
    const initials = name.split(/\s+/).filter(Boolean).map((w) => w[0]).filter((c) => /[A-Za-z]/.test(c)).slice(0, 2).join("").toUpperCase();
    const many = L.length > 8;

    box.innerHTML = `
      <div class="crumb"><a href="../">Home</a> › <a href="../scientists/">Scientists</a> › ${esc(name)}</div>
      <div class="u-head"><div class="u-logo p-av">${esc(initials || "👤")}</div><div><h1>${esc(name)}</h1>
        <div class="muted">${L.slice(0, 3).map((i) => `${flag(i.country_code)} <a href="../university/?id=${sid(i.id)}">${esc(i.display_name)}</a>`).join(" · ") || "Institution not known"}
        ${a.orcid ? ` · <a class="orc" href="${esc(a.orcid)}" target="_blank" rel="noopener">iD</a> <a href="${esc(a.orcid)}" target="_blank" rel="noopener">ORCID</a>` : ""}
        · <a href="https://openalex.org/${id}" target="_blank" rel="noopener">OpenAlex ↗</a></div></div></div>
      ${many ? `<p class="note warnbox">⚠ This OpenAlex profile lists ${L.length} institutions, so it may combine several people with the same name.</p>` : ""}
      <div class="xstats x6"><div><span>Citations (career)</span><b>${fmt(a.cited_by_count)}</b></div>
        <div><span>Citations ${YEAR - 4}–${YEAR}</span><b>${fmt(c5)}</b></div>
        <div><span>h-index</span><b>${fmt((a.summary_stats || {}).h_index)}</b></div>
        <div><span>i10-index</span><b>${fmt((a.summary_stats || {}).i10_index)}</b></div>
        <div><span>Papers (career)</span><b>${fmt(a.works_count)}</b></div>
        <div><span>Papers ${YEAR - 4}–${YEAR}</span><b>${fmt(p5)}</b></div></div>
      <p class="note">Source: OpenAlex open data. Google Scholar-based sites usually show higher numbers (they also count theses, slides and duplicates); Scopus and Web of Science usually lower.</p>
      <div class="u-grid3">
        <section class="panel2"><h2>Papers per year</h2><div class="u-bars">${cby.map((c) => `<div class="${c.year === YEAR ? "cur" : ""}"><i style="height:${Math.max(3, c.works_count / mx * 110)}px"></i>${String(c.year).slice(2)}<br><b>${fmt(c.works_count)}</b></div>`).join("")}</div></section>
        <section class="panel2"><h2>Research fields</h2>${fl.map(([f, n]) => `<div class="u-hb"><span>${esc(f)}</span><i style="width:${n / fmx * 90}px"></i></div>`).join("") || "<p class='note'>—</p>"}
          <h2 style="margin-top:14px">Main topics</h2>${topics.map((t) => `<span class="u-pill">${esc(t.display_name)}</span>`).join(" ") || "—"}</section>
        <section class="panel2"><h2>Works most with</h2><div id="pCo" class="note">Loading…</div></section>
      </div>
      <div class="u-grid2">
        <section class="panel2"><h2>Latest papers</h2><div id="pNew" class="note">Loading…</div></section>
        <section class="panel2"><h2>Most-cited papers</h2><div id="pTop" class="note">Loading…</div></section>
      </div>
      <p class="note">Numbers come live from OpenAlex. Papers are matched to people automatically, so a profile can now and then miss a paper or include someone else's.
      <a href="../scientists/?c=${esc((L[0] || {}).country_code || "")}">More scientists${L[0] ? " in " + esc((() => { try { return new Intl.DisplayNames(["en"], { type: "region" }).of(L[0].country_code); } catch (_) { return L[0].country_code; } })()) : ""} →</a></p>`;

    const fill = (sel, html) => { const e = box.querySelector(sel); if (e) { e.classList.remove("note"); e.innerHTML = html; } };
    const paper = (w) => `<tr><td><a href="${esc(w.doi || "https://openalex.org/" + sid(w.id))}" target="_blank" rel="noopener">${esc(w.display_name)}</a>
      <div class="muted">${esc(w.publication_date || "")}${w.primary_location && w.primary_location.source ? " · " + esc(w.primary_location.source.display_name) : ""}</div></td>
      <td class="r"><b>${fmt(w.cited_by_count)}</b><div class="muted">cites</div></td></tr>`;
    const sel = "id,doi,display_name,publication_date,cited_by_count,primary_location";
    get(`works?filter=author.id:${id}&sort=publication_date:desc&per_page=6&select=${sel}`)
      .then((r) => fill("#pNew", `<table class="rt"><tbody>${r.results.map(paper).join("")}</tbody></table>`)).catch(() => fill("#pNew", "—"));
    get(`works?filter=author.id:${id}&sort=cited_by_count:desc&per_page=6&select=${sel}`)
      .then((r) => fill("#pTop", `<table class="rt"><tbody>${r.results.map(paper).join("")}</tbody></table>`)).catch(() => fill("#pTop", "—"));
    get(`works?filter=author.id:${id},from_publication_date:${YEAR - 4}-01-01&group_by=authorships.author.id`)
      .then((r) => {
        const co = (r.group_by || []).filter((x) => sid(x.key) !== id).slice(0, 8);
        fill("#pCo", co.length ? `<table class="rt"><tbody>${co.map((x) => `<tr><td><a href="?id=${sid(x.key)}">${esc(x.key_display_name)}</a></td><td class="r">${fmt(x.count)} papers</td></tr>`).join("")}</tbody></table>
          <p class="note">Co-authors since ${YEAR - 4}.</p>` : "No co-authors in the last 5 years.");
      }).catch(() => fill("#pCo", "—"));
  })();
})();
