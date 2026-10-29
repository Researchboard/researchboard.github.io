/* All-universities directory on /universities/ (data: /data/universities/*.json, refreshed weekly) */
(function () {
  const box = document.getElementById("udir");
  if (!box) return;
  const $ = (s) => box.querySelector(s);
  const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString("en-US"));
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const BASE = "../data/universities/";
  let IDX = null, rows = [], view = [], shown = 50, sortKey = "last", sortDir = -1, cc = "", NAMES = null, cname = {};
  const doy = (() => { const n = new Date(), s = Date.UTC(n.getUTCFullYear(), 0, 1); return Math.max(1, (Date.now() - s) / 864e5); })();
  // row: [id, name, city, now, last, total, cites, h, oa, spike, typical] (+cc in front for world rows)
  const norm = (r, c) => ({ id: r[0], name: r[1], city: r[2], now: r[3], last: r[4], total: r[5], cites: r[6], h: r[7], oa: r[8],
    spike: r[9], typical: r[10], cc: c, pace: r[4] && !r[9] ? ((r[3] / doy * 365) / r[4] - 1) * 100 : null });
  const flag = (c) => c ? `<span class="fi fi-${c.toLowerCase()}"></span>` : "";

  async function get(p) { const r = await fetch(BASE + p, { cache: "no-cache" }); if (!r.ok) throw new Error(p); return r.json(); }

  function render() {
    const q = $("#udSearch").value.trim().toLowerCase();
    view = rows.filter((r) => !q || r.name.toLowerCase().includes(q) || (r.city || "").toLowerCase().includes(q));
    const key = sortKey;
    view.sort((a, b) => {
      const va = key === "last" && a.spike ? a.typical : a[key], vb = key === "last" && b.spike ? b.typical : b[key];
      if (key === "name") return sortDir * String(va).localeCompare(String(vb));
      return sortDir * ((va ?? -1e12) - (vb ?? -1e12));
    });
    const year = IDX ? IDX.year : new Date().getFullYear();
    const tb = $("#udBody");
    tb.innerHTML = view.slice(0, shown).map((r, i) => {
      const pace = r.pace == null ? "—" : `<span class="${r.pace >= 0 ? "up" : "down"}">${r.pace >= 0 ? "▲" : "▼"} ${Math.abs(r.pace).toFixed(0)}%</span>`;
      const warn = r.spike ? ` <span class="ud-warn" title="OpenAlex shows a sudden jump for this university (usually a bulk upload of old records). We rank it by a typical year (${fmt(r.typical)}).">⚠</span>` : "";
      return `<tr><td>${i + 1}</td><td class="nm">${cc ? "" : flag(r.cc)}<a href="../university/?id=${r.id}">${esc(r.name)}</a>${warn}<div class="ud-city">${esc(r.city || "")}${cc ? "" : (r.city ? ", " : "") + esc(cname[r.cc] || r.cc || "")}</div></td>` +
        `<td class="r"><b>${fmt(r.now)}</b></td><td class="r">${fmt(r.last)}</td><td class="r">${pace}</td>` +
        `<td class="r hm">${fmt(r.cites)}</td><td class="r hm">${fmt(r.h)}</td><td class="r hm">${r.oa == null ? "—" : r.oa + "%"}</td></tr>`;
    }).join("") || `<tr><td colspan="8">No university matches “${esc(q)}”.</td></tr>`;
    $("#udMore").hidden = view.length <= shown;
    $("#udMore").textContent = `Show more (${fmt(view.length - shown)} left)`;
    $("#udInfo").textContent = cc ? `${fmt(rows.length)} universities in ${cname[cc] || cc}` : (q && NAMES ? `${fmt(view.length)} matches worldwide` : `World top ${rows.length} by papers in ${year - 1}`);
    box.querySelectorAll("th[data-k]").forEach((th) => th.classList.toggle("on", th.dataset.k === sortKey));
  }

  async function loadCountry(c) {
    cc = c; shown = 50;
    $("#udBody").innerHTML = `<tr><td colspan="8">Loading…</td></tr>`;
    try {
      if (!c) rows = IDX.world.map((r) => norm(r.slice(1), r[0]));
      else rows = (await get(c + ".json")).map((r) => norm(r, c));
    } catch (_) { rows = []; }
    try { const u = new URL(location.href); if (c) u.searchParams.set("c", c); else u.searchParams.delete("c"); history.replaceState(null, "", u); } catch (_) {}
    render();
  }

  let t = null;
  $("#udSearch").addEventListener("input", () => {
    clearTimeout(t);
    t = setTimeout(async () => {
      const q = $("#udSearch").value.trim().toLowerCase();
      if (!cc && q.length >= 3) {          // world view: search every university by name
        if (!NAMES) { try { NAMES = await get("names.json"); } catch (_) { NAMES = []; } }
        const hits = NAMES.filter((n) => n[1].toLowerCase().includes(q)).slice(0, 200);
        rows = hits.map((n) => ({ id: n[0], name: n[1], cc: n[2], city: "", now: null, last: null, pace: null }));
        // fill numbers from the country files of the first few matching countries
        const ccs = [...new Set(hits.map((h) => h[2]))].slice(0, 8);
        for (const c of ccs) {
          try { const full = Object.fromEntries((await get(c + ".json")).map((r) => [r[0], r]));
            rows = rows.map((r) => (full[r.id] ? norm(full[r.id], r.cc) : r)); } catch (_) {}
        }
        shown = 50; render();
      } else if (!cc && !q) { loadCountry(""); }
      else { shown = 50; render(); }
    }, 250);
  });
  $("#udCountry").addEventListener("change", (e) => { $("#udSearch").value = ""; loadCountry(e.target.value); });
  $("#udMore").addEventListener("click", () => { shown += 100; render(); });
  box.querySelectorAll("th[data-k]").forEach((th) => th.addEventListener("click", () => {
    const k = th.dataset.k; if (sortKey === k) sortDir = -sortDir; else { sortKey = k; sortDir = k === "name" ? 1 : -1; } render();
  }));

  (async () => {
    try { IDX = await get("index.json"); }
    catch (_) { $("#udBody").innerHTML = `<tr><td colspan="8">The full list of universities is being prepared and will appear after the next weekly update.</td></tr>`; return; }
    try { const l = await fetch("../data/latest.json").then((r) => r.json()); cname = l.country_names || {}; } catch (_) {}
    const dn = new Intl.DisplayNames(["en"], { type: "region" });
    const nm = (c) => cname[c] || (() => { try { return dn.of(c); } catch (_) { return c; } })();
    IDX.countries.forEach(([c]) => { cname[c] = nm(c); });
    const opts = IDX.countries.slice().sort((a, b) => cname[a[0]].localeCompare(cname[b[0]]));
    $("#udCountry").innerHTML = `<option value="">🌍 World top ${IDX.world.length}</option>` +
      opts.map(([c, n]) => `<option value="${c}">${esc(cname[c])} (${fmt(n)})</option>`).join("");
    $("#udTotal").textContent = `${fmt(IDX.total)} universities in ${IDX.countries.length} countries`;
    const year = IDX.year;
    $("#thNow").textContent = `${year} so far`; $("#thLast").textContent = `${year - 1}`;
    const start = new URLSearchParams(location.search).get("c");
    const c0 = start && IDX.countries.some((x) => x[0] === start.toUpperCase()) ? start.toUpperCase() : "";
    $("#udCountry").value = c0;
    loadCountry(c0);
  })();
})();
