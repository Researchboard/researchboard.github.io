/* ResearchBoard — shared by every page: theme switch, site search, CSV buttons */
(function () {
  "use strict";
  const root = (document.body && document.body.dataset.root) || "./";
  const $ = (s, r) => (r || document).querySelector(s);
  const el = (t, c, x) => { const e = document.createElement(t); if (c) e.className = c; if (x != null) e.textContent = x; return e; };
  const fmt = (n) => (n == null ? "—" : Number(n).toLocaleString("en-US"));

  // ------------------------------------------------------------ theme
  const btn = $("#themeBtn");
  if (btn) btn.addEventListener("click", () => {
    const dark = getComputedStyle(document.documentElement).getPropertyValue("color-scheme").trim() === "dark";
    const t = dark ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", t);
    try { localStorage.setItem("researchboard-theme", t); } catch (_) { /* private mode */ }
    document.dispatchEvent(new CustomEvent("rb-theme"));
  });

  // ------------------------------------------------------------ search
  let IDX = null, loading = null;
  const norm = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  function load() {
    if (IDX) return Promise.resolve(IDX);
    if (!loading) loading = fetch(root + "data/search-index.json", { cache: "no-store" }).then((r) => r.json()).then((d) => {
      d.countries.forEach((c) => { c.k = norm(c[1]); });
      d.inst.forEach((i) => { i.k = norm(i[1]); });
      IDX = d; return d;
    }).catch(() => (IDX = { dates: [], countries: [], inst: [] }));
    return loading;
  }
  window.RBSearchIndex = load;
  const lastVal = (row, off) => { for (let i = row.length - 1; i >= off; i--) if (row[i] != null) return row[i]; return null; };

  function setup(box) {
    const inp = $("input", box), drop = $(".gdrop", box);
    let items = [], cur = -1;
    const go = (it) => { if (it) location.href = it.href; };
    function render(q) {
      drop.replaceChildren(); items = []; cur = -1;
      if (!q) { drop.hidden = true; return; }
      const n = norm(q);
      const score = (k) => (k.startsWith(n) ? 0 : k.includes(" " + n) ? 1 : k.includes(n) ? 2 : 9);
      const pick = (arr, max) => arr.map((r) => [score(r.k), r]).filter((x) => x[0] < 9)
        .sort((a, b) => a[0] - b[0] || (lastVal(b[1], 3) || 0) - (lastVal(a[1], 3) || 0)).slice(0, max).map((x) => x[1]);
      const C = pick(IDX.countries, 5), I = pick(IDX.inst, 7);
      const day = IDX.dates.length ? new Date(IDX.dates[IDX.dates.length - 1] + "T00:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" }) : "";
      const group = (title, rows, mk) => {
        drop.appendChild(el("div", "g", title));
        if (!rows.length) { drop.appendChild(el("div", "none", `No ${title.toLowerCase()} match "${q}"`)); return; }
        rows.forEach((r) => { const a = mk(r); drop.appendChild(a); items.push(a); });
      };
      const row = (code, name, val, href) => {
        const a = el("a"); a.href = href;
        const left = el("span", "nm");
        if (code) left.appendChild(el("span", "fi fi-" + code.toLowerCase()));
        left.append(name);
        a.append(left, el("small", null, val != null ? `${fmt(val)} papers${day ? " on " + day : ""}` : ""));
        a.addEventListener("mouseenter", () => setCur(items.indexOf(a)));
        return a;
      };
      group("Countries", C, (r) => row(r[0], r[1], lastVal(r, 3), root + "country/" + r[2] + ".html"));
      group("Institutions", I, (r) => row(r[2], r[1], lastVal(r, 3), root + "explore/?id=" + encodeURIComponent(r[0])));
      drop.appendChild(el("div", "tip", 'Try a country ("Bangladesh") or an institution ("Harvard", "Dhaka", "MIT")'));
      drop.hidden = false;
    }
    function setCur(i) { items.forEach((a, j) => a.classList.toggle("hl", j === i)); cur = i; }
    inp.addEventListener("focus", () => { load().then(() => render(inp.value.trim())); });
    inp.addEventListener("input", () => { load().then(() => render(inp.value.trim())); });
    inp.addEventListener("keydown", (e) => {
      if (drop.hidden) return;
      if (e.key === "ArrowDown") { e.preventDefault(); setCur(Math.min(items.length - 1, cur + 1)); }
      else if (e.key === "ArrowUp") { e.preventDefault(); setCur(Math.max(0, cur - 1)); }
      else if (e.key === "Enter") { e.preventDefault(); go(items[cur >= 0 ? cur : 0]); }
      else if (e.key === "Escape") { drop.hidden = true; inp.blur(); }
    });
    document.addEventListener("click", (e) => { if (!box.contains(e.target)) drop.hidden = true; });
  }
  document.querySelectorAll(".gsearch").forEach(setup);

  // ------------------------------------------------------------ period tabs + CSV on static pages
  document.querySelectorAll("[data-tabs]").forEach((tabs) => {
    const scope = tabs.closest("section, article, main") || document;
    tabs.addEventListener("click", (e) => {
      const b = e.target.closest("[data-tab]"); if (!b) return;
      tabs.querySelectorAll("[data-tab]").forEach((x) => x.classList.toggle("on", x === b));
      scope.querySelectorAll("[data-panel]").forEach((p) => { p.hidden = p.dataset.panel !== b.dataset.tab; });
    });
  });
  document.querySelectorAll("[data-csv]").forEach((b) => b.addEventListener("click", () => {
    const scope = b.closest("section, article, main") || document;
    const t = [...scope.querySelectorAll("table")].find((x) => !x.closest("[hidden]"));
    if (!t) return;
    const q = (v) => (/[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v);
    const rows = [...t.rows].map((r) => [...r.cells].map((c) => q(c.innerText.trim())).join(","));
    const a = el("a"); a.href = URL.createObjectURL(new Blob([rows.join("\n")], { type: "text/csv" }));
    a.download = (b.dataset.csv || "researchboard") + ".csv"; document.body.appendChild(a); a.click(); a.remove();
  }));
})();
