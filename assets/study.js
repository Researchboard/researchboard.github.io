/* Study Abroad (/study/): 🎓 Scholarships · 💰 Funded professors · US active grants · Canada active grants */
(function () {
  const box = document.getElementById("study");
  if (!box) return;
  const OA = "https://api.openalex.org/";
  const $ = (s) => box.querySelector(s);
  const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString("en-US"));
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const sid = (u) => String(u || "").split("/").pop();
  const oa = (p) => fetch(OA + p + (p.includes("?") ? "&" : "?") + "mailto=researchboardlive@gmail.com").then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
  const FLAG = new Proxy({}, { get: (_, c) => (typeof c === "string" && /^[A-Z]{2}$/.test(c) ? `<span class="fi fi-${c.toLowerCase()}"></span>` : "") });
  const CNAME = { SE: "Sweden", HU: "Hungary", TR: "Türkiye", KR: "South Korea", JP: "Japan", GB: "United Kingdom", DE: "Germany", EU: "European Union", CN: "China", AU: "Australia", US: "USA", NL: "Netherlands", FR: "France", CH: "Switzerland", HK: "Hong Kong", SG: "Singapore", SA: "Saudi Arabia", TW: "Taiwan", CA: "Canada" };
  const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const today = new Date();
  const P = new URLSearchParams(location.search);
  let tab = ["scholarships", "professors", "usa", "canada"].includes(P.get("tab")) ? P.get("tab") : "scholarships";
  function setURL(k, v) { try { const u = new URL(location.href); if (v) u.searchParams.set(k, v); else u.searchParams.delete(k); history.replaceState(null, "", u); } catch (_) {} }

  // funded-research figures for 2025 from OpenAlex (papers naming a funder), checked Oct 2026
  const COUNTRIES = {
    CA: { mf: ["✅", "Often (thesis MSc)"], pf: ["✅", "Common"], how: "Email a professor", stat: [67197, 54],
      notes: ["Research (thesis-based) master's and PhD students are usually paid from the professor's grant as research or teaching assistants.", "Course-based master's are usually not funded.", "Contact professors whose recent papers match your interest before applying."],
      links: [["Universities Canada — find a program", "https://www.univcan.ca/"]] },
    DE: { mf: ["⚠️", "Rare — but tuition is free or low"], pf: ["✅", "Common (paid contract)"], how: "Apply to advertised positions", stat: [104516, 58],
      notes: ["A PhD is often a paid job contract on a professor's project.", "Master's study is usually tuition-free at public universities; DAAD offers scholarships.", "Look for PhD vacancies at universities and Max Planck, Helmholtz, Fraunhofer and Leibniz institutes."],
      links: [["DAAD scholarship database", "https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/"], ["EURAXESS jobs", "https://euraxess.ec.europa.eu/"]] },
    KR: { mf: ["✅", "Common"], pf: ["✅", "Common"], how: "Email a professor", stat: [70706, 66],
      notes: ["The lab head usually pays a monthly research-assistant stipend from grants; tuition is often covered.", "The professor usually decides — write to those whose papers match your interest.", "Government scholarship: Global Korea Scholarship (GKS). Intakes in March and September."],
      links: [["Study in Korea", "https://www.studyinkorea.go.kr/"]] },
    JP: { mf: ["✅", "Via scholarship"], pf: ["✅", "Common"], how: "Contact a professor + scholarship", stat: [76497, 49],
      notes: ["Most international students are funded by the MEXT scholarship or university scholarships.", "Some labs also hire research assistants.", "For MEXT you usually need a professor who agrees to host you."],
      links: [["Study in Japan", "https://www.studyinjapan.go.jp/en/"]] },
    CN: { mf: ["✅", "Common"], pf: ["✅", "Common"], how: "Scholarship + professor", stat: [768321, 68],
      notes: ["China funds more research than any other country.", "Chinese Government (CSC) and university scholarships cover tuition and a stipend; labs often add a monthly allowance.", "Many programmes are taught in English."],
      links: [["Campus China (CSC)", "https://www.campuschina.org/"]] },
    AU: { mf: ["⚠️", "Research master's only"], pf: ["✅", "Common"], how: "Contact a supervisor, then apply", stat: [63328, 56],
      notes: ["PhD students are usually funded by Research Training Program (RTP) or university scholarships.", "Supervisors sometimes add a top-up from their grants.", "Find a supervisor first — most universities ask for one."],
      links: [["Research Training Program", "https://www.education.gov.au/research-block-grants/research-training-program"]] },
    NL: { mf: ["❌", "Rare (Holland Scholarship is partial)"], pf: ["✅", "Salaried job"], how: "Apply to advertised positions", stat: [39870, 58],
      notes: ["A PhD is a paid employee position with a salary, usually for four years.", "Positions are advertised like jobs — apply to a specific project.", "Master's funding is limited."],
      links: [["AcademicTransfer — PhD vacancies", "https://www.academictransfer.com/en/"]] },
    SE: { mf: ["⚠️", "Swedish Institute scholarship"], pf: ["✅", "Salaried job"], how: "Apply to advertised positions", stat: [31840, 67],
      notes: ["A PhD is a salaried employment, usually four years.", "Vacancies are posted on each university's job pages.", "Master's: the Swedish Institute (SISGP) is the main scholarship."],
      links: [["EURAXESS jobs", "https://euraxess.ec.europa.eu/"]] },
    HK: { mf: ["⚠️", "Research MPhil is funded"], pf: ["✅", "Common"], how: "Contact a professor + apply", stat: [28769, 68],
      notes: ["Research postgraduate students (MPhil and PhD) usually receive a monthly studentship.", "The Hong Kong PhD Fellowship adds a higher stipend and travel allowance."],
      links: [["Hong Kong PhD Fellowship", "https://cerg1.ugc.edu.hk/hkpfs/index.html"]] },
    SG: { mf: ["⚠️", "Rare"], pf: ["✅", "Common"], how: "Scholarship + professor", stat: [17786, 63],
      notes: ["PhD students are usually funded through university research scholarships or SINGA.", "NUS, NTU and A*STAR institutes are the main options."],
      links: [["SINGA", "https://www.a-star.edu.sg/Scholarships/for-graduate-studies/singapore-international-graduate-award-singa"]] },
  };
  const C_ORDER = ["CA", "DE", "KR", "JP", "CN", "AU", "NL", "SE", "HK", "SG"];

  box.innerHTML = `
    <div class="st-hero"><h1>🎓 Study abroad: <span>scholarships</span> and <span>funded</span> MS / PhD positions</h1>
      <p>Fully funded scholarships for international students, professors with funded research in 10 countries, and US and Canadian professors with active government grants — all free, with links to official sources.</p>
      <p class="st-hero-link"><a href="../us-universities/">🗺️ Map of every US university for master's &amp; PhD — application fees, tuition, international students →</a></p></div>
    <div class="st-tabs" role="tablist">
      <button data-t="scholarships">🎓 Scholarships</button><button data-t="professors">💰 Funded professors</button><button data-t="usa"><span class="fi fi-us"></span> US active grants</button><button data-t="canada"><span class="fi fi-ca"></span> Canada active grants</button></div>
    <div id="tScholarships"></div><div id="tProfessors" hidden></div><div id="tUsa" hidden></div><div id="tCanada" hidden></div>`;
  function show(t) {
    tab = t; setURL("tab", t === "scholarships" ? "" : t);
    box.querySelectorAll(".st-tabs button").forEach((b) => b.classList.toggle("on", b.dataset.t === t));
    $("#tScholarships").hidden = t !== "scholarships"; $("#tProfessors").hidden = t !== "professors"; $("#tUsa").hidden = t !== "usa"; $("#tCanada").hidden = t !== "canada";
    if (t === "scholarships") initScholarships(); else if (t === "professors") initProfessors(); else if (t === "usa") initUsa(); else initCanada();
  }
  box.querySelectorAll(".st-tabs button").forEach((b) => b.addEventListener("click", () => show(b.dataset.t)));

  // =================================================================== Scholarships
  let SCH = null, schReady = false;
  function status(s) {
    if (s.deadline) {
      const d = new Date(s.deadline + "T23:59:00"), days = Math.ceil((d - today) / 864e5);
      const lab = `${d.getDate()} ${MON[d.getMonth()]} ${d.getFullYear()}`;
      if (days < 0) return ["closed", s.window ? `Closed · usually opens ${MON[s.window[0] - 1]}` : `Closed ${lab}`, 500];
      return [days <= 90 ? "soon" : "open", `Closes ${lab}`, days];
    }
    const [a, b] = s.window || [0, 0], m = today.getMonth() + 1;
    if (!a) return ["closed", "Check official site", 99];
    let inWin = a <= b ? m >= a && m <= b : m >= a || m <= b;
    if (inWin && m === b && s.closeDay && today.getDate() > s.closeDay) return ["closed", `Usually closed by ${s.closeDay} ${MON[b - 1]} · next ${MON[a - 1]}`, 400];
    const until = (x) => ((x - m + 12) % 12);
    if (inWin) return ["soon", m === b ? `Usually closes in ${MON[b - 1]} — check now` : `Usually open now (${MON[a - 1]}–${MON[b - 1]})`, until(b) * 30 + 15];
    const k = until(a);
    if (k <= 3) return ["open", `Usually opens ${MON[a - 1]}`, 40 + k * 30];
    return ["closed", `Usually ${MON[a - 1]}–${MON[b - 1]}`, 200 + k * 30];
  }
  function card(s) {
    const [cls, lab] = status(s);
    const lvl = s.levels.map((l) => `<span>${esc(l)}</span>`).join("");
    const tags = (s.tags || []).map((l) => `<span>${esc(l)}</span>`).join("");
    const bd = s.bd === "yes" ? `<span class="bd"><span class="fi fi-bd"></span> Bangladesh eligible</span>` : s.bd === "check" ? `<span class="chk">Check country list</span>` : "";
    return `<article class="sc"><div class="sc-top"><div><h3>${FLAG[s.country] || ""} ${esc(s.name)}</h3><div class="sc-c">${esc(CNAME[s.country] || s.country)} · ${esc(s.type)}</div></div>
      <span class="dl ${cls}">${esc(lab)}</span></div>
      <div class="sc-tags"><span class="${s.funding === "full" ? "full" : "part"}">${s.funding === "full" ? "Fully funded" : "Partial funding"}</span>${lvl}${tags}${bd}</div>
      <p><b>Covers:</b> ${esc(s.covers)}</p><p><b>Who can apply:</b> ${esc(s.who)}</p>
      ${s.timing ? `<p class="sc-when"><b>When:</b> ${esc(s.timing)}</p>` : ""}
      <div class="sc-ft"><span class="${s.checked ? "ok" : "usu"}">${s.checked ? "✔ Dates checked " + esc(fmtMonth(s.checked)) : "Usual timing — check this year's call"}</span>
        <a class="sc-go" href="${esc(s.url)}" target="_blank" rel="noopener">Apply on official site ↗</a></div>
      <div class="sc-web">🌐 <a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.site)}</a>${s.local ? ` · <a href="${esc(s.local.url)}" target="_blank" rel="noopener">${esc(s.local.label)}: ${esc(s.local.site)}</a>` : ""}</div></article>`;
  }
  const fmtMonth = (ym) => { const [y, m] = ym.split("-"); return `${MON[+m - 1]} ${y}`; };
  async function initScholarships() {
    if (schReady) return; schReady = true;
    const T = $("#tScholarships");
    T.innerHTML = `<div class="sc-f"><input id="scQ" type="search" placeholder="Search a scholarship, country or field…" aria-label="Search scholarships">
      <select id="scC" aria-label="Country"><option value="">All countries</option></select>
      <select id="scL" aria-label="Level"><option value="">Master's and PhD</option><option value="Master's">Master's</option><option value="PhD">PhD</option></select>
      <label><input type="checkbox" id="scFull"> Fully funded only</label><label><input type="checkbox" id="scOpen"> Open or opening soon</label>
      <label><input type="checkbox" id="scBD"> Open to Bangladesh</label></div>
      <div class="sc-soon" id="scSoon"></div><p class="note" id="scN"></p><div class="sc-grid" id="scGrid"><p class="note">Loading…</p></div>
      <p class="note">Dates change every year. Cards marked ✔ were checked for this year's round; others show the usual timing from past years — always confirm on the official website before applying. Spotted a mistake? Email researchboardlive@gmail.com.</p>`;
    try { SCH = await fetch("../assets/scholarships.json", { cache: "no-cache" }).then((r) => r.json()); }
    catch (_) { $("#scGrid").innerHTML = `<p class="note">Couldn't load the list. Please refresh.</p>`; return; }
    const cs = [...new Set(SCH.items.map((s) => s.country))].sort((a, b) => (CNAME[a] || a).localeCompare(CNAME[b] || b));
    $("#scC").innerHTML += cs.map((c) => `<option value="${c}">${esc(CNAME[c] || c)}</option>`).join("");
    const pc = P.get("c"); if (pc && cs.includes(pc.toUpperCase())) $("#scC").value = pc.toUpperCase();
    const soon = SCH.items.map((s) => [s, status(s)]).filter(([, st]) => st[0] === "soon")
      .sort((a, b) => (a[0].deadline ? 0 : 1) - (b[0].deadline ? 0 : 1) || a[1][2] - b[1][2]).slice(0, 4);
    $("#scSoon").innerHTML = soon.length ? `⏰ <b>Closing soon:</b> ` + soon.map(([s, st]) => `${FLAG[s.country] || ""} ${esc(s.short || s.name)} — <b>${esc(st[1].replace("Closes ", ""))}</b>`).join(" · ") : "";
    const render = () => {
      const q = $("#scQ").value.trim().toLowerCase(), c = $("#scC").value, l = $("#scL").value;
      const list = SCH.items.filter((s) => (!q || (s.name + " " + (CNAME[s.country] || "") + " " + s.who + " " + s.covers).toLowerCase().includes(q))
        && (!c || s.country === c) && (!l || s.levels.some((x) => x.includes(l))) && (!$("#scFull").checked || s.funding === "full")
        && (!$("#scOpen").checked || status(s)[0] !== "closed") && (!$("#scBD").checked || s.bd === "yes"))
        .sort((a, b) => status(a)[2] - status(b)[2]);
      $("#scN").textContent = `${list.length} of ${SCH.items.length} scholarships · sorted by next deadline`;
      $("#scGrid").innerHTML = list.map(card).join("") || `<p class="note">No scholarship matches. Try removing a filter.</p>`;
    };
    ["#scQ", "#scC", "#scL", "#scFull", "#scOpen", "#scBD"].forEach((k) => $(k).addEventListener("input", render));
    render();
  }

  // =================================================================== Funded professors (OpenAlex)
  let profReady = false, pc = C_ORDER.includes((P.get("c") || "").toUpperCase()) ? P.get("c").toUpperCase() : "KR";
  function initProfessors() {
    if (profReady) return; profReady = true;
    const T = $("#tProfessors");
    T.innerHTML = `<div class="st-lbl">① Pick a country where professors fund MS / PhD students</div>
      <div class="st-cc">${C_ORDER.map((c) => `<button data-c="${c}">${FLAG[c]} ${CNAME[c]}</button>`).join("")}</div>
      <div id="pCard"></div>
      <div class="st-lbl">② Type your research topic</div>
      <div class="st-row"><input id="pQ" type="search" placeholder='e.g. "solar cells", "machine learning", "rice genetics", "public health"' aria-label="Research topic"><button class="st-go" id="pGo">Find funded professors</button></div>
      <p class="st-big" id="pBig"></p>
      <div class="st-grid"><section class="panel2"><h2 id="pTitle">③ Funded professors</h2><div id="pList"><p class="note">Type a topic to see professors whose research on it is funded.</p></div>
        <button class="ud-more" id="pMore" hidden>Load more</button></section>
        <aside><section class="panel2"><h2 id="pFunTitle">Who funds research here</h2><div id="pFun" class="note">Loading…</div></section>
        <section class="panel2"><h2>Universities active on it</h2><div id="pIns" class="note">Type a topic.</div></section>
        <section class="panel2 st-tip">✉️ <b>Next step:</b> open 3–5 professors' recent papers, then email each a short note naming one of their papers and asking whether they have a funded MS or PhD position. <a href="../blog/find-a-research-supervisor.html">Email template →</a></section></aside></div>
      <p class="note">Based on the funders named in papers' acknowledgements in OpenAlex since ${today.getFullYear() - 3}. It shows who had funding recently — not a guarantee of an open position today.</p>`;
    T.querySelectorAll(".st-cc button").forEach((b) => b.addEventListener("click", () => { pc = b.dataset.c; setURL("c", pc); countryCard(); if ($("#pQ").value.trim()) runProf(); }));
    $("#pGo").addEventListener("click", runProf);
    $("#pQ").addEventListener("keydown", (e) => { if (e.key === "Enter") runProf(); });
    $("#pMore").addEventListener("click", () => { pPage++; renderProf(); });
    if (P.get("q") && tab === "professors") $("#pQ").value = P.get("q");
    countryCard();
    if ($("#pQ").value.trim()) runProf();
  }
  async function countryCard() {
    const c = COUNTRIES[pc];
    box.querySelectorAll(".st-cc button").forEach((b) => b.classList.toggle("on", b.dataset.c === pc));
    $("#pCard").innerHTML = `<section class="panel2 st-card"><div><h2>${FLAG[pc]} ${CNAME[pc]} — how funding works</h2>
      <div class="st-kv"><div><span>Funded MS</span><b>${c.mf[0]} ${esc(c.mf[1])}</b></div><div><span>Funded PhD</span><b>${c.pf[0]} ${esc(c.pf[1])}</b></div><div><span>How to get in</span><b>${esc(c.how)}</b></div></div>
      <ul>${c.notes.map((n) => `<li>${esc(n)}</li>`).join("")}</ul>
      <p class="note">${fmt(c.stat[0])} papers from ${CNAME[pc]} named a funder in 2025 (${c.stat[1]}% of its research). Useful links: ${c.links.map(([n, u]) => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(n)} ↗</a>`).join(" · ")} ·
        <a href="#" data-sch="${pc}">Scholarships in ${CNAME[pc]} →</a></p></div></section>`;
    const a = $("#pCard [data-sch]");
    if (a) a.addEventListener("click", (e) => { e.preventDefault(); show("scholarships"); const s = $("#scC"); if (s && [...s.options].some((o) => o.value === pc)) { s.value = pc; s.dispatchEvent(new Event("input")); } });
    if (!$("#pQ").value.trim()) funders(null);
  }
  const from = `${today.getFullYear() - 3}-01-01`;
  const T_ = "type:article|review|preprint";
  async function funders(q) {
    $("#pFunTitle").textContent = q ? `Who funds “${q}” in ${CNAME[pc]}` : `Who funds research in ${CNAME[pc]}`;
    try {
      const g = await oa(`works?${q ? "search=" + encodeURIComponent(q) + "&" : ""}filter=authorships.institutions.country_code:${pc},from_publication_date:${from},${T_}&group_by=funders.id`);
      const L = (g.group_by || []).slice(0, 7), mx = Math.max(1, ...L.map((x) => x.count));
      $("#pFun").classList.remove("note");
      $("#pFun").innerHTML = L.map((x) => `<div class="st-hb"><span>${esc(x.key_display_name)}</span><i style="width:${x.count / mx * 80}px"></i><b>${fmt(x.count)}</b></div>`).join("") + `<p class="note">Funded papers since ${today.getFullYear() - 3}.</p>`;
    } catch (_) { $("#pFun").textContent = "—"; }
  }
  let profRows = [], pPage = 1, pTok = 0;
  async function runProf() {
    const q = $("#pQ").value.trim(); if (!q) return;
    setURL("q", q);
    const my = ++pTok;
    $("#pTitle").textContent = `③ Funded professors on “${q}” in ${CNAME[pc]}`;
    $("#pList").innerHTML = `<p class="note">Searching OpenAlex…</p>`; $("#pBig").textContent = ""; $("#pMore").hidden = true;
    funders(q);
    const base = `works?search=${encodeURIComponent(q)}&filter=authorships.institutions.country_code:${pc},from_publication_date:${from},${T_}`;
    try {
      const [all, fun, au, ins] = await Promise.all([oa(base + "&per_page=1&select=id"), oa(base + ",funders.id:!null&per_page=1&select=id"),
        oa(base + ",funders.id:!null&group_by=authorships.author.id"), oa(base + "&group_by=authorships.institutions.lineage")]);
      if (my !== pTok) return;
      const n = all.meta.count, f = fun.meta.count;
      $("#pBig").innerHTML = n ? `In ${CNAME[pc]}, <b>${fmt(f)} of ${fmt(n)}</b> papers on “${esc(q)}” since ${today.getFullYear() - 3} name a funder — <b>${Math.round(f / n * 100)}% funded</b>.` : `No papers found on “${esc(q)}” in ${CNAME[pc]}. Try a broader word.`;
      // universities: keep education institutions in this country
      const iids = (ins.group_by || []).slice(0, 25).map((x) => sid(x.key));
      if (iids.length) {
        const meta = await oa(`institutions?filter=openalex:${iids.join("|")}&per_page=50&select=id,type,country_code`);
        const okI = new Set((meta.results || []).filter((x) => x.type === "education" && (x.country_code || "").toUpperCase() === pc).map((x) => sid(x.id)));
        const L = (ins.group_by || []).filter((x) => okI.has(sid(x.key))).slice(0, 6);
        $("#pIns").classList.remove("note");
        $("#pIns").innerHTML = L.length ? `<table class="rt"><tbody>${L.map((x) => `<tr><td><a href="../university/?id=${sid(x.key)}">${esc(x.key_display_name)}</a></td><td class="r">${fmt(x.count)}</td></tr>`).join("")}</tbody></table><p class="note">Papers on the topic since ${today.getFullYear() - 3}.</p>` : "—";
      }
      // professors: details for the authors with most funded papers, kept if based in this country
      const top = (au.group_by || []).slice(0, 60);
      const det = {};
      for (let k = 0; k < top.length; k += 50) {
        const r = await oa(`authors?filter=openalex:${top.slice(k, k + 50).map((x) => sid(x.key)).join("|")}&per_page=50&select=id,display_name,last_known_institutions,summary_stats,orcid`);
        (r.results || []).forEach((a) => { det[sid(a.id)] = a; });
      }
      if (my !== pTok) return;
      profRows = top.map((x) => [det[sid(x.key)], x.count]).filter(([a]) => a && (a.last_known_institutions || []).length <= 8
        && (a.last_known_institutions || []).some((i) => (i.country_code || "").toUpperCase() === pc));
      pPage = 1; renderProf();
    } catch (_) { if (my === pTok) $("#pList").innerHTML = `<p class="note">OpenAlex didn't answer just now. Please try again in a minute.</p>`; }
  }
  function renderProf() {
    const L = profRows.slice(0, pPage * 20);
    $("#pList").innerHTML = L.length ? `<table class="rt"><thead><tr><th>#</th><th>Professor / researcher</th><th class="r">Funded papers</th><th class="r">h-index</th></tr></thead><tbody>${L.map(([a, n], i) => {
      const inst = (a.last_known_institutions || []).find((x) => (x.country_code || "").toUpperCase() === pc);
      return `<tr><td>${i + 1}</td><td><a href="../scientist/?id=${sid(a.id)}"><b>${esc(a.display_name)}</b></a>${a.orcid ? ` <a class="orc" href="${esc(a.orcid)}" target="_blank" rel="noopener">iD</a>` : ""}
        <div class="ud-city">${inst ? `<a href="../university/?id=${sid(inst.id)}">${esc(inst.display_name)}</a>` : ""}</div>
        <div class="st-acts"><a href="../scientist/?id=${sid(a.id)}">Profile &amp; recent papers</a></div></td>
        <td class="r"><b>${fmt(n)}</b></td><td class="r">${fmt((a.summary_stats || {}).h_index)}</td></tr>`;
    }).join("")}</tbody></table>` : `<p class="note">No funded researchers found for this topic here. Try a broader topic.</p>`;
    $("#pMore").hidden = profRows.length <= pPage * 20;
  }

  // =================================================================== US active grants (NSF live + NIH weekly)
  let usaReady = false, NIH = null;
  function initUsa() {
    if (usaReady) return; usaReady = true;
    const T = $("#tUsa");
    T.innerHTML = `<div class="st-row"><input id="uQ" type="search" placeholder='e.g. "solar cells", "machine learning", "cancer", "arsenic"' aria-label="Research topic">
      <select id="uSort" aria-label="Sort"><option value="amt">Sort: largest grant</option><option value="end">Sort: ending latest</option></select><button class="st-go" id="uGo">Search grants</button></div>
      <div class="st-chips"><label><input type="checkbox" id="uNSF" checked> Science &amp; engineering (NSF)</label><label><input type="checkbox" id="uNIH" checked> Health &amp; biology (NIH)</label>
        <label><input type="checkbox" id="u2028"> Only grants active until ${today.getFullYear() + 2} or later</label></div>
      <p class="st-big" id="uBig"></p>
      <div class="st-grid"><section class="panel2"><h2 id="uTitle">US professors with active grants</h2><div id="uList"><p class="note">Loading the newest grants…</p></div>
        <button class="ud-more" id="uMore" hidden>Load more</button></section>
        <aside><section class="panel2"><h2>Health topics (NIH)</h2><div id="uTopics" class="st-tchips note">Loading…</div><p class="note">NIH grants are refreshed weekly for these topics. <a href="https://reporter.nih.gov/" target="_blank" rel="noopener">Search all NIH grants ↗</a></p></section>
        <section class="panel2"><h2>What the grant types mean</h2><p><span class="gt lab">Individual lab grant</span> One professor's project — the most direct route to a research-assistant job.</p>
          <p><span class="gt train">Training program</span> Pays PhD students directly (NIH T32 and similar) — ask the program director.</p>
          <p><span class="gt ctr">Research center</span> A large team grant across several labs — many positions.</p></section>
        <section class="panel2 st-tip">✉️ <b>Tip:</b> contact professors whose grants run 2+ more years. Mention the project title and one of their recent papers, and ask whether they are hiring a graduate research assistant.</section></aside></div>
      <p class="note">Official sources: <a href="https://www.nsf.gov/awardsearch/" target="_blank" rel="noopener">NSF Award Search</a> (live) and <a href="https://reporter.nih.gov/" target="_blank" rel="noopener">NIH RePORTER</a> (weekly). Amounts are what the agency awarded; not all of it pays students.</p>`;
    fetch("../data/grants/nih-index.json", { cache: "no-cache" }).then((r) => r.json()).then((j) => {
      NIH = j;
      $("#uTopics").classList.remove("note");
      $("#uTopics").innerHTML = j.topics.map(([t, s, n]) => `<button data-t="${esc(t)}">${esc(t)} <span>${fmt(n)}</span></button>`).join("");
      $("#uTopics").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { $("#uQ").value = b.dataset.t; runUsa(); }));
    }).catch(() => { $("#uTopics").textContent = "NIH topics appear after the next weekly update."; });
    $("#uGo").addEventListener("click", runUsa);
    $("#uQ").addEventListener("keydown", (e) => { if (e.key === "Enter") runUsa(); });
    ["#uSort", "#u2028"].forEach((k) => $(k).addEventListener("input", () => { uPage = 1; renderUsa(); }));
    ["#uNSF", "#uNIH"].forEach((k) => $(k).addEventListener("input", () => { if ($("#uQ").value.trim()) runUsa(); else { uPage = 1; renderUsa(); } }));
    $("#uMore").addEventListener("click", () => { uPage++; renderUsa(); });
    if (P.get("q") && tab === "usa") { $("#uQ").value = P.get("q"); runUsa(); } else usaDefault();
  }
  // before anyone searches: grants awarded in the last 60 days (new grants = labs that are hiring)
  async function usaDefault() {
    const my = ++uTok; uRows = []; uCounts = {};
    $("#uTitle").textContent = "Newest US grants — awarded in the last 60 days";
    const from = new Date(today.getTime() - 60 * 864e5);
    const jobs = [(async () => {
      const base = `https://api.nsf.gov/services/v1/awards.json?dateStart=${encodeURIComponent(mdy(from))}&expDateStart=${encodeURIComponent(mdy(today))}&rpp=25`;
      for (let off = 1; off <= 76; off += 25) {
        const r = await fetch(base + `&offset=${off}`).then((x) => x.json());
        const a = (r.response && r.response.award) || [];
        uCounts.NSF = ((r.response || {}).metadata || {}).totalCount || uCounts.NSF;
        a.forEach((x) => { if (!/^Conference\b/i.test(x.title || "")) { const o = nsfRow(x); if (o) uRows.push(o); } });
        if (a.length < 25) break;
      }
    })().catch(() => {}), (async () => {
      const d = await fetch("../data/grants/nih-latest.json", { cache: "no-cache" }).then((r) => r.json());
      uCounts.NIH = d.total; d.rows.forEach((x) => uRows.push(nihRow(x)));
    })().catch(() => {})];
    await Promise.all(jobs);
    if (my !== uTok) return;
    const parts = [];
    if (uCounts.NSF > 0) parts.push(`<b>${fmt(uCounts.NSF)} new NSF awards</b>`);
    if (uCounts.NIH > 0) parts.push(`<b>${fmt(uCounts.NIH)} new NIH lab and training grants</b>`);
    $("#uBig").innerHTML = parts.length ? `${parts.join(" and ")} in the last 60 days. Individual lab and training grants first — type a topic to search all active grants.` : "";
    uPage = 1; renderUsa();
  }
  function nsfRow(x) {
    const t = x.title || "";
    if (/^(SBIR|STTR)\b/i.test(t) || /\b(INC|LLC|CORP|CORPORATION|LTD)\.?$/i.test((x.awardeeName || "").trim())) return null;   // companies rarely hire graduate students
    if (/Community College|Technical College/i.test(x.awardeeName || "")) return null;                                    // no graduate programs
    const [mm, dd, yy] = String(x.expDate || "").split("/");
    return { src: "NSF", pi: `${x.piFirstName || ""} ${x.piLastName || ""}`.trim(), org: x.awardeeName || "", st: x.awardeeStateCode || "",
      amt: +(x.estimatedTotalAmt || x.fundsObligatedAmt || 0), end: yy ? `${yy}-${mm}-${dd}` : "", title: t,
      kind: /graduate research fellowship|research traineeship|graduate fellowship|\bNRT\b|\bREU\b/i.test(t) ? "train" : /\b(center|centers|institute|RII|PREM|CREST|MRSEC|STC|ERC|Infrastructure|Facility|Facilities|Operations|Mid-scale|NAIRR|Network)\b/i.test(t) ? "ctr" : "lab",
      url: `https://www.nsf.gov/awardsearch/showAward?AWD_ID=${x.id}` };
  }
  const nihRow = (x) => ({ src: "NIH", pi: x.pi, org: x.org, st: x.st, amt: x.amt, end: x.end, title: x.title, code: x.code,
    kind: x.kind === "training" ? "train" : x.kind === "center" ? "ctr" : "lab", url: `https://reporter.nih.gov/project-details/${x.appl}` });
  let uRows = [], uPage = 1, uTok = 0, uCounts = {};
  const mdy = (d) => `${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getDate()).padStart(2, "0")}/${d.getFullYear()}`;
  async function runUsa() {
    const q = $("#uQ").value.trim(); if (!q) { setURL("q", ""); return usaDefault(); }
    setURL("q", q);
    const my = ++uTok; uRows = []; uCounts = {};
    $("#uTitle").textContent = `US professors with active grants on “${q}”`;
    $("#uList").innerHTML = `<p class="note">Searching official grant databases…</p>`; $("#uBig").textContent = "";
    const jobs = [];
    if ($("#uNSF").checked) jobs.push((async () => {
      const base = `https://api.nsf.gov/services/v1/awards.json?keyword=${encodeURIComponent('"' + q + '"')}&expDateStart=${encodeURIComponent(mdy(today))}&rpp=25`;
      let total = 0;
      for (let off = 1; off <= 76; off += 25) {
        const r = await fetch(base + `&offset=${off}`).then((x) => x.json());
        const a = (r.response && r.response.award) || [];
        total = ((r.response || {}).metadata || {}).totalCount || total;
        a.forEach((x) => { const o = nsfRow(x); if (o) uRows.push(o); });
        if (a.length < 25) break;
      }
      uCounts.NSF = total;
    })().catch(() => { uCounts.NSF = -1; }));
    if ($("#uNIH").checked) jobs.push((async () => {
      if (!NIH) NIH = await fetch("../data/grants/nih-index.json").then((r) => r.json()).catch(() => null);
      const ql = q.toLowerCase();
      const hit = NIH && NIH.topics.find(([t]) => t.toLowerCase() === ql) || (NIH && NIH.topics.find(([t]) => ql.includes(t.toLowerCase()) || t.toLowerCase().includes(ql)));
      if (!hit) { uCounts.NIH = null; return; }
      const d = await fetch(`../data/grants/nih-${hit[1]}.json`).then((r) => r.json());
      uCounts.NIH = d.total; uCounts.NIHtopic = d.topic;
      d.rows.forEach((x) => uRows.push(nihRow(x)));
    })().catch(() => { uCounts.NIH = -1; }));
    await Promise.all(jobs);
    if (my !== uTok) return;
    const parts = [];
    if (uCounts.NSF > 0) parts.push(`<b>${fmt(uCounts.NSF)} active NSF awards</b>`);
    if (uCounts.NIH > 0) parts.push(`<b>${fmt(uCounts.NIH)} active NIH grants</b>${uCounts.NIHtopic && uCounts.NIHtopic.toLowerCase() !== q.toLowerCase() ? ` (topic “${esc(uCounts.NIHtopic)}”)` : ""}`);
    $("#uBig").innerHTML = parts.length ? `Found ${parts.join(" and ")} on “${esc(q)}”.` :
      `No active grants found for “${esc(q)}”.${uCounts.NIH === null && $("#uNIH").checked ? " For health topics, pick one from the NIH list or search NIH RePORTER directly." : ""}`;
    uPage = 1; renderUsa();
  }
  const K = { lab: ["lab", "Individual lab grant"], train: ["train", "Training program"], ctr: ["ctr", "Research center"] };
  const endLab = (e) => { if (!e) return "—"; const [y, m] = e.split("-"); return m ? `${MON[+m - 1]} ${y}` : y; };
  function grantTable(S, cur) {
    const money = (n) => n >= 999500 ? `${cur}${(n / 1e6).toFixed(2)}M` : n >= 1e3 ? `${cur}${Math.round(n / 1e3)}K` : n ? `${cur}${n}` : "—";
    const per = (x) => x.src === "NSF" ? "total" : x.src === "NSERC" ? "per year" : x.src === "CIHR" ? "CIHR funding" : "this year";
    return `<table class="rt"><thead><tr><th>Professor (PI)</th><th class="r">Award</th><th class="r">Active until</th></tr></thead><tbody>${S.map((x) =>
      `<tr><td><b>${esc(x.pi)}</b><div class="ud-city">${esc(x.org)}${x.st ? " · " + esc(x.st) : ""}</div>
        <div class="st-gt">${esc(x.title)} <span class="gt ${K[x.kind][0]}">${K[x.kind][1]}</span> <span class="src">${x.src}</span></div>
        <div class="st-acts">${x.url ? `<a href="${esc(x.url)}" target="_blank" rel="noopener">Grant details ↗</a> ` : ""}<a href="../scientists/?q=${encodeURIComponent(x.pi)}">Find on ResearchBoard</a></div></td>
        <td class="r"><b>${money(x.amt)}</b><div class="ud-city">${per(x)}</div></td><td class="r"><span class="act">${endLab(x.end)}</span></td></tr>`).join("")}</tbody></table>`;
  }
  function sortFilter(rows, sortSel, lateSel, srcOk, labsFirst) {
    let L = rows.filter((x) => srcOk(x.src));
    if ($(lateSel).checked) L = L.filter((x) => x.end >= `${today.getFullYear() + 2}`);
    const rank = (x) => (labsFirst && x.kind === "ctr" ? 1 : 0);
    L.sort($(sortSel).value === "end" ? (a, b) => (b.end || "").localeCompare(a.end || "") : (a, b) => rank(a) - rank(b) || b.amt - a.amt);
    return L;
  }
  function renderUsa() {
    const L = sortFilter(uRows, "#uSort", "#u2028", (s) => (s === "NSF" ? $("#uNSF").checked : $("#uNIH").checked), !$("#uQ").value.trim());
    if (!L.length) { $("#uList").innerHTML = `<p class="note">No active grants to show.</p>`; $("#uMore").hidden = true; return; }
    $("#uList").innerHTML = grantTable(L.slice(0, uPage * 25), "$");
    $("#uMore").hidden = L.length <= uPage * 25;
  }

  // =================================================================== Canada active grants (NSERC + CIHR, refreshed weekly)
  let caReady = false, CA = null, CIHR = null, cRows = [], cPage = 1, cTok = 0;
  function initCanada() {
    if (caReady) return; caReady = true;
    const T = $("#tCanada");
    T.innerHTML = `<div class="st-row"><input id="cQ" type="search" placeholder='e.g. "machine learning", "solar cells", "cancer", "water treatment"' aria-label="Research topic">
      <select id="cSort" aria-label="Sort"><option value="amt">Sort: largest grant</option><option value="end">Sort: ending latest</option></select><button class="st-go" id="cGo">Search grants</button></div>
      <div class="st-chips"><label><input type="checkbox" id="cNSERC" checked> Science &amp; engineering (NSERC)</label><label><input type="checkbox" id="cCIHR" checked> Health (CIHR)</label>
        <label><input type="checkbox" id="c2028"> Only grants active until ${today.getFullYear() + 2} or later</label></div>
      <p class="st-big" id="cBig"></p>
      <div class="st-grid"><section class="panel2"><h2 id="cTitle">Canadian professors with active grants</h2><div id="cList"><p class="note">Loading…</p></div>
        <button class="ud-more" id="cMore" hidden>Load more</button></section>
        <aside><section class="panel2"><h2>Science &amp; engineering topics (NSERC)</h2><div id="cTopics" class="st-tchips note">Loading…</div><p class="note">Refreshed weekly. <a href="https://nserc-crsng.canada.ca/en/awards-database" target="_blank" rel="noopener">Search all NSERC awards ↗</a></p></section>
        <section class="panel2"><h2>How funding works in Canada</h2><p>Thesis-based MSc and PhD students are usually paid from their supervisor's grant. An <b>NSERC Discovery grant</b> is the main grant a science or engineering professor uses to pay students; <b>CIHR Project grants</b> do the same in health research.</p>
          <p><span class="gt lab">Individual lab grant</span> One professor's research program.</p><p><span class="gt train">Training program</span> NSERC CREATE and CIHR training grants fund students directly.</p><p><span class="gt ctr">Research center</span> Large team or network grants, research chairs.</p></section>
        <section class="panel2 st-tip">✉️ <b>Tip:</b> write to professors whose grants run 2+ more years. Mention the grant title and one of their recent papers, and ask whether they are taking a thesis-based MSc or PhD student.</section></aside></div>
      <p class="note">Official sources: <a href="https://nserc-crsng.canada.ca/en/awards-database" target="_blank" rel="noopener">NSERC Awards Database</a> and <a href="https://open.canada.ca/data/en/dataset/49edb1d7-5cb4-4fa7-897c-515d1aad5da3" target="_blank" rel="noopener">CIHR Grants and Awards open data</a>, refreshed weekly. NSERC amounts are the yearly instalment; the end date comes from the number of instalments left. Amounts in Canadian dollars.</p>`;
    $("#cGo").addEventListener("click", runCanada);
    $("#cQ").addEventListener("keydown", (e) => { if (e.key === "Enter") runCanada(); });
    ["#cSort", "#c2028", "#cNSERC", "#cCIHR"].forEach((k) => $(k).addEventListener("input", () => { cPage = 1; renderCanada(); }));
    $("#cMore").addEventListener("click", () => { cPage++; renderCanada(); });
    fetch("../data/grants/ca-index.json", { cache: "no-cache" }).then((r) => r.json()).then((j) => {
      CA = j;
      const tp = (j.topics || []).filter((t) => t[3] > 0);
      $("#cTopics").classList.toggle("note", !tp.length);
      $("#cTopics").innerHTML = tp.length ? tp.map(([t, s, n, k]) => `<button data-t="${esc(t)}">${esc(t)} <span>${fmt(k)}</span></button>`).join("") : "Topics appear after the next weekly update.";
      $("#cTopics").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { $("#cQ").value = b.dataset.t; runCanada(); }));
      if (P.get("q") && tab === "canada") { $("#cQ").value = P.get("q"); runCanada(); } else canadaDefault();
    }).catch(() => {
      $("#cTopics").textContent = "Topics appear after the next weekly update.";
      $("#cList").innerHTML = `<p class="note">Canadian grants are being collected and appear after the next daily update. Meanwhile, search the <a href="https://nserc-crsng.canada.ca/en/awards-database" target="_blank" rel="noopener">NSERC Awards Database ↗</a>.</p>`;
    });
  }
  const caRow = (x, src) => Object.assign({}, x, { src: x.src || src,
    url: (x.src || src) === "NSERC" ? `https://nserc-crsng.canada.ca/en/awards-database/${x.id}` : "" });
  function canadaDefault() {
    $("#cTitle").textContent = "Largest active grants in Canada";
    cRows = (CA.featured || []).map((x) => caRow(x));
    $("#cBig").innerHTML = cRows.length ? `Showing some of the largest active grants${CA.cihr ? ` — <b>${fmt(CA.cihr)} active CIHR health grants</b> and NSERC grants in ${(CA.topics || []).filter((t) => t[3] > 0).length} topics` : ""}. Type a topic to search.` : "";
    cPage = 1; renderCanada();
  }
  async function runCanada() {
    const q = $("#cQ").value.trim(); setURL("q", q);
    if (!q) return canadaDefault();
    const my = ++cTok; cRows = [];
    $("#cTitle").textContent = `Canadian professors with active grants on “${q}”`;
    $("#cList").innerHTML = `<p class="note">Searching…</p>`; $("#cBig").textContent = "";
    const ql = q.toLowerCase(), words = ql.split(/\s+/).filter(Boolean);
    let nN = 0, nC = 0, topic = "";
    const tps = (CA && CA.topics) || [];
    const hit = tps.find(([t]) => t.toLowerCase() === ql) || tps.find(([t]) => ql.includes(t.toLowerCase()) || t.toLowerCase().includes(ql));
    if (hit) {
      const d = await fetch(`../data/grants/ca-nserc-${hit[1]}.json`).then((r) => r.json()).catch(() => null);
      if (d) { topic = d.topic; d.rows.forEach((x) => cRows.push(caRow(x, "NSERC"))); nN = d.rows.length; }
    }
    // other NSERC rows already loaded (featured) whose title matches
    const have = new Set(cRows.map((x) => x.id));
    ((CA && CA.featured) || []).forEach((x) => { if (x.src === "NSERC" && !have.has(x.id) && words.every((w) => x.title.toLowerCase().includes(w))) { cRows.push(caRow(x)); nN++; } });
    if (!CIHR) CIHR = await fetch("../data/grants/ca-cihr.json").then((r) => r.json()).then((j) => j.rows).catch(() => []);
    CIHR.forEach((x) => { const h = `${x.title} ${x.kw} ${x.prog}`.toLowerCase(); if (words.every((w) => h.includes(w))) { cRows.push(caRow(x, "CIHR")); nC++; } });
    if (my !== cTok) return;
    const parts = [];
    if (nN) parts.push(`<b>${fmt(nN)} NSERC grant${nN === 1 ? "" : "s"}</b>${topic && topic.toLowerCase() !== ql ? ` (topic “${esc(topic)}”)` : ""}`);
    if (nC) parts.push(`<b>${fmt(nC)} CIHR grant${nC === 1 ? "" : "s"}</b>`);
    $("#cBig").innerHTML = parts.length ? `Found ${parts.join(" and ")} on “${esc(q)}”.` :
      `No active grants found for “${esc(q)}”. For science and engineering, pick a topic from the list or search the NSERC Awards Database directly.`;
    cPage = 1; renderCanada();
  }
  function renderCanada() {
    const L = sortFilter(cRows, "#cSort", "#c2028", (s) => (s === "NSERC" ? $("#cNSERC").checked : $("#cCIHR").checked), !$("#cQ").value.trim());
    if (!L.length) { $("#cList").innerHTML = `<p class="note">No active grants to show.</p>`; $("#cMore").hidden = true; return; }
    $("#cList").innerHTML = grantTable(L.slice(0, cPage * 25), "CA$");
    $("#cMore").hidden = L.length <= cPage * 25;
  }

  show(tab);
})();
